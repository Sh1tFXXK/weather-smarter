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
    return project_root / "backend" / "data" / "memory.db"


class MemoryStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages (session_id, id);"
        )
        self._conn.commit()

    def add_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = json.dumps(metadata, ensure_ascii=False) if metadata else None
        created_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO messages (session_id, role, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, payload, created_at),
            )
            self._conn.commit()

    def list_messages(self, *, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT role, content, metadata, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        rows.reverse()
        result: List[Dict[str, Any]] = []
        for role, content, metadata, created_at in rows:
            result.append(
                {
                    "role": role,
                    "content": content,
                    "metadata": json.loads(metadata) if metadata else None,
                    "timestamp": created_at,
                }
            )
        return result

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self._conn.commit()


_STORE: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _STORE
    if _STORE is None:
        db_path = Path(os.getenv("MEMORY_DB_PATH", str(_default_db_path())))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _STORE = MemoryStore(db_path)
    return _STORE
