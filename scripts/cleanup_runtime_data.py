from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "backend" / "data"


def cleanup_tasks() -> int:
    db_path = DATA_DIR / "tasks.db"
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            """
            DELETE FROM tasks
            WHERE json_extract(metadata, '$.source') = 'test'
            """
        )
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def cleanup_memory() -> int:
    db_path = DATA_DIR / "memory.db"
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            """
            DELETE FROM messages
            WHERE session_id LIKE 'startup-check%'
               OR session_id LIKE 'query-no-%'
               OR session_id IN (
                    'placeholder-location-user',
                    'profile-analysis-user',
                    'health-alerts-no-profile',
                    'query-profile-user'
               )
            """
        )
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def main() -> None:
    deleted_tasks = cleanup_tasks()
    deleted_messages = cleanup_memory()
    print(f"deleted_tasks={deleted_tasks}")
    print(f"deleted_messages={deleted_messages}")


if __name__ == "__main__":
    main()
