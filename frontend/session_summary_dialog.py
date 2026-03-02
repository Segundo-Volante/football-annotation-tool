"""Session Summary dialog — shown on completion or via menu.

Displays final session statistics including timing, annotation counts,
and category breakdown.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget,
)

from backend.i18n import t
from backend.session_stats import SessionStats


class SessionSummaryDialog(QDialog):
    """Session completion summary with detailed statistics."""

    def __init__(self, stats: SessionStats, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("summary.title"))
        self.setFixedSize(450, 380)
        self.setStyleSheet("""
            QDialog { background: #1E1E1E; }
            QLabel { color: #EEE; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Title
        title = QLabel(t("summary.title"))
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #4A90D9;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Completion badge
        s = stats.get_summary()
        pct = s["completion_percent"]
        badge_color = "#8AD98A" if pct >= 100 else "#D9C84A" if pct >= 50 else "#D94A4A"
        badge = QLabel(f"{pct}%")
        badge.setStyleSheet(
            f"font-size: 48px; font-weight: bold; color: {badge_color};"
        )
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(badge)

        # Stats grid
        grid = QWidget()
        grid.setStyleSheet("background: #2A2A2A; border-radius: 8px;")
        grid_layout = QVBoxLayout(grid)
        grid_layout.setContentsMargins(16, 12, 16, 12)
        grid_layout.setSpacing(6)

        stats_items = [
            (t("summary.annotated"), str(s["annotated"]), "#4A90D9"),
            (t("summary.skipped"), str(s["skipped"]), "#D94A4A"),
            (t("summary.total_frames"), str(s["total"]), "#EEE"),
            (t("summary.elapsed_time"), s["elapsed"], "#AAA"),
            (t("summary.avg_speed"),
             f"{s['avg_seconds']}s/frame ({s['frames_per_minute']} fpm)", "#8AD98A"),
            (t("summary.today_count"), str(s["today_count"]), "#D9C84A"),
        ]

        for label, value, color in stats_items:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #888; font-size: 12px;")
            row.addWidget(lbl)
            row.addStretch()
            val = QLabel(value)
            val.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
            row.addWidget(val)
            grid_layout.addLayout(row)

        layout.addWidget(grid)
        layout.addStretch()

        # Close button
        close_btn = QPushButton(t("button.confirm"))
        close_btn.setStyleSheet(
            "QPushButton { background: #4A90D9; color: white; padding: 10px 30px;"
            " border-radius: 6px; font-weight: bold; font-size: 14px; }"
            "QPushButton:hover { background: #5AA0E9; }"
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
