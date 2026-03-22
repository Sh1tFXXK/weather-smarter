from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _default_db_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "backend" / "data" / "health_profiles.db"


class HealthProfileStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS health_profiles (
                user_id TEXT PRIMARY KEY,
                conditions TEXT,
                note TEXT,
                consent INTEGER NOT NULL,
                sensitivity TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def upsert_profile(
        self,
        *,
        user_id: str,
        conditions: List[str],
        note: Optional[str],
        consent: bool,
        sensitivity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        payload_conditions = json.dumps(conditions, ensure_ascii=False)
        payload_sensitivity = json.dumps(sensitivity, ensure_ascii=False) if sensitivity else None
        with self._lock:
            existing = self._conn.execute(
                "SELECT created_at FROM health_profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
            created_at = existing[0] if existing else now
            self._conn.execute(
                """
                INSERT INTO health_profiles (user_id, conditions, note, consent, sensitivity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    conditions=excluded.conditions,
                    note=excluded.note,
                    consent=excluded.consent,
                    sensitivity=excluded.sensitivity,
                    updated_at=excluded.updated_at
                """,
                (
                    user_id,
                    payload_conditions,
                    note,
                    1 if consent else 0,
                    payload_sensitivity,
                    created_at,
                    now,
                ),
            )
            self._conn.commit()
        return {
            "user_id": user_id,
            "conditions": conditions,
            "note": note,
            "consent": consent,
            "sensitivity": sensitivity or {},
            "created_at": created_at,
            "updated_at": now,
            "source": "mock",
        }

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT user_id, conditions, note, consent, sensitivity, created_at, updated_at
                FROM health_profiles
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if not row:
            return None
        conditions = json.loads(row[1]) if row[1] else []
        sensitivity = json.loads(row[4]) if row[4] else {}
        return {
            "user_id": row[0],
            "conditions": conditions,
            "note": row[2],
            "consent": bool(row[3]),
            "sensitivity": sensitivity,
            "created_at": row[5],
            "updated_at": row[6],
            "source": "mock",
        }

    def delete_profile(self, user_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM health_profiles WHERE user_id = ?", (user_id,)
            )
            self._conn.commit()
        return cur.rowcount > 0


_STORE: Optional[HealthProfileStore] = None


def get_health_profile_store() -> HealthProfileStore:
    global _STORE
    if _STORE is None:
        db_path = Path(os.getenv("HEALTH_PROFILE_DB_PATH", str(_default_db_path())))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _STORE = HealthProfileStore(db_path)
    return _STORE
