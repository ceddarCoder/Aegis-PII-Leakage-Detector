"""
database.py — SQLite database setup and session management.

Usage:
    from database import get_db, init_db

    init_db()  # call once at startup

    with get_db() as db:
        db.add(record)
        db.commit()
"""

import os
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from models import Base

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

DB_PATH = os.getenv("AEGIS_DB_PATH", "./aegis.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + multi-thread
    echo=False,
)

# Enable WAL mode for better concurrent read performance
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create all tables if they don't already exist.
    Safe to call multiple times (idempotent).
    """
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized at: %s", DB_PATH)


@contextmanager
def get_db() -> Session:
    """
    Context manager that yields a database session and handles
    commit/rollback/close automatically.

    Usage:
        with get_db() as db:
            db.add(some_record)
            db.commit()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Return a raw session (caller is responsible for commit/close).
    Prefer get_db() context manager for most use cases.
    """
    return SessionLocal()
