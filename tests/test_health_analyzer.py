"""Tests for HealthAnalyzer — dataset quality analysis."""

import json
import pytest

from backend.annotation_store import AnnotationStore
from backend.health_analyzer import HealthAnalyzer
from backend.models import Category, FrameStatus


@pytest.fixture
def store(tmp_path):
    return AnnotationStore(tmp_path)


@pytest.fixture
def populated_store(store):
    """Store with a few annotated frames and boxes."""
    # Frame with boxes
    store.ensure_frame("a.png")
    store.set_frame_status("a.png", FrameStatus.ANNOTATED)
    store.set_frame_dimensions("a.png", 1920, 1080)
    store.add_box("a.png", 10, 20, 50, 60, Category.HOME_PLAYER,
                   jersey_number=7, player_name="Jason")
    store.add_box("a.png", 100, 200, 30, 40, Category.BALL)

    # Frame with duplicate jerseys
    store.ensure_frame("b.png")
    store.set_frame_status("b.png", FrameStatus.ANNOTATED)
    store.set_frame_dimensions("b.png", 1920, 1080)
    store.add_box("b.png", 10, 20, 50, 60, Category.HOME_PLAYER,
                   jersey_number=7, player_name="Jason")
    store.add_box("b.png", 200, 300, 50, 60, Category.HOME_PLAYER,
                   jersey_number=7, player_name="John Doe")

    # Empty annotated frame (issue)
    store.ensure_frame("c.png")
    store.set_frame_status("c.png", FrameStatus.ANNOTATED)

    # Frame with tiny box
    store.ensure_frame("d.png")
    store.set_frame_status("d.png", FrameStatus.IN_PROGRESS)
    store.set_frame_dimensions("d.png", 1920, 1080)
    store.add_box("d.png", 10, 20, 5, 5, Category.BALL)

    return store


class TestHealthAnalyzer:
    def test_run_full_analysis(self, populated_store):
        analyzer = HealthAnalyzer(populated_store)
        report = analyzer.run_full_analysis()

        assert "frame_stats" in report
        assert "box_stats" in report
        assert "category_distribution" in report
        assert "issues" in report

    def test_frame_stats(self, populated_store):
        analyzer = HealthAnalyzer(populated_store)
        report = analyzer.run_full_analysis()

        fs = report["frame_stats"]
        assert fs["total_frames"] == 4
        assert fs["total_boxes"] == 5

    def test_category_distribution(self, populated_store):
        analyzer = HealthAnalyzer(populated_store)
        report = analyzer.run_full_analysis()

        dist = report["category_distribution"]
        assert "home_player" in dist
        assert "ball" in dist

    def test_detect_empty_annotated(self, populated_store):
        analyzer = HealthAnalyzer(populated_store)
        report = analyzer.run_full_analysis()

        empty_issues = [i for i in report["issues"]
                         if i["type"] == "empty_annotated"]
        assert len(empty_issues) == 1
        assert empty_issues[0]["frame"] == "c.png"

    def test_detect_tiny_boxes(self, populated_store):
        analyzer = HealthAnalyzer(populated_store)
        report = analyzer.run_full_analysis()

        tiny_issues = [i for i in report["issues"]
                        if i["type"] == "tiny_box"]
        assert len(tiny_issues) == 1
        assert tiny_issues[0]["frame"] == "d.png"

    def test_detect_duplicate_jersey(self, populated_store):
        analyzer = HealthAnalyzer(populated_store)
        report = analyzer.run_full_analysis()

        dupe_issues = [i for i in report["issues"]
                        if i["type"] == "duplicate_jersey"]
        assert len(dupe_issues) == 1
        assert dupe_issues[0]["frame"] == "b.png"

    def test_jersey_distribution(self, populated_store):
        analyzer = HealthAnalyzer(populated_store)
        report = analyzer.run_full_analysis()

        jersey_dist = report["jersey_distribution"]
        assert len(jersey_dist) > 0

    def test_issue_summary(self, populated_store):
        analyzer = HealthAnalyzer(populated_store)
        summary = analyzer.get_issue_summary()
        assert summary["total_issues"] > 0
        assert "by_type" in summary
