"""Yerel hesap doğrulaması — SQLite kullanıcı + oturum (cookie) tabanlı.

Parolalar PBKDF2-HMAC-SHA256 (stdlib) ile saklanır; oturum token'ı rastgele
üretilip `sessions` tablosunda tutulur ve HttpOnly cookie'de taşınır.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

from app.config import settings
from app.services import store

SESSION_COOKIE = "ir_session"
_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                 _PBKDF2_ITERATIONS).hex()
    return f"pbkdf2:{_PBKDF2_ITERATIONS}:{salt}:{digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split(":")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                   int(iterations)).hex()
        return hmac.compare_digest(calc, digest)
    except (ValueError, AttributeError):
        return False


def ensure_admin() -> Dict[str, Any]:
    """Hiç kullanıcı yoksa varsayılan `admin`/`admin` hesabını açar.

    Kullanıcılar varsa ilk oluşturulanı döner (sahipsiz kayıtları devralmak için).
    """
    if store.users_empty():
        return store.create_user("admin", hash_password("admin"))
    user = store.get_user_by_username("admin")
    return user if user else store.first_user()


def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    user = store.get_user_by_username(username)
    if user is None or not verify_password(password, user["password_hash"]):
        return None
    return {"id": user["id"], "username": user["username"]}


def open_session(user_id: str) -> str:
    return store.create_session(user_id, settings.SESSION_TTL_DAYS)


def close_session(token: str) -> None:
    store.delete_session(token)


def get_current_user(request: Request) -> Dict[str, Any]:
    """FastAPI dependency: oturum cookie'sini doğrular, kullanıcıyı döner."""
    token = request.cookies.get(SESSION_COOKIE)
    user = store.get_session_user(token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Oturum gerekli — giriş yapın.")
    return user
