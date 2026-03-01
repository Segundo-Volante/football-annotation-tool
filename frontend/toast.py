from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QLabel, QWidget


class Toast(QLabel):
    """Non-blocking overlay notification."""

    STYLES = {
        "success": "background: rgba(74,144,217,220); color: white;",
        "skip":    "background: rgba(217,74,74,220); color: white;",
        "warning": "background: rgba(245,166,35,220); color: #1E1E2E;",
        "info":    "background: rgba(42,42,60,230); color: #E8E8F0;",
    }

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setVisible(False)
        self._base_style = (
            "font-size: 14px; font-weight: bold; padding: 10px 24px; "
            "border-radius: 8px; "
        )

    def show_message(self, text: str, style: str = "info", duration_ms: int = 1500):
        css = self.STYLES.get(style, self.STYLES["info"])
        self.setStyleSheet(self._base_style + css)
        self.setText(text)
        self.adjustSize()
        # Position at top center of parent
        parent = self.parentWidget()
        if parent:
            x = (parent.width() - self.width()) // 2
            y = 50
            self.move(x, y)
        self.setVisible(True)
        QTimer.singleShot(duration_ms, self._hide)

    def _hide(self):
        self.setVisible(False)
