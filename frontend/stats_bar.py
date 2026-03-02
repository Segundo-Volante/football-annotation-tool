"""Real-time statistics bar widget displayed below the progress bar.

Shows annotation speed, ETA, session elapsed time, and today's count.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

from backend.i18n import t
from backend.session_stats import SessionStats


class StatsBar(QWidget):
    """Compact stats bar showing real-time annotation metrics."""

    def __init__(self, stats: SessionStats, parent=None):
        super().__init__(parent)
        self._stats = stats
        self.setFixedHeight(24)
        self.setStyleSheet("background: #2A2A2A; border-top: 1px solid #444;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(16)

        self._speed_label = QLabel()
        self._speed_label.setStyleSheet("color: #8AD98A; font-size: 11px; font-weight: bold;")
        layout.addWidget(self._speed_label)

        self._eta_label = QLabel()
        self._eta_label.setStyleSheet("color: #D9C84A; font-size: 11px;")
        layout.addWidget(self._eta_label)

        self._elapsed_label = QLabel()
        self._elapsed_label.setStyleSheet("color: #AAA; font-size: 11px;")
        layout.addWidget(self._elapsed_label)

        layout.addStretch()

        self._today_label = QLabel()
        self._today_label.setStyleSheet("color: #AAA; font-size: 11px;")
        layout.addWidget(self._today_label)

        # Auto-refresh every second
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1000)

        self.refresh()

    def refresh(self):
        """Update all stat labels from the SessionStats object."""
        s = self._stats.get_summary()

        speed = s["frames_per_minute"]
        if speed > 0:
            self._speed_label.setText(
                t("stats.speed", speed=f"{speed:.1f}",
                  avg=f"{s['avg_seconds']:.1f}")
            )
        else:
            self._speed_label.setText(t("stats.speed_idle"))

        self._eta_label.setText(t("stats.eta", eta=s["eta"]))
        self._elapsed_label.setText(t("stats.elapsed", elapsed=s["elapsed"]))
        self._today_label.setText(t("stats.today", count=s["today_count"]))
