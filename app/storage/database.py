import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.storage.models import Base

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

raw_db_url = os.getenv("DATABASE_URL")

def build_engine(url_str: str = None):
    if url_str and url_str.strip():
        # Handle cloud providers (e.g. Render/Heroku) using postgres:// instead of postgresql://
        if url_str.startswith("postgres://"):
            url_str = url_str.replace("postgres://", "postgresql://", 1)
        
        # Auto-sanitize accidental double colons in user:password
        if "://" in url_str:
            scheme, rest = url_str.split("://", 1)
            if "::" in rest:
                rest = rest.replace("::", ":", 1)
            # Ensure sslmode=require for Supabase pooler connections
            if "supabase" in rest and "sslmode=" not in rest:
                sep = "&" if "?" in rest else "?"
                rest = f"{rest}{sep}sslmode=require"
            url_str = f"{scheme}://{rest}"

        try:
            return create_engine(
                url_str,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                echo=False
            )
        except Exception as e:
            print(f"[DATABASE WARNING] Could not create PostgreSQL engine: {e}. Falling back to SQLite.")

    # SQLite fallback
    DB_PATH = DATA_DIR / "applications.db"
    sqlite_url = f"sqlite:///{DB_PATH.as_posix()}"
    return create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
        echo=False
    )

engine = build_engine(raw_db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    global engine, SessionLocal
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[DATABASE WARNING] Failed initializing DB schema: {e}. Falling back to SQLite.")
        DB_PATH = DATA_DIR / "applications.db"
        sqlite_url = f"sqlite:///{DB_PATH.as_posix()}"
        engine = create_engine(sqlite_url, connect_args={"check_same_thread": False}, echo=False)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
