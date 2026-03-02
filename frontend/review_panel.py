"""Quick Review panel — search, filter, and batch-edit annotations.

Accessible from the main window as a dockable panel or dialog.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QSpinBox, QMessageBox,
)

from backend.batch_operations import BatchOperations
from backend.i18n import t
from backend.models import Category, CATEGORY_NAMES, FrameStatus


class ReviewPanel(QDialog):
    """Quick review and batch edit dialog."""

    navigate_to_frame = pyqtSignal(str)  # emits filename to navigate to

    def __init__(self, batch_ops: BatchOperations, parent=None):
        super().__init__(parent)
        self._ops = batch_ops

        self.setWindowTitle(t("review.title"))
        self.setMinimumSize(700, 500)
        self.resize(800, 550)
        self.setStyleSheet("""
            QDialog { background: #1E1E1E; }
            QLabel { color: #EEE; }
            QGroupBox { color: #CCC; border: 1px solid #444; border-radius: 6px;
                        margin-top: 8px; padding-top: 16px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; }
            QLineEdit, QComboBox, QSpinBox { background: #333; color: #EEE;
                border: 1px solid #555; border-radius: 3px; padding: 4px; }
            QTableWidget { background: #2A2A2A; color: #EEE; gridline-color: #444;
                           border: none; }
            QHeaderView::section { background: #333; color: #EEE; padding: 4px;
                                   border: none; border-right: 1px solid #444; }
            QPushButton { background: #333; color: #EEE; padding: 6px 16px;
                          border-radius: 4px; }
            QPushButton:hover { background: #444; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Search section
        search_group = QGroupBox(t("review.search"))
        sg_layout = QHBoxLayout(search_group)

        sg_layout.addWidget(QLabel(t("review.search_by")))
        self._search_type = QComboBox()
        self._search_type.addItems([
            t("review.jersey_number"),
            t("review.player_name"),
            t("review.category"),
            t("review.status"),
            t("review.issues"),
        ])
        sg_layout.addWidget(self._search_type)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(t("review.search_placeholder"))
        sg_layout.addWidget(self._search_input, stretch=1)

        search_btn = QPushButton(t("review.search_btn"))
        search_btn.setStyleSheet(
            "QPushButton { background: #4A90D9; color: white; font-weight: bold; }"
        )
        search_btn.clicked.connect(self._do_search)
        sg_layout.addWidget(search_btn)

        layout.addWidget(search_group)

        # Results table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            t("review.col_frame"), t("review.col_status"),
            t("review.col_boxes"), t("review.col_details"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table, stretch=1)

        # Batch edit section
        edit_group = QGroupBox(t("review.batch_edit"))
        eg_layout = QHBoxLayout(edit_group)

        eg_layout.addWidget(QLabel(t("review.change_jersey")))
        self._old_jersey = QSpinBox()
        self._old_jersey.setRange(0, 99)
        eg_layout.addWidget(self._old_jersey)
        eg_layout.addWidget(QLabel("→"))
        self._new_jersey = QSpinBox()
        self._new_jersey.setRange(0, 99)
        eg_layout.addWidget(self._new_jersey)

        self._new_name = QLineEdit()
        self._new_name.setPlaceholderText(t("review.new_name"))
        self._new_name.setMaximumWidth(150)
        eg_layout.addWidget(self._new_name)

        apply_btn = QPushButton(t("review.apply_change"))
        apply_btn.setStyleSheet(
            "QPushButton { background: #D9C84A; color: #1E1E2E; font-weight: bold; }"
        )
        apply_btn.clicked.connect(self._apply_jersey_change)
        eg_layout.addWidget(apply_btn)

        layout.addWidget(edit_group)

        # Bottom buttons
        btn_layout = QHBoxLayout()

        player_summary_btn = QPushButton(t("review.player_summary"))
        player_summary_btn.clicked.connect(self._show_player_summary)
        btn_layout.addWidget(player_summary_btn)

        btn_layout.addStretch()

        close_btn = QPushButton(t("button.confirm"))
        close_btn.setStyleSheet(
            "QPushButton { background: #4A90D9; color: white; font-weight: bold; }"
        )
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _do_search(self):
        search_type = self._search_type.currentIndex()
        query = self._search_input.text().strip()

        results = []
        if search_type == 0:  # Jersey number
            try:
                jersey = int(query) if query else 0
                results = self._ops.search_by_jersey(jersey)
            except ValueError:
                return
        elif search_type == 1:  # Player name
            if query:
                results = self._ops.search_by_player_name(query)
        elif search_type == 2:  # Category
            # Map query to category
            for cat in Category:
                name = CATEGORY_NAMES.get(cat, "")
                if query.lower() in name.lower():
                    results = self._ops.filter_by_category(cat)
                    break
        elif search_type == 3:  # Status
            for status in FrameStatus:
                if query.lower() in status.value.lower():
                    results = self._ops.filter_by_status(status)
                    break
        elif search_type == 4:  # Issues
            results = self._ops.filter_frames_with_issues()

        self._populate_table(results)

    def _populate_table(self, results: list[dict]):
        self._table.setRowCount(len(results))
        for row, r in enumerate(results):
            self._table.setItem(row, 0, QTableWidgetItem(r.get("filename", "")))
            self._table.setItem(row, 1, QTableWidgetItem(r.get("status", "")))
            self._table.setItem(row, 2, QTableWidgetItem(
                str(r.get("box_count", 0))
            ))
            # Details
            details = ""
            if "player_name" in r and r["player_name"]:
                details = r["player_name"]
            elif "issues" in r:
                details = ", ".join(r["issues"])
            elif "jerseys" in r:
                details = ", ".join(f"#{j}" for j in r["jerseys"])
            self._table.setItem(row, 3, QTableWidgetItem(details))

    def _on_double_click(self, row: int, col: int):
        item = self._table.item(row, 0)
        if item:
            self.navigate_to_frame.emit(item.text())

    def _apply_jersey_change(self):
        old = self._old_jersey.value()
        new = self._new_jersey.value()
        name = self._new_name.text().strip() or None

        if old == new and name is None:
            return

        count = self._ops.bulk_change_jersey(old, new, new_name=name)
        QMessageBox.information(
            self,
            t("review.change_applied"),
            t("review.jerseys_changed", count=count, old=old, new=new),
        )

    def _show_player_summary(self):
        players = self._ops.get_player_summary()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            t("review.col_jersey"), t("review.col_player"),
            t("review.col_category_col"), t("review.col_appearances"),
        ])
        self._table.setRowCount(len(players))
        for row, p in enumerate(players):
            self._table.setItem(row, 0, QTableWidgetItem(f"#{p['jersey']}"))
            self._table.setItem(row, 1, QTableWidgetItem(p["name"]))
            self._table.setItem(row, 2, QTableWidgetItem(p["category"]))
            self._table.setItem(row, 3, QTableWidgetItem(str(p["appearances"])))
