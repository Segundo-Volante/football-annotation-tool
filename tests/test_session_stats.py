"""Tests for SessionStats — real-time annotation statistics."""

import time
import pytest

from backend.session_stats import SessionStats


class TestSessionStats:
    def test_initial_state(self):
        stats = SessionStats(total_frames=100)
        assert stats.annotated_count == 0
        assert stats.skipped_count == 0
        assert stats.total_frames == 100

    def test_finish_frame_annotated(self):
        stats = SessionStats(total_frames=10)
        stats.start_session()
        stats.start_frame()
        stats.finish_frame(was_annotated=True)
        assert stats.annotated_count == 1
        assert stats.processed_count == 1

    def test_finish_frame_skipped(self):
        stats = SessionStats(total_frames=10)
        stats.start_session()
        stats.start_frame()
        stats.finish_frame(was_annotated=False)
        assert stats.skipped_count == 1
        assert stats.processed_count == 1

    def test_completion_percent(self):
        stats = SessionStats(total_frames=10)
        stats.update_counts(annotated=3, skipped=2, total=10)
        assert stats.completion_percent == 50.0

    def test_avg_seconds_per_frame(self):
        stats = SessionStats(total_frames=10)
        stats.start_session()
        # Simulate quick frames
        for _ in range(3):
            stats.start_frame()
            time.sleep(0.01)
            stats.finish_frame(True)
        assert stats.avg_seconds_per_frame > 0

    def test_frames_per_minute(self):
        stats = SessionStats(total_frames=10)
        stats.start_session()
        stats.start_frame()
        time.sleep(0.01)
        stats.finish_frame(True)
        assert stats.frames_per_minute > 0

    def test_eta_formatted_no_data(self):
        stats = SessionStats(total_frames=10)
        assert stats.eta_formatted == "—"

    def test_elapsed_formatted(self):
        stats = SessionStats(total_frames=10)
        stats.start_session()
        assert stats.elapsed_formatted  # should be "0:00" or similar

    def test_today_count(self):
        stats = SessionStats(total_frames=10)
        stats.start_session()
        stats.start_frame()
        stats.finish_frame(True)
        assert stats.today_count == 1

    def test_get_summary(self):
        stats = SessionStats(total_frames=10)
        stats.start_session()
        stats.start_frame()
        stats.finish_frame(True)

        summary = stats.get_summary()
        assert "annotated" in summary
        assert "skipped" in summary
        assert "processed" in summary
        assert "eta" in summary
        assert "elapsed" in summary

    def test_update_counts(self):
        stats = SessionStats(total_frames=50)
        stats.update_counts(annotated=10, skipped=5, total=50)
        assert stats.annotated_count == 10
        assert stats.skipped_count == 5
        assert stats.total_frames == 50
