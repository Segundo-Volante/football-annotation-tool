"""Lightweight SQLite for LOCAL-ONLY state — UI state, session info, export history.

This database is never shared between collaborators.  Each person has their own
``local_state.db``.  All annotation data lives in per-frame JSON files managed
by :class:`AnnotationStore`.
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional


STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_path TEXT NOT NULL,
    session_name TEXT,
    source TEXT NOT NULL,
    match_round TEXT NOT NULL,
    opponent TEXT,
    weather TEXT NOT NULL DEFAULT 'clear',
    lighting TEXT NOT NULL DEFAULT 'floodlight',
    opponent_roster_path TEXT,
    annotation_mode TEXT DEFAULT 'manual',
    model_name TEXT,
    model_confidence REAL DEFAULT 0.30,
    venue TEXT DEFAULT 'home',
    workflow TEXT DEFAULT 'solo',
    annotator TEXT,
    assigned_frames TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_opened TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ui_state (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id),
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    frame_filename TEXT,
    exported_name TEXT,
    output_path TEXT,
    format TEXT DEFAULT 'coco'
);

CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    backup_path TEXT,
    frame_count INTEGER
);
"""


class StateDB:
    """Local-only SQLite storing session info, UI state, export/backup history."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(STATE_SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        """Add columns that may not exist in older databases."""
        existing = {r[1] for r in self.conn.execute("PRAGMA table_info(sessions)").fetchall()}
        for col, default in [
            ("workflow", "'solo'"),
            ("annotator", "NULL"),
            ("assigned_frames", "NULL"),
            ("annotation_mode", "'manual'"),
            ("model_name", "NULL"),
            ("model_confidence", "0.30"),
            ("venue", "'home'"),
        ]:
            if col not in existing:
                self.conn.execute(
                    f"ALTER TABLE sessions ADD COLUMN {col} TEXT DEFAULT {default}"
                )
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ── Session operations ──

    def create_session(self, folder_path: str, source: str, match_round: str,
                       opponent: str = "", weather: str = "clear",
                       lighting: str = "floodlight",
                       opponent_roster_path: str = "",
                       annotation_mode: str = "manual",
                       model_name: str = "",
                       model_confidence: float = 0.30,
                       venue: str = "home",
                       workflow: str = "solo",
                       annotator: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions (folder_path, source, match_round, opponent, "
            "weather, lighting, opponent_roster_path, annotation_mode, "
            "model_name, model_confidence, venue, workflow, annotator, last_opened) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (folder_path, source, match_round, opponent, weather, lighting,
             opponent_roster_path or None, annotation_mode,
             model_name or None, model_confidence, venue, workflow, annotator or None),
        )
        self.conn.commit()
        return cur.lastrowid

    def find_session_by_folder(self, folder_path: str) -> Optional[int]:
        row = self.conn.execute(
            "SELECT id FROM sessions WHERE folder_path = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (folder_path,),
        ).fetchone()
        return row["id"] if row else None

    def get_session(self, session_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE sessions SET last_opened = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )
            self.conn.commit()
            return dict(row)
        return None

    def get_session_mode(self, session_id: int) -> str:
        row = self.conn.execute(
            "SELECT annotation_mode FROM sessions WHERE id = ?", (session_id,),
        ).fetchone()
        return row["annotation_mode"] if row and row["annotation_mode"] else "manual"

    # ── UI State ──

    def save_ui_state(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO ui_state (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def get_ui_state(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM ui_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def save_clean_exit(self, clean: bool) -> None:
        self.save_ui_state("clean_exit", "1" if clean else "0")

    def was_clean_exit(self) -> bool:
        return self.get_ui_state("clean_exit", "1") == "1"

    # ── Export History ──

    def record_export(self, session_id: int, frame_filename: str,
                      exported_name: str, output_path: str = "",
                      fmt: str = "coco") -> None:
        self.conn.execute(
            "INSERT INTO exports (session_id, frame_filename, exported_name, "
            "output_path, format) VALUES (?, ?, ?, ?, ?)",
            (session_id, frame_filename, exported_name, output_path, fmt),
        )
        self.conn.commit()

    def get_export_history(self, session_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM exports WHERE session_id = ? ORDER BY exported_at",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Backup History ──

    def record_backup(self, backup_path: str, frame_count: int) -> None:
        self.conn.execute(
            "INSERT INTO backups (backup_path, frame_count) VALUES (?, ?)",
            (backup_path, frame_count),
        )
        self.conn.commit()

    def get_latest_backup(self) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM backups ORDER BY backup_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
