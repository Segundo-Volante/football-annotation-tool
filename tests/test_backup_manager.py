"""Tests for BackupManager — auto-backup system."""

import json
import pytest

from backend.backup_manager import BackupManager


@pytest.fixture
def setup(tmp_path):
    """Create project structure with some annotation files."""
    annotations_dir = tmp_path / "annotations"
    annotations_dir.mkdir()

    # Create some fake annotation JSON files
    for i in range(5):
        data = {"frame_filename": f"frame_{i:03d}.png", "status": "annotated", "boxes": []}
        (annotations_dir / f"frame_{i:03d}.json").write_text(json.dumps(data))

    return tmp_path


class TestBackupManager:
    def test_create_backup(self, setup):
        mgr = BackupManager(setup)
        result = mgr.create_backup()
        assert result is not None
        assert "annotations_backup_" in result
        assert result.endswith(".zip")

    def test_backup_creates_zip(self, setup):
        mgr = BackupManager(setup)
        result = mgr.create_backup()
        from pathlib import Path
        assert Path(result).exists()

    def test_get_backups(self, setup):
        mgr = BackupManager(setup)
        mgr.create_backup()
        backups = mgr.get_backups()
        assert len(backups) == 1
        assert backups[0]["file_count"] == 5

    def test_frame_count_trigger(self, setup):
        mgr = BackupManager(setup, frame_interval=3)
        # First 2 saves should not trigger
        assert mgr.notify_frame_saved() is None
        assert mgr.notify_frame_saved() is None
        # Third should trigger
        result = mgr.notify_frame_saved()
        assert result is not None

    def test_prune_old_backups(self, setup):
        mgr = BackupManager(setup, max_backups=2)
        mgr.create_backup()
        mgr.create_backup()
        mgr.create_backup()
        backups = mgr.get_backups()
        assert len(backups) <= 2

    def test_no_annotations_no_backup(self, tmp_path):
        mgr = BackupManager(tmp_path)
        result = mgr.create_backup()
        assert result is None

    def test_restore_backup(self, setup):
        mgr = BackupManager(setup)
        zip_path = mgr.create_backup()

        # Delete annotations
        import shutil
        shutil.rmtree(setup / "annotations")
        (setup / "annotations").mkdir()

        count = mgr.restore_backup(zip_path)
        assert count == 5
