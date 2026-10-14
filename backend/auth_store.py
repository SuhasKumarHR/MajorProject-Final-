"""Small SQLite-backed authentication store for local ACR_AGENT deployments.

SQLite is deliberately used here instead of a hosted PostgreSQL service.  It is
free, requires no daemon, and is included with Python.  Passwords are never
stored in plaintext; sessions are opaque, randomly generated cookies whose
hashes are stored in the database.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "data" / "acr_agent.sqlite3"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
PBKDF2_ROUNDS = 310_000


def database_path() -> Path:
    configured = os.getenv("ACR_AUTH_DB", "").strip()
    path = Path(configured) if configured else DEFAULT_DB
    if not path.is_absolute():
        path = BASE_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
            """
        )


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def _password_digest(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS
    ).hex()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user(name: str, email: str, password: str) -> dict[str, Any]:
    clean_name = " ".join(name.split())
    clean_email = _normalise_email(email)
    if len(clean_name) < 2:
        raise ValueError("Name must contain at least 2 characters.")
    if "@" not in clean_email or len(clean_email) > 254:
        raise ValueError("Enter a valid email address.")
    if len(password) < 8 or len(password) > 256:
        raise ValueError("Password must contain 8 to 256 characters.")

    salt = secrets.token_bytes(16)
    digest = _password_digest(password, salt)
    now = int(time.time())
    try:
        with _connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users(name, email, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?, ?)",
                (clean_name, clean_email, digest, salt.hex(), now),
            )
            user_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise ValueError("An account with this email already exists.") from exc
    return {"id": user_id, "name": clean_name, "email": clean_email}


def authenticate(email: str, password: str) -> dict[str, Any] | None:
    clean_email = _normalise_email(email)
    with _connect() as connection:
        row = connection.execute(
            "SELECT id, name, email, password_hash, password_salt FROM users WHERE email = ?",
            (clean_email,),
        ).fetchone()
    if row is None:
        return None
    expected = _password_digest(password, bytes.fromhex(row["password_salt"]))
    if not hmac.compare_digest(expected, row["password_hash"]):
        return None
    return {"id": int(row["id"]), "name": row["name"], "email": row["email"]}


def get_or_create_oauth_user(name: str, email: str) -> dict[str, Any]:
    """Create or reuse a user after Google has verified the email address."""
    clean_name = " ".join(name.split()) or "Google operator"
    clean_email = _normalise_email(email)
    if "@" not in clean_email or len(clean_email) > 254:
        raise ValueError("Google did not return a valid email address.")
    with _connect() as connection:
        row = connection.execute(
            "SELECT id, name, email FROM users WHERE email = ?", (clean_email,)
        ).fetchone()
        if row is not None:
            return {"id": int(row["id"]), "name": row["name"], "email": row["email"]}

        # OAuth users do not use this random password. It only satisfies the
        # shared users table; Google remains the identity provider.
        salt = secrets.token_bytes(16)
        random_password = secrets.token_urlsafe(48)
        cursor = connection.execute(
            "INSERT INTO users(name, email, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?, ?)",
            (clean_name, clean_email, _password_digest(random_password, salt), salt.hex(), int(time.time())),
        )
        return {"id": int(cursor.lastrowid), "name": clean_name, "email": clean_email}


def create_session(user_id: int, remember: bool = True) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    lifetime = SESSION_TTL_SECONDS if remember else 60 * 60 * 8
    with _connect() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        connection.execute(
            "INSERT INTO sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (_token_hash(token), user_id, now + lifetime, now),
        )
    return token


def user_for_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    now = int(time.time())
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT users.id, users.name, users.email
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
            """,
            (_token_hash(token), now),
        ).fetchone()
        connection.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    if row is None:
        return None
    return {"id": int(row["id"]), "name": row["name"], "email": row["email"]}


def delete_session(token: str | None) -> None:
    if not token:
        return
    with _connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

