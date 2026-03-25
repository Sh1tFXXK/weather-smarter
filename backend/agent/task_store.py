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
    return project_root / "backend" / "data" / "tasks.db"


class TaskStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                priority INTEGER NOT NULL,
                metadata TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_time ON tasks (scheduled_time, id);"
        )
        self._conn.commit()

    def create_task(
        self,
        *,
        task_type: str,
        scheduled_time: str,
        priority: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        payload_metadata = json.dumps(metadata or {}, ensure_ascii=False)
        status = "scheduled"
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO tasks (type, scheduled_time, priority, metadata, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task_type, scheduled_time, priority, payload_metadata, status, now, now),
            )
            self._conn.commit()
            task_id = int(cursor.lastrowid)
        return {
            "task_id": task_id,
            "type": task_type,
            "status": status,
            "scheduledTime": scheduled_time,
            "priority": priority,
            "metadata": metadata or {},
            "createdAt": now,
            "updatedAt": now,
            "source": "sqlite",
        }

    def list_tasks(self, *, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, type, scheduled_time, priority, metadata, status, created_at, updated_at
                FROM tasks
                ORDER BY scheduled_time ASC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "task_id": row[0],
                    "type": row[1],
                    "scheduledTime": row[2],
                    "priority": row[3],
                    "metadata": json.loads(row[4]) if row[4] else {},
                    "status": row[5],
                    "createdAt": row[6],
                    "updatedAt": row[7],
                    "source": "sqlite",
                }
            )
        return result


_STORE: Optional[TaskStore] = None


def get_task_store() -> TaskStore:
    global _STORE
    if _STORE is None:
        db_path = Path(os.getenv("TASK_DB_PATH", str(_default_db_path())))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _STORE = TaskStore(db_path)
    return _STORE
