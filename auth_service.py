"""Zero-dependency Authentication & Session Service for Bharat Praman.

Uses Python standard library (sqlite3, hashlib, hmac, secrets) with
PBKDF2-HMAC-SHA256 (100,000 iterations + 16-byte random salt).
Manages user accounts, sessions, and tier upgrades without external dependencies.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("uvicorn.error")

DB_PATH = Path(os.getenv("AUTH_DB_PATH", Path(__file__).parent / "auth.db")).resolve()
VALID_PROMO_CODES = {"BHARAT_PRO_2026", "BHARAT_ENTERPRISE", "PRO_VAULT_VIP"}
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite tables for users and active bearer sessions."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                name TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'free',
                created_at REAL NOT NULL
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
        """)
        conn.commit()


def _hash_pw(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex()


def register_user(
    email: str,
    password: str,
    name: str = "",
    tier: str = "free",
    promo_code: Optional[str] = None,
) -> dict:
    """Register a new user account. Raises ValueError on duplicate email or invalid input."""
    email_clean = (email or "").strip().lower()
    if not EMAIL_REGEX.match(email_clean):
        raise ValueError("Invalid email address format.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    init_db()
    assigned_tier = "free"
    if promo_code and promo_code.strip().upper() in VALID_PROMO_CODES:
        assigned_tier = "premium"
    elif tier in ("free", "premium", "admin"):
        assigned_tier = tier

    user_id = f"usr_{secrets.token_hex(8)}"
    salt_hex = secrets.token_hex(16)
    pw_hash = _hash_pw(password, salt_hex)
    display_name = name.strip() or email_clean.split("@")[0].title()
    now = time.time()

    with get_db() as conn:
        try:
            conn.execute(
                """
                INSERT INTO users (id, email, password_hash, salt, name, tier, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, email_clean, pw_hash, salt_hex, display_name, assigned_tier, now),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError("An account with this email already exists.")

    return {
        "id": user_id,
        "email": email_clean,
        "name": display_name,
        "tier": assigned_tier,
        "created_at": now,
    }


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Verify email/password and issue a 30-day Bearer session token."""
    init_db()
    email_clean = (email or "").strip().lower()
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email_clean,),
        ).fetchone()
        if not row:
            return None

        expected_hash = _hash_pw(password, row["salt"])
        if not hmac.compare_digest(expected_hash, row["password_hash"]):
            return None

        user_id = row["id"]
        token = f"bp_tok_{secrets.token_urlsafe(32)}"
        now = time.time()
        expires = now + (30 * 86400)  # 30 days

        conn.execute(
            """
            INSERT INTO sessions (token, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, user_id, now, expires),
        )
        conn.commit()

        return {
            "token": token,
            "user": {
                "id": row["id"],
                "email": row["email"],
                "name": row["name"],
                "tier": row["tier"],
            },
        }


def get_user_from_token(token: str) -> Optional[dict]:
    """Retrieve user dictionary given a Bearer session token."""
    if not token:
        return None
    init_db()
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    now = time.time()
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.name, u.tier, s.expires_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, now),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "tier": row["tier"],
        }


def upgrade_user(user_id: str, promo_code: str) -> bool:
    """Upgrade user to premium using a verified enterprise promo code."""
    init_db()
    if not promo_code or promo_code.strip().upper() not in VALID_PROMO_CODES:
        return False

    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE users SET tier = 'premium' WHERE id = ?",
            (user_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def logout(token: str) -> bool:
    """Invalidate session token."""
    if not token:
        return False
    init_db()
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return cursor.rowcount > 0


# Self-initialize on import
try:
    init_db()
except Exception as _e:
    logger.warning("auth_service init_db warning: %s", _e)
