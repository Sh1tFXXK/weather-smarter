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
                display_name TEXT,
                persona TEXT,
                identity_summary TEXT,
                role TEXT,
                organization TEXT,
                home_base TEXT,
                family_structure TEXT,
                asset_preferences TEXT,
                schedule_windows TEXT,
                decision_style TEXT,
                preferences TEXT,
                goals TEXT,
                constraints TEXT,
                routines TEXT,
                important_people TEXT,
                important_locations TEXT,
                work_context TEXT,
                long_term_memory TEXT,
                sensitivity_type TEXT,
                priority_tags TEXT,
                conditions TEXT,
                note TEXT,
                consent INTEGER NOT NULL,
                sensitivity TEXT,
                profile_version TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self._ensure_columns()
        self._conn.commit()

    def _ensure_columns(self) -> None:
        rows = self._conn.execute("PRAGMA table_info(health_profiles);").fetchall()
        existing_columns = {row[1] for row in rows}
        optional_columns = {
            "display_name": "TEXT",
            "persona": "TEXT",
            "identity_summary": "TEXT",
            "role": "TEXT",
            "organization": "TEXT",
            "home_base": "TEXT",
            "family_structure": "TEXT",
            "asset_preferences": "TEXT",
            "schedule_windows": "TEXT",
            "decision_style": "TEXT",
            "preferences": "TEXT",
            "goals": "TEXT",
            "constraints": "TEXT",
            "routines": "TEXT",
            "important_people": "TEXT",
            "important_locations": "TEXT",
            "work_context": "TEXT",
            "long_term_memory": "TEXT",
            "sensitivity_type": "TEXT",
            "priority_tags": "TEXT",
            "profile_version": "TEXT",
        }
        for column, column_type in optional_columns.items():
            if column not in existing_columns:
                self._conn.execute(
                    f"ALTER TABLE health_profiles ADD COLUMN {column} {column_type}"
                )

    @staticmethod
    def _dump_json(value: Optional[Any]) -> Optional[str]:
        if value in (None, "", [], {}):
            return None
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _load_json_list(value: Optional[str]) -> List[str]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item).strip() for item in parsed if str(item).strip()]

    @staticmethod
    def _load_json_dict(value: Optional[str]) -> Dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def upsert_profile(
        self,
        *,
        user_id: str,
        display_name: Optional[str] = None,
        identity_summary: Optional[str] = None,
        role: Optional[str] = None,
        organization: Optional[str] = None,
        home_base: Optional[str] = None,
        family_structure: Optional[List[str]] = None,
        asset_preferences: Optional[List[str]] = None,
        schedule_windows: Optional[List[str]] = None,
        decision_style: Optional[str] = None,
        preferences: Optional[List[str]] = None,
        goals: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None,
        routines: Optional[List[str]] = None,
        important_people: Optional[List[str]] = None,
        important_locations: Optional[List[str]] = None,
        work_context: Optional[str] = None,
        long_term_memory: Optional[str] = None,
        conditions: List[str],
        note: Optional[str],
        consent: bool,
        persona: Optional[str] = None,
        sensitivity_type: Optional[str] = None,
        priority_tags: Optional[List[str]] = None,
        sensitivity: Optional[Dict[str, Any]] = None,
        profile_version: str = "v2",
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        payload_conditions = self._dump_json(conditions) or "[]"
        payload_preferences = self._dump_json(preferences)
        payload_goals = self._dump_json(goals)
        payload_constraints = self._dump_json(constraints)
        payload_routines = self._dump_json(routines)
        payload_important_people = self._dump_json(important_people)
        payload_important_locations = self._dump_json(important_locations)
        payload_family_structure = self._dump_json(family_structure)
        payload_asset_preferences = self._dump_json(asset_preferences)
        payload_schedule_windows = self._dump_json(schedule_windows)
        payload_sensitivity = self._dump_json(sensitivity)
        payload_priority_tags = self._dump_json(priority_tags)
        with self._lock:
            existing = self._conn.execute(
                "SELECT created_at FROM health_profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
            created_at = existing[0] if existing else now
            self._conn.execute(
                """
                INSERT INTO health_profiles (
                    user_id,
                    display_name,
                    persona,
                    identity_summary,
                    role,
                    organization,
                    home_base,
                    family_structure,
                    asset_preferences,
                    schedule_windows,
                    decision_style,
                    preferences,
                    goals,
                    constraints,
                    routines,
                    important_people,
                    important_locations,
                    work_context,
                    long_term_memory,
                    sensitivity_type,
                    priority_tags,
                    conditions,
                    note,
                    consent,
                    sensitivity,
                    profile_version,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    persona=excluded.persona,
                    identity_summary=excluded.identity_summary,
                    role=excluded.role,
                    organization=excluded.organization,
                    home_base=excluded.home_base,
                    family_structure=excluded.family_structure,
                    asset_preferences=excluded.asset_preferences,
                    schedule_windows=excluded.schedule_windows,
                    decision_style=excluded.decision_style,
                    preferences=excluded.preferences,
                    goals=excluded.goals,
                    constraints=excluded.constraints,
                    routines=excluded.routines,
                    important_people=excluded.important_people,
                    important_locations=excluded.important_locations,
                    work_context=excluded.work_context,
                    long_term_memory=excluded.long_term_memory,
                    sensitivity_type=excluded.sensitivity_type,
                    priority_tags=excluded.priority_tags,
                    conditions=excluded.conditions,
                    note=excluded.note,
                    consent=excluded.consent,
                    sensitivity=excluded.sensitivity,
                    profile_version=excluded.profile_version,
                    updated_at=excluded.updated_at
                """,
                (
                    user_id,
                    display_name,
                    persona,
                    identity_summary,
                    role,
                    organization,
                    home_base,
                    payload_family_structure,
                    payload_asset_preferences,
                    payload_schedule_windows,
                    decision_style,
                    payload_preferences,
                    payload_goals,
                    payload_constraints,
                    payload_routines,
                    payload_important_people,
                    payload_important_locations,
                    work_context,
                    long_term_memory,
                    sensitivity_type,
                    payload_priority_tags,
                    payload_conditions,
                    note,
                    1 if consent else 0,
                    payload_sensitivity,
                    profile_version,
                    created_at,
                    now,
                ),
            )
            self._conn.commit()
        profile = self.get_profile(user_id)
        if not profile:
            raise RuntimeError(f"failed to load profile after upsert: {user_id}")
        return profile

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    user_id,
                    display_name,
                    persona,
                    identity_summary,
                    role,
                    organization,
                    home_base,
                    family_structure,
                    asset_preferences,
                    schedule_windows,
                    decision_style,
                    preferences,
                    goals,
                    constraints,
                    routines,
                    important_people,
                    important_locations,
                    work_context,
                    long_term_memory,
                    sensitivity_type,
                    priority_tags,
                    conditions,
                    note,
                    consent,
                    sensitivity,
                    profile_version,
                    created_at,
                    updated_at
                FROM health_profiles
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "user_id": row[0],
            "display_name": row[1],
            "persona": row[2],
            "identity_summary": row[3],
            "role": row[4],
            "organization": row[5],
            "home_base": row[6],
            "family_structure": self._load_json_list(row[7]),
            "asset_preferences": self._load_json_list(row[8]),
            "schedule_windows": self._load_json_list(row[9]),
            "decision_style": row[10],
            "preferences": self._load_json_list(row[11]),
            "goals": self._load_json_list(row[12]),
            "constraints": self._load_json_list(row[13]),
            "routines": self._load_json_list(row[14]),
            "important_people": self._load_json_list(row[15]),
            "important_locations": self._load_json_list(row[16]),
            "work_context": row[17],
            "long_term_memory": row[18],
            "sensitivity_type": row[19],
            "priority_tags": self._load_json_list(row[20]),
            "conditions": self._load_json_list(row[21]),
            "note": row[22],
            "consent": bool(row[23]),
            "sensitivity": self._load_json_dict(row[24]),
            "profile_version": row[25] or "v2",
            "created_at": row[26],
            "updated_at": row[27],
            "source": "sqlite",
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
