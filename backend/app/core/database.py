"""Database configuration and session management using SQLAlchemy 2.0.

Provides:
- SQLAlchemy Engine with connection pooling
- Scoped SessionLocal factory
- Declarative Base class for all ORM models
- Dependency generator `get_db()` for FastAPI route dependency injection
- Health check utility `check_database_connection()`
"""

import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session, DeclarativeBase
from app.core.config import settings

logger = logging.getLogger(__name__)

# Connection arguments (e.g. SQLite requires check_same_thread: False)
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Create database engine with pool pre-ping (validates connection liveness before use)
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=settings.DEBUG and False,  # Set to True if detailed SQL queries logging is desired
)

# Session factory for creating transactional database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a transactional database session per request.

    Ensures the session is always closed after the request completes,
    preventing connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """Verifies database reachability by executing a lightweight SELECT 1 query."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"Database connection check failed: {e}")
        return False
