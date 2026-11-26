"""Kalıcı kayıtlar — PostgreSQL (`DATABASE_URL`) veya SQLite (`data/scans.db`).

Tarama geçmişi, kullanıcılar, oturumlar ve favoriler burada tutulur.
İşletme listesi JSON blob olarak saklanır; liste ekranı işletme detayını
getirmez, tek kayıt açıldığında blob çözülür. Tüm sorgular kullanıcı
bazlıdır: kayıtlar `user_id` ile sahibine bağlanır.

`DATABASE_URL` doluysa Postgres'e bağlanılır (Docker); boşsa yerel
geliştirme ve testler için SQLite dosyası kullanılır. SQL'ler `?`
yer tutuculu yazılır; Postgres'te `%s`'e çevrilir.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import secrets
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scans (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    scanned_at  TEXT NOT NULL,
    lat         REAL NOT NULL,
    lng         REAL NOT NULL,
    radius_m    INTEGER NOT NULL,
    stats_json  TEXT NOT NULL,
    businesses_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scans_user ON scans(user_id);
CREATE TABLE IF NOT EXISTS favorites (
    user_id  TEXT NOT NULL,
    scan_id  TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (user_id, scan_id)
);
CREATE TABLE IF NOT EXISTS business_favorites (
    user_id    TEXT NOT NULL,
    place_id   TEXT NOT NULL,
    scan_id    TEXT NOT NULL DEFAULT '',
    added_at   TEXT NOT NULL,
    business_json TEXT NOT NULL,
    PRIMARY KEY (user_id, place_id)
);
CREATE TABLE IF NOT EXISTS quick_messages (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT '',
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Tarama özetine favori durumunu ekleyen ortak SELECT ifadesi.
_FAV_FLAG = "EXISTS(SELECT 1 FROM favorites f WHERE f.user_id = s.user_id AND f.scan_id = s.id) AS fav"


def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _pg() -> bool:
    return bool(settings.DATABASE_URL)


class _PgCompat:
    """psycopg bağlantısını sqlite3 benzeri arayüze sarar.

    `?` yer tutucuları `%s`'e çevirir; `with` bloğu çıkışında psycopg
    commit/close yapar (sqlite3 bağlam yöneticisiyle aynı sözleşme).
    """

    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._conn.__exit__(exc_type, exc, tb)

    def execute(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql.replace("?", "%s"), params)

    def executescript(self, script: str) -> None:
        for stmt in script.split(";"):
            if stmt.strip():
                self._conn.execute(stmt)


def _connect():
    if _pg():
        import psycopg
        from psycopg.rows import dict_row

        return _PgCompat(psycopg.connect(settings.DATABASE_URL, row_factory=dict_row))
    conn = sqlite3.connect(settings.db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    if _pg():
        with _connect() as conn:
            # Postgres'te REAL 4 bayattır; koordinat hassasiyeti için DOUBLE PRECISION.
            conn.executescript(_SCHEMA.replace("REAL", "DOUBLE PRECISION"))
            # Tek kullanıcılı dönemden kalan scans tablosunda user_id eksikse
            # eklenir (yeni şemada zaten var; IF NOT EXISTS no-op olur).
            conn.execute(
                "ALTER TABLE scans ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT ''")
            conn.execute(
                "ALTER TABLE quick_messages ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT ''")
        return
    os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)
    with _connect() as conn:
        # Tek kullanıcılı dönemden kalan scans tablosuna önce kolon eklenir ki
        # _SCHEMA'daki idx_scans_user index'i oluşturulabilsin (sahip sonra atanır).
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "scans" in tables:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(scans)")}
            if "user_id" not in cols:
                conn.execute("ALTER TABLE scans ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
        if "quick_messages" in tables:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(quick_messages)")}
            if "title" not in cols:
                conn.execute("ALTER TABLE quick_messages ADD COLUMN title TEXT NOT NULL DEFAULT ''")
        conn.executescript(_SCHEMA)


def claim_unowned_scans(user_id: str) -> None:
    """Kullanıcı kavramı öncesi kayıtları (user_id='') verilen kullanıcıya bağlar."""
    with _connect() as conn:
        conn.execute("UPDATE scans SET user_id = ? WHERE user_id = ''", (user_id,))


_IMPORT_TABLES = ("users", "sessions", "scans", "favorites",
                  "business_favorites", "quick_messages")


def import_sqlite_if_empty(sqlite_path: str) -> int:
    """Postgres modunda, users tablosu boşken eski SQLite dosyasını aktarır.

    Bir kere çalışması amaçlanır; users doluysa ya da dosya yoksa no-op.
    Dönüş: taşınan satır sayısı.
    """
    if not _pg() or not os.path.isfile(sqlite_path) or not users_empty():
        return 0
    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    moved = 0
    try:
        names = {r[0] for r in src.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        with _connect() as conn:
            for table in _IMPORT_TABLES:
                if table not in names:
                    continue
                rows = src.execute(f"SELECT * FROM {table}").fetchall()
                if not rows:
                    continue
                cols = list(rows[0].keys())
                marks = ", ".join(["?"] * len(cols))
                for r in rows:
                    conn.execute(
                        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({marks})"
                        " ON CONFLICT DO NOTHING",
                        tuple(r[c] for c in cols),
                    )
                    moved += 1
    finally:
        src.close()
    return moved


# ---- Kullanıcılar ----

def users_empty() -> bool:
    with _connect() as conn:
        return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None


def first_user() -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT id, username FROM users LIMIT 1").fetchone()
    return dict(row) if row else None


def create_user(username: str, password_hash: str) -> Dict[str, Any]:
    user = {"id": uuid.uuid4().hex[:12], "username": username}
    with _connect() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], username, password_hash, _utcnow()),
        )
    return user


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    return dict(row) if row else None


# ---- Oturumlar ----

def create_session(user_id: str, ttl_days: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=ttl_days)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, _utcnow(), expires.isoformat(timespec="seconds")),
        )
    return token


def get_session_user(token: str) -> Optional[Dict[str, Any]]:
    """Token'ı çözüp sahibini döner; süresi dolmuş oturumu siler."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT s.user_id, s.expires_at, u.username FROM sessions s"
            " JOIN users u ON u.id = s.user_id WHERE s.token = ?",
            (token,),
        ).fetchone()
        if row is None:
            return None
        if row["expires_at"] < _utcnow():
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            return None
        return {"id": row["user_id"], "username": row["username"]}


