"""
auth.py — JWT authentication utilities for Aegis PII Scanner.

NOTE: We use the `bcrypt` library directly (not passlib).
Passlib's detect_wrap_bug() is broken with bcrypt >= 4.0 on Python 3.12.

We pre-hash passwords with SHA-256 (always 64 hex chars) before bcrypt,
so we are always safely under the 72-byte bcrypt limit regardless.
"""

import os
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("AEGIS_JWT_SECRET", "aegis-super-secret-key-change-in-production-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("AEGIS_TOKEN_EXPIRE_MIN", "1440"))  # 24 h

# ──────────────────────────────────────────────────────────────────
# Password hashing  (SHA-256 pre-hash → bcrypt)
# passlib is intentionally NOT used; its detect_wrap_bug() is broken
# with bcrypt >= 4.0.x on Python 3.12.
# ──────────────────────────────────────────────────────────────────

def _pre_hash(password: str) -> bytes:
    """
    SHA-256 hex digest → always 64 ASCII chars → safely under bcrypt's 72-byte limit.
    Returns bytes ready for bcrypt.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")


def get_password_hash(password: str) -> str:
    """Hash password with bcrypt (after SHA-256 pre-hash). Returns string."""
    hashed = bcrypt.hashpw(_pre_hash(password), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(_pre_hash(plain_password), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────
# JWT helpers
# ──────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception


# ──────────────────────────────────────────────────────────────────
# FastAPI dependency
# ──────────────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_token(token)
    return {
        "email": payload.get("sub"),
        "full_name": payload.get("name", ""),
        "user_id": payload.get("uid"),
    }
