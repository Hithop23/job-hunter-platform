from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base declarativa única para todos los modelos ORM."""


def make_engine(db_path: Path | str) -> Engine:
    """Crea el engine SQLite. Acepta ':memory:' para pruebas."""
    db_path = Path(db_path)
    if str(db_path) in (":memory:", "", "sqlite://"):
        return create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
        )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    from app import models  # noqa: F401  (importa para registrar los modelos)

    Base.metadata.create_all(engine)