def delete_session(token: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ---- Taramalar ----

def _row_to_summary(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "scanned_at": row["scanned_at"],
        "lat": row["lat"],
        "lng": row["lng"],
        "radius_m": row["radius_m"],
        "stats": json.loads(row["stats_json"]),
        "is_favorite": bool(row["fav"]),
    }


def insert_scan(user_id: str, lat: float, lng: float, radius_m: int,
                stats: Dict[str, Any], businesses: List[Dict[str, Any]]) -> Dict[str, Any]:
    rec = {
        "id": uuid.uuid4().hex[:12],
        "scanned_at": _utcnow(),
        "lat": lat, "lng": lng, "radius_m": radius_m,
        "stats": stats, "businesses": businesses,
    }
    with _connect() as conn:
        conn.execute(
            "INSERT INTO scans (id, user_id, scanned_at, lat, lng, radius_m, stats_json, businesses_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rec["id"], user_id, rec["scanned_at"], lat, lng, radius_m,
             json.dumps(stats, ensure_ascii=False), json.dumps(businesses, ensure_ascii=False)),
        )
    return rec


def list_scans(user_id: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT s.id, s.scanned_at, s.lat, s.lng, s.radius_m, s.stats_json, {_FAV_FLAG}"
            " FROM scans s WHERE s.user_id = ? ORDER BY s.scanned_at DESC",
            (user_id,),
        ).fetchall()
    return [_row_to_summary(r) for r in rows]


def get_scan(scan_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            f"SELECT s.*, {_FAV_FLAG} FROM scans s WHERE s.id = ? AND s.user_id = ?",
            (scan_id, user_id),
        ).fetchone()
    if row is None:
        return None
    rec = _row_to_summary(row)
    rec["businesses"] = json.loads(row["businesses_json"])
    return rec


