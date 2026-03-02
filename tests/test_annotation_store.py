"""Tests for AnnotationStore — per-frame JSON storage."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from backend.annotation_store import AnnotationStore
from backend.models import (
    BoundingBox, BoxSource, BoxStatus, Category, FrameAnnotation,
    FrameStatus, Occlusion,
)


@pytest.fixture
def store(tmp_path):
    """Create a fresh AnnotationStore in a temporary directory."""
    return AnnotationStore(tmp_path)


class TestAnnotationStore:
    def test_ensure_frame_creates_json(self, store, tmp_path):
        store.ensure_frame("frame_001.png")
        json_path = tmp_path / "annotations" / "frame_001.json"
        assert json_path.exists()

        data = json.loads(json_path.read_text())
        assert data["frame_filename"] == "frame_001.png"
        assert data["status"] == "unviewed"
        assert data["boxes"] == []

    def test_ensure_frame_with_session_meta(self, store, tmp_path):
        meta = {"source": "TV", "match_round": "R5", "opponent": "Real Madrid"}
        store.ensure_frame("frame_002.png", session_meta=meta)
        data = json.loads(
            (tmp_path / "annotations" / "frame_002.json").read_text()
        )
        assert data["session_metadata"]["source"] == "TV"
        assert data["session_metadata"]["match_round"] == "R5"

    def test_ensure_frame_idempotent(self, store, tmp_path):
        store.ensure_frame("frame_003.png")
        # Add a box and ensure again — should not overwrite
        store.add_box("frame_003.png", 10, 20, 30, 40, Category.BALL)
        store.ensure_frame("frame_003.png")
        boxes = store.get_boxes("frame_003.png")
        assert len(boxes) == 1

    def test_add_box_returns_id(self, store):
        store.ensure_frame("test.png")
        box_id = store.add_box("test.png", 10, 20, 50, 60, Category.HOME_PLAYER)
        assert isinstance(box_id, str)
        assert len(box_id) == 8

    def test_get_boxes(self, store):
        store.ensure_frame("test.png")
        store.add_box("test.png", 10, 20, 50, 60, Category.HOME_PLAYER,
                       jersey_number=7, player_name="Jason")
        store.add_box("test.png", 100, 200, 30, 40, Category.BALL)

        boxes = store.get_boxes("test.png")
        assert len(boxes) == 2
        assert boxes[0].category == Category.HOME_PLAYER
        assert boxes[0].jersey_number == 7
        assert boxes[0].player_name == "Jason"
        assert boxes[1].category == Category.BALL

    def test_update_box(self, store):
        store.ensure_frame("test.png")
        box_id = store.add_box("test.png", 10, 20, 50, 60, Category.OPPONENT)
        store.update_box("test.png", box_id, category=Category.HOME_PLAYER,
                          jersey_number=10, player_name="John Doe")

        boxes = store.get_boxes("test.png")
        assert len(boxes) == 1
        assert boxes[0].category == Category.HOME_PLAYER
        assert boxes[0].jersey_number == 10
        assert boxes[0].player_name == "John Doe"

    def test_delete_box(self, store):
        store.ensure_frame("test.png")
        id1 = store.add_box("test.png", 10, 20, 50, 60, Category.HOME_PLAYER)
        id2 = store.add_box("test.png", 100, 200, 30, 40, Category.BALL)

        store.delete_box("test.png", id1)
        boxes = store.get_boxes("test.png")
        assert len(boxes) == 1
        assert boxes[0].category == Category.BALL

    def test_set_frame_status(self, store):
        store.ensure_frame("test.png")
        store.set_frame_status("test.png", FrameStatus.ANNOTATED)

        frame = store.get_frame_annotation("test.png")
        assert frame.status == FrameStatus.ANNOTATED

    def test_set_frame_status_with_skip(self, store):
        store.ensure_frame("test.png")
        store.set_frame_status("test.png", FrameStatus.SKIPPED, skip_reason="replay")

        frame = store.get_frame_annotation("test.png")
        assert frame.status == FrameStatus.SKIPPED
        assert frame.skip_reason == "replay"

    def test_save_frame_metadata(self, store):
        store.ensure_frame("test.png")
        store.save_frame_metadata("test.png", shot_type="wide", camera_motion="pan")

        frame = store.get_frame_annotation("test.png")
        assert frame.metadata["shot_type"] == "wide"
        assert frame.metadata["camera_motion"] == "pan"

    def test_set_frame_dimensions(self, store):
        store.ensure_frame("test.png")
        store.set_frame_dimensions("test.png", 1920, 1080)

        frame = store.get_frame_annotation("test.png")
        assert frame.image_width == 1920
        assert frame.image_height == 1080

    def test_get_frame_annotation_nonexistent(self, store):
        result = store.get_frame_annotation("nonexistent.png")
        assert result is None

    def test_get_session_stats(self, store):
        store.ensure_frame("a.png")
        store.ensure_frame("b.png")
        store.ensure_frame("c.png")
        store.set_frame_status("a.png", FrameStatus.ANNOTATED)
        store.set_frame_status("b.png", FrameStatus.SKIPPED)

        stats = store.get_session_stats()
        assert stats["total"] == 3
        assert stats["annotated"] == 1
        assert stats["skipped"] == 1
        assert stats["unviewed"] == 1

    def test_get_all_frame_summaries(self, store):
        store.ensure_frame("a.png")
        store.ensure_frame("b.png")
        store.add_box("a.png", 10, 20, 50, 60, Category.BALL)

        summaries = store.get_all_frame_summaries()
        assert len(summaries) == 2

        a_summary = next(s for s in summaries if s["filename"] == "a.png")
        assert a_summary["box_count"] == 1

    def test_ai_box_operations(self, store):
        store.ensure_frame("test.png")
        # Add manual box
        manual_id = store.add_box("test.png", 10, 20, 50, 60, Category.HOME_PLAYER)
        # Add AI pending box
        ai_id = store.add_box("test.png", 100, 200, 30, 40, Category.OPPONENT,
                               source="ai_detected", box_status="pending",
                               confidence=0.85, detected_class="person")

        # Check pending count
        assert store.get_pending_box_count("test.png") == 1

        # Bulk assign
        count = store.bulk_assign_pending("test.png", Category.HOME_PLAYER)
        assert count == 1
        assert store.get_pending_box_count("test.png") == 0

    def test_delete_ai_pending_boxes(self, store):
        store.ensure_frame("test.png")
        store.add_box("test.png", 10, 20, 50, 60, Category.HOME_PLAYER)  # manual
        store.add_box("test.png", 100, 200, 30, 40, Category.OPPONENT,
                       source="ai_detected", box_status="pending")
        store.add_box("test.png", 300, 400, 30, 40, Category.OPPONENT,
                       source="ai_detected", box_status="finalized")

        store.delete_ai_pending_boxes("test.png")
        boxes = store.get_boxes("test.png")
        # Manual + finalized AI should remain
        assert len(boxes) == 2

    def test_get_next_seq(self, store):
        store.ensure_frame("a.png")
        store.ensure_frame("b.png")
        store.set_frame_status("a.png", FrameStatus.ANNOTATED)

        assert store.get_next_seq() == 2  # 1 annotated + 1

    def test_has_annotations(self, store):
        assert not store.has_annotations()
        store.ensure_frame("test.png")
        assert store.has_annotations()

    def test_iter_all_frames(self, store):
        store.ensure_frame("a.png")
        store.ensure_frame("b.png")
        store.add_box("a.png", 10, 20, 50, 60, Category.BALL)

        frames = list(store.iter_all_frames())
        assert len(frames) == 2

    def test_save_frame_annotation(self, store):
        frame = FrameAnnotation(
            id=None, original_filename="test.png",
            image_width=1920, image_height=1080,
            source="TV", match_round="R5", opponent="Rival FC",
            weather="clear", lighting="floodlight",
        )
        frame.boxes = [
            BoundingBox(id="abc123", frame_id=0, x=10, y=20, width=50, height=60,
                        category=Category.HOME_PLAYER, jersey_number=7,
                        player_name="Jason"),
        ]
        store.save_frame_annotation("test.png", frame)

        loaded = store.get_frame_annotation("test.png")
        assert loaded.image_width == 1920
        assert loaded.source == "TV"
        assert len(loaded.boxes) == 1
        assert loaded.boxes[0].player_name == "Jason"
