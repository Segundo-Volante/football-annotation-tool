"""One-time migration from SQLite-only storage to per-frame JSON architecture.

If a project has an ``annotations.db`` but no ``annotations/`` folder, this
module converts every frame's data into individual JSON files, then renames
the old database to ``annotations.db.backup``.
"""

import logging
import os
from pathlib import Path
from typing import Callable, Optional

from backend.annotation_store import AnnotationStore
from backend.database import DatabaseManager

logger = logging.getLogger(__name__)


class MigrationTool:
    """Reads all frames and boxes from an existing SQLite ``annotations.db``
    and writes per-frame JSON files via :class:`AnnotationStore`."""

    def __init__(self, db_path: str | Path, project_root: str | Path):
        self.db_path = Path(db_path)
        self.project_root = Path(project_root)

    def needs_migration(self) -> bool:
        """Return True if old DB exists but annotations/ folder has no JSON files."""
        if not self.db_path.exists():
            return False
        annotations_dir = self.project_root / "annotations"
        if annotations_dir.exists() and any(annotations_dir.glob("*.json")):
            return False
        return True

    def migrate(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> dict:
        """Run the migration.

        Args:
            progress_callback: Optional ``(current, total)`` callback.

        Returns:
            ``{frames_migrated, boxes_migrated, errors}``
        """
        db = DatabaseManager(self.db_path)
        store = AnnotationStore(self.project_root)

        # Find the most recent session
        row = db.conn.execute(
            "SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            db.close()
            return {"frames_migrated": 0, "boxes_migrated": 0, "errors": []}

        session_id = row["id"]
        session = db.get_session(session_id)

        # Session-level metadata to embed in each JSON
        session_meta = {
            "source": session.get("source", "") if session else "",
            "match_round": session.get("match_round", "") if session else "",
            "opponent": session.get("opponent", "") if session else "",
            "weather": session.get("weather", "clear") if session else "clear",
            "lighting": session.get("lighting", "floodlight") if session else "floodlight",
        }

        frames = db.get_session_frames(session_id)
        total = len(frames)
        frames_migrated = 0
        boxes_migrated = 0
        errors = []

        for i, f_dict in enumerate(frames):
            frame_id = f_dict["id"]
            filename = f_dict["original_filename"]
            try:
                frame = db.get_frame(frame_id)
                if frame is None:
                    continue

                # Ensure session_metadata is included
                store.ensure_frame(filename, session_meta=session_meta)

                # Update status
                store.set_frame_status(filename, frame.status)

                # Save metadata
                if frame.metadata:
                    store.save_frame_metadata(filename, **frame.metadata)

                # Update session metadata
                store.update_session_metadata(filename, session_meta)

                # Save image dimensions
                if frame.image_width > 0:
                    store.set_frame_dimensions(filename, frame.image_width, frame.image_height)

                # Save exported filename if any
                if frame.exported_filename:
                    store.set_exported_filename(filename, frame.exported_filename)

                # Add boxes
                for box in frame.boxes:
                    store.add_box(
                        filename,
                        box.x, box.y, box.width, box.height,
                        box.category,
                        jersey_number=box.jersey_number,
                        player_name=box.player_name,
                        occlusion=box.occlusion,
                        truncated=box.truncated,
                        source=box.source.value,
                        box_status=box.box_status.value,
                        confidence=box.confidence,
                        detected_class=box.detected_class,
                    )
                    boxes_migrated += 1

                frames_migrated += 1

            except Exception as e:
                logger.error("Migration error for frame %s: %s", filename, e)
                errors.append(f"{filename}: {e}")

            if progress_callback:
                progress_callback(i + 1, total)

        db.close()

        # Rename old DB to backup
        backup_path = self.db_path.with_suffix(".db.backup")
        if backup_path.exists():
            backup_path.unlink()
        os.rename(str(self.db_path), str(backup_path))
        logger.info(
            "Migration complete: %d frames, %d boxes migrated. Old DB renamed to %s",
            frames_migrated, boxes_migrated, backup_path,
        )

        return {
            "frames_migrated": frames_migrated,
            "boxes_migrated": boxes_migrated,
            "errors": errors,
        }

    def verify(self) -> list[str]:
        """Compare SQLite and JSON contents. Return list of discrepancies."""
        discrepancies = []
        if not self.db_path.exists():
            return ["Old database not found (already migrated?)"]

        db = DatabaseManager(self.db_path)
        store = AnnotationStore(self.project_root)

        row = db.conn.execute(
            "SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            db.close()
            return []

        session_id = row["id"]
        frames = db.get_session_frames(session_id)

        for f_dict in frames:
            filename = f_dict["original_filename"]
            db_frame = db.get_frame(f_dict["id"])
            json_frame = store.get_frame_annotation(filename)

            if db_frame and not json_frame:
                discrepancies.append(f"{filename}: missing JSON file")
            elif db_frame and json_frame:
                db_box_count = len(db_frame.boxes)
                json_box_count = len(json_frame.boxes)
                if db_box_count != json_box_count:
                    discrepancies.append(
                        f"{filename}: box count mismatch "
                        f"(DB={db_box_count}, JSON={json_box_count})"
                    )

        db.close()
        return discrepancies
