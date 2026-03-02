"""Real-time session statistics for the annotation workflow.

Tracks annotation speed, estimates remaining time, and maintains
rolling averages for display in the stats bar.
"""

import time
from collections import deque
from datetime import datetime
from typing import Optional


class SessionStats:
    """Track annotation timing, speed, and ETA in real-time."""

    def __init__(self, total_frames: int = 0):
        self.total_frames = total_frames
        self._start_time: Optional[float] = None
        self._frame_times: deque = deque(maxlen=50)  # last 50 frame durations
        self._frame_start: Optional[float] = None
        self._annotated_count = 0
        self._skipped_count = 0
        self._session_start: Optional[datetime] = None
        self._daily_counts: dict[str, int] = {}  # date -> count

    def start_session(self):
        """Mark the start of the annotation session."""
        self._start_time = time.time()
        self._session_start = datetime.now()

    def start_frame(self):
        """Mark the start of annotating a frame."""
        self._frame_start = time.time()

    def finish_frame(self, was_annotated: bool = True):
        """Mark the completion of a frame annotation.

        Args:
            was_annotated: True if annotated, False if skipped.
        """
        if self._frame_start is not None:
            duration = time.time() - self._frame_start
            self._frame_times.append(duration)
            self._frame_start = None

        if was_annotated:
            self._annotated_count += 1
        else:
            self._skipped_count += 1

        # Track daily count
        today = datetime.now().strftime("%Y-%m-%d")
        self._daily_counts[today] = self._daily_counts.get(today, 0) + 1

    @property
    def avg_seconds_per_frame(self) -> float:
        """Rolling average seconds per frame (last 50 frames)."""
        if not self._frame_times:
            return 0.0
        return sum(self._frame_times) / len(self._frame_times)

    @property
    def frames_per_minute(self) -> float:
        """Current annotation speed in frames per minute."""
        avg = self.avg_seconds_per_frame
        if avg <= 0:
            return 0.0
        return 60.0 / avg

    @property
    def eta_seconds(self) -> float:
        """Estimated time remaining in seconds."""
        remaining = self.total_frames - self._annotated_count - self._skipped_count
        if remaining <= 0:
            return 0.0
        avg = self.avg_seconds_per_frame
        if avg <= 0:
            return 0.0
        return remaining * avg

    @property
    def eta_formatted(self) -> str:
        """Human-readable ETA string."""
        secs = self.eta_seconds
        if secs <= 0:
            return "—"
        if secs < 60:
            return f"{secs:.0f}s"
        if secs < 3600:
            return f"{secs / 60:.0f}m"
        hours = int(secs // 3600)
        mins = int((secs % 3600) // 60)
        return f"{hours}h {mins}m"

    @property
    def elapsed_formatted(self) -> str:
        """Elapsed session time as human-readable string."""
        if self._start_time is None:
            return "0:00"
        elapsed = time.time() - self._start_time
        hours = int(elapsed // 3600)
        mins = int((elapsed % 3600) // 60)
        secs = int(elapsed % 60)
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"

    @property
    def annotated_count(self) -> int:
        return self._annotated_count

    @property
    def skipped_count(self) -> int:
        return self._skipped_count

    @property
    def processed_count(self) -> int:
        return self._annotated_count + self._skipped_count

    @property
    def completion_percent(self) -> float:
        if self.total_frames <= 0:
            return 0.0
        return (self.processed_count / self.total_frames) * 100

    @property
    def today_count(self) -> int:
        """Number of frames processed today."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self._daily_counts.get(today, 0)

    def get_summary(self) -> dict:
        """Return a summary dict for display."""
        return {
            "annotated": self._annotated_count,
            "skipped": self._skipped_count,
            "processed": self.processed_count,
            "total": self.total_frames,
            "completion_percent": round(self.completion_percent, 1),
            "avg_seconds": round(self.avg_seconds_per_frame, 1),
            "frames_per_minute": round(self.frames_per_minute, 1),
            "eta": self.eta_formatted,
            "elapsed": self.elapsed_formatted,
            "today_count": self.today_count,
        }

    def update_counts(self, annotated: int, skipped: int, total: int):
        """Sync counts from external source (e.g. store stats)."""
        self._annotated_count = annotated
        self._skipped_count = skipped
        self.total_frames = total
