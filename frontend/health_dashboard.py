"""Dataset Health Dashboard dialog.

Provides a comprehensive view of annotation quality, distribution
statistics, and detected issues across the entire dataset.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QWidget, QScrollArea, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView,
)

from backend.health_analyzer import HealthAnalyzer
from backend.i18n import t

# ── Design tokens (unified with project palette) ──
_BG = "#1E1E2E"
_CARD = "#2A2A3C"
_ELEVATED = "#33334C"
_BORDER = "#404060"
_ACCENT = "#F5A623"
_ACCENT_HOVER = "#FFB833"
_TEXT = "#E8E8F0"
_MUTED = "#8888A0"
_SUCCESS = "#43A047"
_ERROR = "#D9534F"

_DIALOG_STYLE = f"""
    QDialog {{ background: {_BG}; }}
    QLabel {{ color: {_TEXT}; font-size: 12px; }}
    QTabWidget::pane {{
        border: 1px solid {_BORDER}; background: {_CARD};
        border-radius: 4px;
    }}
    QTabBar::tab {{
        background: {_ELEVATED}; color: {_MUTED};
        padding: 8px 20px; border-top-left-radius: 4px;
        border-top-right-radius: 4px; margin-right: 2px;
        font-size: 12px;
    }}
    QTabBar::tab:selected {{
        background: {_ACCENT}; color: {_BG}; font-weight: bold;
    }}
    QTabBar::tab:hover:!selected {{ background: #404060; color: {_TEXT}; }}
    QTableWidget {{
        background: {_CARD}; color: {_TEXT};
        gridline-color: {_BORDER}; border: 1px solid {_BORDER};
        border-radius: 4px; font-size: 12px;
    }}
    QTableWidget::item {{ padding: 6px 8px; }}
    QTableWidget::item:selected {{ background: #3A3A5C; }}
    QHeaderView::section {{
        background: {_ELEVATED}; color: {_MUTED}; padding: 6px 8px;
        border: none; border-right: 1px solid {_BORDER};
        font-size: 11px; font-weight: bold;
    }}
    QScrollArea {{ border: none; background: transparent; }}
"""


class HealthDashboard(QDialog):
    """Health dashboard showing annotation statistics and issues."""

    def __init__(self, analyzer: HealthAnalyzer, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("health.title"))
        self.setMinimumSize(750, 540)
        self.resize(850, 640)
        self.setStyleSheet(_DIALOG_STYLE)

        self._report = analyzer.run_full_analysis()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # ── Title ──
        title = QLabel(t("health.title"))
        title.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {_ACCENT};"
        )
        layout.addWidget(title)

        subtitle = QLabel("Annotation quality overview and detected issues")
        subtitle.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
        layout.addWidget(subtitle)

        # ── Tab widget ──
        tabs = QTabWidget()
        tabs.addTab(self._build_overview_tab(), t("health.tab_overview"))
        tabs.addTab(self._build_distribution_tab(), t("health.tab_distribution"))
        tabs.addTab(self._build_issues_tab(), t("health.tab_issues"))
        tabs.addTab(self._build_metadata_tab(), t("health.tab_metadata"))
        layout.addWidget(tabs)

        # ── Close button ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(t("button.confirm"))
        close_btn.setStyleSheet(
            f"QPushButton {{ background: {_ACCENT}; color: {_BG}; padding: 10px 28px;"
            f" border-radius: 6px; font-weight: bold; font-size: 13px; border: none; }}"
            f"QPushButton:hover {{ background: {_ACCENT_HOVER}; }}"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # ── Tabs ──────────────────────────────────────────────────────────

    def _build_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        fs = self._report["frame_stats"]
        bs = self._report["box_stats"]

        # Frame statistics
        layout.addWidget(self._section_label(t("health.frame_stats")))
        grid = self._stat_grid([
            (t("health.total_frames"), str(fs["total_frames"])),
            (t("health.annotated"), str(fs.get("by_status", {}).get("annotated", 0))),
            (t("health.skipped"), str(fs.get("by_status", {}).get("skipped", 0))),
            (t("health.in_progress"), str(fs.get("by_status", {}).get("in_progress", 0))),
            (t("health.unviewed"), str(fs.get("by_status", {}).get("unviewed", 0))),
        ])
        layout.addWidget(grid)

        # Box statistics
        layout.addWidget(self._section_label(t("health.box_stats")))
        grid2 = self._stat_grid([
            (t("health.total_boxes"), str(bs["total"])),
            (t("health.manual_boxes"), str(bs["manual"])),
            (t("health.ai_boxes"), str(bs["ai_detected"])),
            (t("health.pending_boxes"), str(bs["pending"])),
            (t("health.avg_per_frame"), str(fs["avg_boxes_per_frame"])),
            (t("health.truncated"), str(bs["truncated"])),
        ])
        layout.addWidget(grid2)

        layout.addStretch()
        return widget

    def _build_distribution_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Category distribution
        layout.addWidget(self._section_label(t("health.category_dist")))
        cat_dist = self._report["category_distribution"]
        if cat_dist:
            table = QTableWidget(len(cat_dist), 2)
            table.setHorizontalHeaderLabels([t("health.category"), t("health.count")])
            table.horizontalHeader().setStretchLastSection(True)
            for row, (cat, count) in enumerate(sorted(cat_dist.items(), key=lambda x: -x[1])):
                table.setItem(row, 0, QTableWidgetItem(cat))
                table.setItem(row, 1, QTableWidgetItem(str(count)))
            table.setMaximumHeight(200)
            layout.addWidget(table)

        # Jersey distribution (top 20)
        layout.addWidget(self._section_label(t("health.jersey_dist")))
        jersey_dist = self._report["jersey_distribution"]
        if jersey_dist:
            items = list(jersey_dist.items())[:20]
            table = QTableWidget(len(items), 2)
            table.setHorizontalHeaderLabels([t("health.player"), t("health.appearances")])
            table.horizontalHeader().setStretchLastSection(True)
            for row, (player, count) in enumerate(items):
                table.setItem(row, 0, QTableWidgetItem(player))
                table.setItem(row, 1, QTableWidgetItem(str(count)))
            layout.addWidget(table)

        layout.addStretch()
        return widget

    def _build_issues_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        issues = self._report["issues"]
        layout.addWidget(self._section_label(
            t("health.issues_found", count=len(issues))
        ))

        if not issues:
            ok_label = QLabel(t("health.no_issues"))
            ok_label.setStyleSheet(
                f"color: {_SUCCESS}; font-size: 14px; font-weight: bold; padding: 24px;"
            )
            ok_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(ok_label)
        else:
            table = QTableWidget(len(issues), 3)
            table.setHorizontalHeaderLabels([
                t("health.severity"), t("health.frame"), t("health.issue"),
            ])
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            for row, issue in enumerate(issues):
                severity_item = QTableWidgetItem(issue["severity"].upper())
                if issue["severity"] == "warning":
                    severity_item.setForeground(Qt.GlobalColor.yellow)
                else:
                    severity_item.setForeground(Qt.GlobalColor.cyan)
                table.setItem(row, 0, severity_item)
                table.setItem(row, 1, QTableWidgetItem(issue["frame"]))
                table.setItem(row, 2, QTableWidgetItem(issue["message"]))
            layout.addWidget(table)

        layout.addStretch()
        return widget

    def _build_metadata_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        mc = self._report["metadata_coverage"]
        layout.addWidget(self._section_label(
            t("health.metadata_coverage_title",
              count=mc.get("annotated_frames", 0))
        ))

        coverage = mc.get("coverage", {})
        if coverage:
            table = QTableWidget(len(coverage), 3)
            table.setHorizontalHeaderLabels([
                t("health.field"), t("health.filled"), t("health.percent"),
            ])
            table.horizontalHeader().setStretchLastSection(True)
            for row, (key, data) in enumerate(coverage.items()):
                table.setItem(row, 0, QTableWidgetItem(key))
                table.setItem(row, 1, QTableWidgetItem(
                    f"{data['filled']} / {data['total']}"
                ))
                pct_item = QTableWidgetItem(f"{data['percent']}%")
                if data["percent"] >= 90:
                    pct_item.setForeground(Qt.GlobalColor.green)
                elif data["percent"] >= 50:
                    pct_item.setForeground(Qt.GlobalColor.yellow)
                else:
                    pct_item.setForeground(Qt.GlobalColor.red)
                table.setItem(row, 2, pct_item)
            layout.addWidget(table)
        else:
            layout.addWidget(QLabel(t("health.no_metadata")))

        layout.addStretch()
        return widget

    # ── Reusable helpers ──────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {_MUTED};"
            " padding: 8px 0 4px 0;"
        )
        return label

    def _stat_grid(self, items: list[tuple[str, str]]) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        for label_text, value_text in items:
            card = QWidget()
            card.setStyleSheet(
                f"background: {_CARD}; border-radius: 8px;"
                f" border: 1px solid {_BORDER};"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            card_layout.setSpacing(4)

            value = QLabel(value_text)
            value.setStyleSheet(
                f"color: {_ACCENT}; font-size: 22px; font-weight: bold;"
                " background: transparent; border: none;"
            )
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(value)

            label = QLabel(label_text)
            label.setStyleSheet(
                f"color: {_MUTED}; font-size: 11px;"
                " background: transparent; border: none;"
            )
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            card_layout.addWidget(label)

            layout.addWidget(card)

        layout.addStretch()
        return widget
