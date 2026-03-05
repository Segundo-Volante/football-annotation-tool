import os
import sys
import logging
import traceback
import tempfile
from pathlib import Path

# Configure logging BEFORE importing anything else
_log_dir = Path(tempfile.gettempdir())
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(_log_dir / "football_app.log", mode="w"),
    ],
)
logger = logging.getLogger(__name__)


def global_exception_hook(exc_type, exc_value, exc_tb):
    """Catch ALL unhandled Python exceptions and log them instead of letting
    PyQt6 call abort().  This is critical on macOS/Rosetta 2."""
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.critical("Unhandled exception:\n%s", msg)
    print(f"\n{'='*60}\nUNHANDLED EXCEPTION:\n{msg}{'='*60}\n", file=sys.stderr, flush=True)


# Install BEFORE PyQt6 import so it catches everything
sys.excepthook = global_exception_hook

# Enable automatic high-DPI scaling (needed for Windows high-DPI displays; no-op on macOS)
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        pass
elif sys.platform == "linux" and "microsoft" in Path("/proc/version").read_text().lower() if Path("/proc/version").exists() else False:
    # WSLg: Windows host DPI may not propagate — let Qt auto-detect
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

# On Windows, import torch BEFORE PyQt6 to avoid c10.dll conflict
if sys.platform == "win32":
    try:
        import torch  # noqa: F401 — must load before Qt to claim DLL search order
    except Exception:
        pass

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from frontend.main_window import MainWindow


def main():
    logger.info("Starting Football Annotation Tool")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Ensure readable font size and white QMessageBox on Windows
    if sys.platform == "win32":
        font = app.font()
        if font.pointSize() < 10:
            font.setPointSize(10)
            app.setFont(font)
        # Dark Fusion theme makes QMessageBox unreadable — force white background
        app.setStyleSheet(
            app.styleSheet() +
            "\nQMessageBox { background-color: #FFFFFF; }"
            "\nQMessageBox QLabel { color: #000000; }"
        )
    window = MainWindow()
    window.show()
    logger.info("MainWindow shown, entering event loop")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
