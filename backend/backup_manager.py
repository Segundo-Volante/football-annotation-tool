"""Auto-backup system for annotation data.

Periodically zips the ``annotations/`` folder and stores timestamped
backups in ``backups/``.  Keeps the most recent *max_backups* archives
and prunes older ones automatically.
"""

import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_MINUTES = 5
DEFAULT_FRAME_INTERVAL = 50
DEFAULT_MAX_BACKUPS = 10


class BackupManager:
    """Creates and manages automatic annotation backups.

    Triggers a backup after a time interval *or* after a certain number of
    frame-level changes, whichever comes first.
    """

    def __init__(
        self,
        project_root: str | Path,
        interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
        frame_interval: int = DEFAULT_FRAME_INTERVAL,
        max_backups: int = DEFAULT_MAX_BACKUPS,
    ):
        self.project_root = Path(project_root)
        self.annotations_dir = self.project_root / "annotations"
        self.backups_dir = self.project_root / "backups"
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        self.interval_minutes = interval_minutes
        self.frame_interval = frame_interval
        self.max_backups = max_backups

        self._frames_since_backup = 0
        self._last_backup_time: Optional[datetime] = None

    def notify_frame_saved(self) -> Optional[str]:
        """Notify the manager that a frame was saved.

        Returns the backup path if a backup was triggered, else None.
        """
        self._frames_since_backup += 1
        if self._frames_since_backup >= self.frame_interval:
            return self.create_backup(reason="frame_count")
        return None

    def check_time_trigger(self) -> Optional[str]:
        """Check whether enough time has elapsed for a periodic backup.

        Call this on a QTimer (e.g. every 60 s).  Returns the backup path
        if a backup was triggered.
        """
        now = datetime.now()
        if self._last_backup_time is None:
            self._last_backup_time = now
            return None
        elapsed = (now - self._last_backup_time).total_seconds() / 60
        if elapsed >= self.interval_minutes:
            return self.create_backup(reason="timer")
        return None

    def create_backup(self, reason: str = "manual") -> Optional[str]:
        """Create a zip backup of the ``annotations/`` folder.

        Returns the path to the new zip, or None if nothing to back up.
        """
        if not self.annotations_dir.exists():
            return None

        json_files = list(self.annotations_dir.glob("*.json"))
        if not json_files:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"annotations_backup_{timestamp}.zip"
        zip_path = self.backups_dir / zip_name

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for jf in json_files:
                    zf.write(jf, jf.name)

            self._frames_since_backup = 0
            self._last_backup_time = datetime.now()
            self._prune_old_backups()

            logger.info("Backup created (%s): %s — %d files",
                        reason, zip_path, len(json_files))
            return str(zip_path)

        except Exception as e:
            logger.error("Backup failed: %s", e, exc_info=True)
            return None

    def restore_backup(self, zip_path: str | Path) -> int:
        """Restore annotations from a backup zip.

        Returns the number of files restored.
        """
        zip_path = Path(zip_path)
        if not zip_path.exists():
            raise FileNotFoundError(f"Backup not found: {zip_path}")

        self.annotations_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".json"):
                    zf.extract(name, self.annotations_dir)
                    count += 1
        logger.info("Restored %d files from %s", count, zip_path)
        return count

    def get_backups(self) -> list[dict]:
        """Return a list of available backups, newest first."""
        backups = []
        for p in sorted(self.backups_dir.glob("annotations_backup_*.zip"), reverse=True):
            stat = p.stat()
            try:
                with zipfile.ZipFile(p, "r") as zf:
                    file_count = len([n for n in zf.namelist() if n.endswith(".json")])
            except Exception:
                file_count = 0
            backups.append({
                "path": str(p),
                "filename": p.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "file_count": file_count,
            })
        return backups

    def _prune_old_backups(self):
        """Delete oldest backups beyond max_backups."""
        backups = sorted(
            self.backups_dir.glob("annotations_backup_*.zip"),
            key=lambda p: p.stat().st_mtime,
        )
        while len(backups) > self.max_backups:
            oldest = backups.pop(0)
            try:
                oldest.unlink()
                logger.info("Pruned old backup: %s", oldest.name)
            except Exception as e:
                logger.warning("Could not prune backup %s: %s", oldest.name, e)

    @property
    def frames_since_backup(self) -> int:
        return self._frames_since_backup
