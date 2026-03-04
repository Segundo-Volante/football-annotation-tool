from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QColor, QIcon, QPainter, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel,
)

from backend.i18n import t
from backend.file_manager import FileManager

STATUS_COLORS = {
    "unviewed": QColor("#E0E0E0"),
    "annotated": QColor("#4A90D9"),
    "skipped": QColor("#D94A4A"),
    "in_progress": QColor("#D9C84A"),
}

THUMB_WIDTH = 100
THUMB_HEIGHT = 56


class Filmstrip(QWidget):
    frame_selected = pyqtSignal(str)  # emits filename (was int DB id)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._count_label = QLabel(t("filmstrip.frame_count", count=0))
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_label.setStyleSheet("color: #CCC; font-weight: bold;")
        layout.addWidget(self._count_label)

        self._list = QListWidget()
        self._list.setIconSize(QSize(THUMB_WIDTH, THUMB_HEIGHT))
        self._list.setSpacing(2)
        self._list.setStyleSheet("""
            QListWidget { background: #2A2A2A; border: none; }
            QListWidget::item { padding: 2px; border-radius: 3px; }
            QListWidget::item:selected { border: 2px solid #FFA500; }
        """)
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        self._filenames: list[str] = []
        self._original_pixmaps: list[QPixmap] = []  # store originals for dot overlay

    def load_frames(self, frames: list[dict], folder_path: str,
                    frame_metadata: dict[str, dict] | None = None):
        self._list.blockSignals(True)
        self._list.clear()
        self._filenames.clear()
        self._original_pixmaps.clear()
        self._frame_metadata = frame_metadata or {}

        import os

        # Track priority groups for section dividers
        current_group = None
        group_counts: dict[int, int] = {}
        if frame_metadata:
            for f in frames:
                g = f.get("priority_group")
                if g is not None:
                    group_counts[g] = group_counts.get(g, 0) + 1

        for f in frames:
            filename = f.get("original_filename") or f.get("filename", "")

            # Insert section divider if priority group changed
            priority_group = f.get("priority_group")
            if frame_metadata and priority_group is not None and priority_group != current_group:
                current_group = priority_group
                label = FileManager.get_priority_group_label(priority_group)
                count = group_counts.get(priority_group, 0)
                divider = QListWidgetItem(f"\u2014 {label} ({count}) \u2014")
                divider.setFlags(Qt.ItemFlag.NoItemFlags)  # not selectable
                divider.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                divider.setForeground(QColor("#8888A0"))
                divider.setBackground(QColor("#1A1A2A"))
                font = QFont()
                font.setPointSize(8)
                font.setItalic(True)
                divider.setFont(font)
                divider.setSizeHint(QSize(THUMB_WIDTH + 20, 18))
                # Mark as divider so we can skip it in lookups
                divider.setData(Qt.ItemDataRole.UserRole, "__divider__")
                self._list.addItem(divider)

            item = QListWidgetItem()
            item.setText(filename)
            item.setForeground(QColor("#EEE"))
            status = f.get("status", "unviewed")
            bg = STATUS_COLORS.get(status, STATUS_COLORS["unviewed"])
            item.setBackground(bg)

            # Build tooltip with video_time if available
            meta = self._frame_metadata.get(filename, {})
            video_time = meta.get("video_time")
            if video_time is not None:
                time_str = FileManager.format_video_time(video_time)
                item.setToolTip(f"{filename} \u2014 {time_str}")
            else:
                item.setToolTip(filename)

            # Store frame data reference on item
            item.setData(Qt.ItemDataRole.UserRole, filename)

            # Load thumbnail
            img_path = os.path.join(folder_path, filename)
            pix = QPixmap(img_path)
            if not pix.isNull():
                pix = pix.scaled(THUMB_WIDTH, THUMB_HEIGHT,
                                 Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
                self._original_pixmaps.append(QPixmap(pix))  # store a copy
                item.setIcon(QIcon(pix))
            else:
                self._original_pixmaps.append(QPixmap())

            item.setSizeHint(QSize(THUMB_WIDTH + 20, THUMB_HEIGHT + 24))
            self._list.addItem(item)
            self._filenames.append(filename)

        self._count_label.setText(t("filmstrip.frame_count", count=len(frames)))
        self._list.blockSignals(False)

    def _frame_row_to_list_row(self, frame_row: int) -> int:
        """Convert a frame index (0-based in self._filenames) to a list widget row,
        accounting for divider items inserted in the list."""
        if frame_row < 0 or frame_row >= len(self._filenames):
            return frame_row
        target_fname = self._filenames[frame_row]
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == target_fname:
                return i
        return frame_row  # fallback

    def _list_row_to_frame_row(self, list_row: int) -> int:
        """Convert a list widget row to a frame index, skipping dividers."""
        item = self._list.item(list_row)
        if not item:
            return -1
        fname = item.data(Qt.ItemDataRole.UserRole)
        if fname == "__divider__" or fname is None:
            return -1
        try:
            return self._filenames.index(fname)
        except ValueError:
            return -1

    def select_row(self, row: int):
        list_row = self._frame_row_to_list_row(row)
        self._list.blockSignals(True)
        self._list.setCurrentRow(list_row)
        self._list.blockSignals(False)
        item = self._list.item(list_row)
        if item:
            self._list.scrollToItem(item)

    def update_status(self, row: int, status: str):
        list_row = self._frame_row_to_list_row(row)
        item = self._list.item(list_row)
        if item:
            bg = STATUS_COLORS.get(status, STATUS_COLORS["unviewed"])
            item.setBackground(bg)

    def update_dot(self, row: int, dot_color: QColor = None):
        """Paint a colored status dot on the thumbnail at the given row."""
        if row < 0 or row >= len(self._original_pixmaps):
            return
        list_row = self._frame_row_to_list_row(row)
        item = self._list.item(list_row)
        if not item:
            return
        orig = self._original_pixmaps[row]
        if orig.isNull():
            return
        pix = QPixmap(orig)  # copy original
        if dot_color:
            p = QPainter(pix)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(dot_color)
            p.setPen(Qt.PenStyle.NoPen)
            dot_size = 10
            p.drawEllipse(pix.width() - dot_size - 3, 3, dot_size, dot_size)
            p.end()
        item.setIcon(QIcon(pix))

    def set_current_highlight(self, row: int):
        # Highlight current row as in-progress (yellow)
        list_row = self._frame_row_to_list_row(row)
        item = self._list.item(list_row)
        if item:
            item.setBackground(STATUS_COLORS["in_progress"])

    def _on_row_changed(self, list_row: int):
        item = self._list.item(list_row)
        if not item:
            return
        fname = item.data(Qt.ItemDataRole.UserRole)
        # Skip divider items — jump to next real frame
        if fname == "__divider__" or fname is None:
            # Try next row
            if list_row + 1 < self._list.count():
                self._list.blockSignals(True)
                self._list.setCurrentRow(list_row + 1)
                self._list.blockSignals(False)
                self._on_row_changed(list_row + 1)
            return
        if fname in self._filenames:
            self.frame_selected.emit(fname)

    def get_filename(self, row: int) -> str:
        if 0 <= row < len(self._filenames):
            return self._filenames[row]
        return ""

    def current_row(self) -> int:
        """Return current frame index (not list widget row)."""
        list_row = self._list.currentRow()
        frame_row = self._list_row_to_frame_row(list_row)
        return frame_row if frame_row >= 0 else 0

    def count(self) -> int:
        """Return number of frames (not including dividers)."""
        return len(self._filenames)