def delete_scan(scan_id: str, user_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM scans WHERE id = ? AND user_id = ?", (scan_id, user_id))
        if cur.rowcount:
            conn.execute("DELETE FROM favorites WHERE scan_id = ?", (scan_id,))
    return cur.rowcount > 0


# ---- Favoriler ----

def list_favorites(user_id: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT s.id, s.scanned_at, s.lat, s.lng, s.radius_m, s.stats_json, 1 AS fav"
            " FROM scans s JOIN favorites f ON f.scan_id = s.id AND f.user_id = s.user_id"
            " WHERE s.user_id = ? ORDER BY f.added_at DESC",
            (user_id,),
        ).fetchall()
    return [_row_to_summary(r) for r in rows]


def add_favorite(user_id: str, scan_id: str) -> bool:
    """Sahip olunan taramayı favoriler; tarama yoksa/başkasınsa False."""
    with _connect() as conn:
        owned = conn.execute(
            "SELECT 1 FROM scans WHERE id = ? AND user_id = ?", (scan_id, user_id)
        ).fetchone()
        if owned is None:
            return False
        conn.execute(
            ("INSERT INTO favorites (user_id, scan_id, added_at) VALUES (?, ?, ?)"
             " ON CONFLICT DO NOTHING") if _pg() else
            "INSERT OR IGNORE INTO favorites (user_id, scan_id, added_at) VALUES (?, ?, ?)",
            (user_id, scan_id, _utcnow()),
        )
    return True


def remove_favorite(user_id: str, scan_id: str) -> bool:
    """Favoriyi kaldırır; tarama sahibi değilse/yoksa False."""
    with _connect() as conn:
        owned = conn.execute(
            "SELECT 1 FROM scans WHERE id = ? AND user_id = ?", (scan_id, user_id)
        ).fetchone()
        if owned is None:
            return False
        conn.execute("DELETE FROM favorites WHERE user_id = ? AND scan_id = ?", (user_id, scan_id))
    return True


# ---- İşletme favorileri ----

def list_business_favorites(user_id: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT place_id, added_at, business_json FROM business_favorites"
            " WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,),
        ).fetchall()
    return [
        {"place_id": r["place_id"], "added_at": r["added_at"],
         "business": json.loads(r["business_json"])}
        for r in rows
    ]


def add_business_favorite(user_id: str, place_id: str,
                          business: Dict[str, Any], scan_id: str = "") -> None:
    """İşletme snapshot'ını favoriler; tekrar ekleme snapshot'ı tazeler."""
    with _connect() as conn:
        params = (user_id, place_id, scan_id, _utcnow(),
                  json.dumps(business, ensure_ascii=False))
        if _pg():
            conn.execute(
                "INSERT INTO business_favorites"
                " (user_id, place_id, scan_id, added_at, business_json)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (user_id, place_id) DO UPDATE SET"
                " scan_id = EXCLUDED.scan_id, added_at = EXCLUDED.added_at,"
                " business_json = EXCLUDED.business_json",
                params,
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO business_favorites"
                " (user_id, place_id, scan_id, added_at, business_json) VALUES (?, ?, ?, ?, ?)",
                params,
            )


def remove_business_favorite(user_id: str, place_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM business_favorites WHERE user_id = ? AND place_id = ?",
            (user_id, place_id),
        )
    return cur.rowcount > 0


# ---- Hızlı mesajlar ----

def list_quick_messages(user_id: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, text, created_at FROM quick_messages"
            " WHERE user_id = ? ORDER BY created_at DESC"
            + (", id DESC" if _pg() else ", rowid DESC"),
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_quick_message(user_id: str, title: str, text: str) -> Dict[str, Any]:
    msg = {"id": uuid.uuid4().hex[:12], "title": title.strip(),
           "text": text.strip(), "created_at": _utcnow()}
    with _connect() as conn:
        conn.execute(
            "INSERT INTO quick_messages (id, user_id, title, text, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (msg["id"], user_id, msg["title"], msg["text"], msg["created_at"]),
        )
    return msg


def update_quick_message(user_id: str, msg_id: str, title: str, text: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE quick_messages SET title = ?, text = ? WHERE id = ? AND user_id = ?",
            (title.strip(), text.strip(), msg_id, user_id),
        )
    return cur.rowcount > 0


def delete_quick_message(user_id: str, msg_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM quick_messages WHERE id = ? AND user_id = ?", (msg_id, user_id)
        )
    return cur.rowcount > 0
