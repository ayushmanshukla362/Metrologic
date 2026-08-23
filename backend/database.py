"""SQLAlchemy connection and declarative base for the MetroLogic database."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


class Base(DeclarativeBase):
    """Base class for all database models."""


def get_database_url() -> str:
    """Return the database URL supplied by the process environment."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return database_url


def get_engine() -> Engine:
    """Create an engine using the configured Neon PostgreSQL URL."""
    database_url = make_url(get_database_url())
    if database_url.drivername in {"postgres", "postgresql"}:
        database_url = database_url.set(drivername="postgresql+psycopg")
    return create_engine(database_url, pool_pre_ping=True)


def get_session() -> Session:
    """Create a SQLAlchemy session for the configured database."""
    session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return session_factory()
