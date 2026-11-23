"""Tarama geçmişi — SQLite'ta kalıcı kayıt.

İşletme listesi JSON blob olarak saklanır; liste ekranı işletme detayını
getirmez, tek kayıt açıldığında blob çözülür.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id          TEXT PRIMARY KEY,
    scanned_at  TEXT NOT NULL,
    lat         REAL NOT NULL,
    lng         REAL NOT NULL,
    radius_m    INTEGER NOT NULL,
    stats_json  TEXT NOT NULL,
    businesses_json TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def _row_to_summary(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "scanned_at": row["scanned_at"],
        "lat": row["lat"],
        "lng": row["lng"],
        "radius_m": row["radius_m"],
        "stats": json.loads(row["stats_json"]),
    }


def insert_scan(lat: float, lng: float, radius_m: int,
                stats: Dict[str, Any], businesses: List[Dict[str, Any]]) -> Dict[str, Any]:
    rec = {
        "id": uuid.uuid4().hex[:12],
        "scanned_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "lat": lat, "lng": lng, "radius_m": radius_m,
        "stats": stats, "businesses": businesses,
    }
    with _connect() as conn:
        conn.execute(
            "INSERT INTO scans (id, scanned_at, lat, lng, radius_m, stats_json, businesses_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (rec["id"], rec["scanned_at"], lat, lng, radius_m,
             json.dumps(stats, ensure_ascii=False), json.dumps(businesses, ensure_ascii=False)),
        )
    return rec


def list_scans() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, scanned_at, lat, lng, radius_m, stats_json FROM scans"
            " ORDER BY scanned_at DESC"
        ).fetchall()
    return [_row_to_summary(r) for r in rows]


def get_scan(scan_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if row is None:
        return None
    rec = _row_to_summary(row)
    rec["businesses"] = json.loads(row["businesses_json"])
    return rec


def delete_scan(scan_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    return cur.rowcount > 0
