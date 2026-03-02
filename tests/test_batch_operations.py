"""Tests for BatchOperations — search, filter, and batch edit."""

import pytest

from backend.annotation_store import AnnotationStore
from backend.batch_operations import BatchOperations
from backend.models import Category, FrameStatus


@pytest.fixture
def store(tmp_path):
    return AnnotationStore(tmp_path)


@pytest.fixture
def ops(store):
    """Batch operations with populated data."""
    # Frame A: home player #7 Jason
    store.ensure_frame("a.png")
    store.set_frame_status("a.png", FrameStatus.ANNOTATED)
    store.add_box("a.png", 10, 20, 50, 60, Category.HOME_PLAYER,
                   jersey_number=7, player_name="Jason")
    store.add_box("a.png", 100, 200, 30, 40, Category.BALL)

    # Frame B: home player #7 Jason, opponent #10 John Doe
    store.ensure_frame("b.png")
    store.set_frame_status("b.png", FrameStatus.ANNOTATED)
    store.add_box("b.png", 10, 20, 50, 60, Category.HOME_PLAYER,
                   jersey_number=7, player_name="Jason")
    store.add_box("b.png", 200, 300, 50, 60, Category.OPPONENT,
                   jersey_number=10, player_name="John Doe")

    # Frame C: skipped
    store.ensure_frame("c.png")
    store.set_frame_status("c.png", FrameStatus.SKIPPED)

    return BatchOperations(store)


class TestBatchOperations:
    def test_search_by_jersey(self, ops):
        results = ops.search_by_jersey(7)
        assert len(results) == 2
        assert all(r["player_name"] == "Jason" for r in results)

    def test_search_by_jersey_not_found(self, ops):
        results = ops.search_by_jersey(99)
        assert len(results) == 0

    def test_search_by_player_name(self, ops):
        results = ops.search_by_player_name("john")
        assert len(results) == 1
        assert results[0]["filename"] == "b.png"

    def test_filter_by_category(self, ops):
        results = ops.filter_by_category(Category.BALL)
        assert len(results) == 1
        assert results[0]["filename"] == "a.png"

    def test_filter_by_status(self, ops):
        results = ops.filter_by_status(FrameStatus.SKIPPED)
        assert len(results) == 1
        assert results[0]["filename"] == "c.png"

    def test_bulk_change_jersey(self, ops):
        count = ops.bulk_change_jersey(7, 77, new_name="Jack Smith")
        assert count == 2

    def test_get_player_summary(self, ops):
        players = ops.get_player_summary()
        assert len(players) > 0
        jason_entries = [p for p in players if p["name"] == "Jason"]
        assert len(jason_entries) == 1
        assert jason_entries[0]["appearances"] == 2
