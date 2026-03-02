"""Export Preview dialog — shows what will be exported and in what format.

Lets the user choose between COCO JSON and YOLO TXT formats,
preview the output, and confirm export.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QGroupBox, QTextEdit,
    QFileDialog, QMessageBox,
)

from backend.annotation_store import AnnotationStore
from backend.i18n import t
from backend.models import CATEGORY_NAMES, FrameStatus


class ExportPreviewDialog(QDialog):
    """Preview and configure dataset export."""

    def __init__(self, store: AnnotationStore, input_folder: str,
                 default_output: str, parent=None):
        super().__init__(parent)
        self._store = store
        self._input_folder = input_folder
        self._output_folder = default_output

        self.setWindowTitle(t("export.preview_title"))
        self.setMinimumSize(550, 450)
        self.setStyleSheet("""
            QDialog { background: #1E1E1E; }
            QLabel { color: #EEE; }
            QGroupBox { color: #CCC; border: 1px solid #444; border-radius: 6px;
                        margin-top: 8px; padding-top: 16px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; }
            QRadioButton { color: #EEE; }
            QTextEdit { background: #2A2A2A; color: #CCC; border: 1px solid #444;
                        font-family: monospace; font-size: 12px; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel(t("export.preview_title"))
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #4A90D9;")
        layout.addWidget(title)

        # Stats summary
        stats = store.get_session_stats()
        summary = QLabel(t("export.summary",
                           annotated=stats["annotated"],
                           skipped=stats["skipped"],
                           total=stats["total"]))
        summary.setStyleSheet("color: #AAA; font-size: 12px;")
        layout.addWidget(summary)

        # Format selection
        format_group = QGroupBox(t("export.format_label"))
        fmt_layout = QVBoxLayout(format_group)

        self._format_group = QButtonGroup(self)
        self._coco_radio = QRadioButton(t("export.format_coco"))
        self._coco_radio.setChecked(True)
        self._yolo_radio = QRadioButton(t("export.format_yolo"))
        self._format_group.addButton(self._coco_radio, 0)
        self._format_group.addButton(self._yolo_radio, 1)
        fmt_layout.addWidget(self._coco_radio)
        fmt_layout.addWidget(self._yolo_radio)
        layout.addWidget(format_group)

        # Output folder
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel(t("export.output_folder")))
        self._output_label = QLabel(self._output_folder)
        self._output_label.setStyleSheet("color: #4A90D9;")
        out_layout.addWidget(self._output_label, stretch=1)
        browse_btn = QPushButton(t("button.browse"))
        browse_btn.setStyleSheet(
            "QPushButton { background: #333; color: #EEE; padding: 4px 12px;"
            " border-radius: 3px; }"
        )
        browse_btn.clicked.connect(self._browse_output)
        out_layout.addWidget(browse_btn)
        layout.addLayout(out_layout)

        # Preview area
        layout.addWidget(QLabel(t("export.preview_label")))
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(150)
        layout.addWidget(self._preview)

        self._update_preview()
        self._format_group.buttonClicked.connect(lambda _: self._update_preview())

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(t("button.cancel"))
        cancel_btn.setStyleSheet(
            "QPushButton { background: #333; color: #EEE; padding: 8px 20px;"
            " border-radius: 4px; }"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        export_btn = QPushButton(t("export.export_button"))
        export_btn.setStyleSheet(
            "QPushButton { background: #4A90D9; color: white; padding: 8px 24px;"
            " border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #5AA0E9; }"
        )
        export_btn.clicked.connect(self.accept)
        btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, t("export.select_output"))
        if folder:
            self._output_folder = folder
            self._output_label.setText(folder)
            self._update_preview()

    def _update_preview(self):
        is_yolo = self._yolo_radio.isChecked()
        stats = self._store.get_session_stats()

        lines = []
        if is_yolo:
            lines.append("Format: YOLO TXT")
            lines.append(f"Output: {self._output_folder}/output_yolo/")
            lines.append("")
            lines.append("Structure:")
            lines.append("  images/train/   — image files")
            lines.append("  labels/train/   — YOLO .txt labels")
            lines.append("  data.yaml       — dataset config")
            lines.append("")
            lines.append(f"Frames to export: {stats['annotated']}")
            lines.append("")
            lines.append("Label format: class_id x_center y_center width height")
        else:
            lines.append("Format: COCO JSON")
            lines.append(f"Output: {self._output_folder}/output/")
            lines.append("")
            lines.append("Structure:")
            lines.append("  frames/         — renamed images")
            lines.append("  annotations/    — per-frame COCO JSON")
            lines.append("  crops/          — cropped player images")
            lines.append("  coco_dataset.json  — combined dataset")
            lines.append("  summary.json    — statistics")
            lines.append("")
            lines.append(f"Frames to export: {stats['annotated']}")

        self._preview.setText("\n".join(lines))

    def get_result(self) -> dict:
        """Return export configuration."""
        return {
            "format": "yolo" if self._yolo_radio.isChecked() else "coco",
            "output_folder": self._output_folder,
        }
