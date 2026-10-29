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

if raw_db_url and raw_db_url.strip():
    # Handle cloud providers (e.g. Render/Heroku) using postgres:// instead of postgresql://
    if raw_db_url.startswith("postgres://"):
        raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
    
    engine = create_engine(
        raw_db_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=False
    )
else:
    DB_PATH = DATA_DIR / "applications.db"
    DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
