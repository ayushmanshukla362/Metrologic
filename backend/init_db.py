"""Minimal database initialization entry point."""

from . import models  # noqa: F401  # Register all tables with Base.metadata.
from .database import Base, get_engine


def create_tables() -> None:
    """Create the Phase 2A tables in the configured PostgreSQL database."""
    Base.metadata.create_all(bind=get_engine())


if __name__ == "__main__":
    create_tables()
