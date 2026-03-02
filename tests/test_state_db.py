"""Tests for StateDB — local-only SQLite state storage."""

import pytest

from backend.state_db import StateDB


@pytest.fixture
def db(tmp_path):
    """Create a fresh StateDB in a temporary directory."""
    return StateDB(tmp_path / "local_state.db")


class TestStateDB:
    def test_create_session(self, db):
        sid = db.create_session(
            "/path/to/images", "TV", "R5",
            opponent="Rival FC", weather="rain",
        )
        assert isinstance(sid, int)
        assert sid > 0

    def test_find_session_by_folder(self, db):
        db.create_session("/images", "TV", "R5")
        found = db.find_session_by_folder("/images")
        assert found is not None

    def test_find_session_not_found(self, db):
        found = db.find_session_by_folder("/nonexistent")
        assert found is None

    def test_get_session(self, db):
        sid = db.create_session("/images", "TV", "R5", opponent="FC Test")
        session = db.get_session(sid)
        assert session is not None
        assert session["source"] == "TV"
        assert session["match_round"] == "R5"
        assert session["opponent"] == "FC Test"

    def test_save_and_get_ui_state(self, db):
        db.save_ui_state("last_row", "42")
        assert db.get_ui_state("last_row") == "42"

    def test_get_ui_state_default(self, db):
        assert db.get_ui_state("missing_key", "default") == "default"

    def test_clean_exit(self, db):
        db.save_clean_exit(False)
        assert not db.was_clean_exit()
        db.save_clean_exit(True)
        assert db.was_clean_exit()

    def test_record_export(self, db):
        sid = db.create_session("/images", "TV", "R5")
        db.record_export(sid, "frame_001.png", "TV_R5_0001.png",
                          output_path="/output", fmt="coco")
        history = db.get_export_history(sid)
        assert len(history) == 1
        assert history[0]["frame_filename"] == "frame_001.png"

    def test_record_backup(self, db):
        db.record_backup("/backups/backup_001.zip", 42)
        latest = db.get_latest_backup()
        assert latest is not None
        assert latest["frame_count"] == 42

    def test_session_with_workflow(self, db):
        sid = db.create_session(
            "/images", "TV", "R5",
            workflow="split_merge", annotator="Jason",
        )
        session = db.get_session(sid)
        assert session["workflow"] == "split_merge"
        assert session["annotator"] == "Jason"

    def test_session_with_ai_mode(self, db):
        sid = db.create_session(
            "/images", "TV", "R5",
            annotation_mode="ai_assisted",
            model_name="yolov8n",
            model_confidence=0.45,
        )
        session = db.get_session(sid)
        assert session["annotation_mode"] == "ai_assisted"

    def test_close(self, db):
        db.close()
        # Should not raise
