"""
mongo.py — Async MongoDB client for Aegis PII Scanner.
Uses Motor (async PyMongo wrapper) for non-blocking database access.

Collections:
  users         — registered user accounts
  scan_history  — per-user lightweight scan summaries
  user_profiles — per-user profile map + last scan results
"""

import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB", "aegis_db")

# Lazily initialised — set by lifespan or first call
_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGODB_URI)
        logger.info("MongoDB client created: %s / %s", MONGODB_URI, DB_NAME)
    return _client


def get_db():
    return get_client()[DB_NAME]


def get_users_col():
    return get_db()["users"]


def get_history_col():
    return get_db()["scan_history"]


def get_profile_col():
    return get_db()["user_profiles"]
