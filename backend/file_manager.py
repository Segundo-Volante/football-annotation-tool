from pathlib import Path
from typing import Optional

import cv2
import numpy as np

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}


class FileManager:
    @staticmethod
    def scan_folder(path: str | Path) -> list[str]:
        folder = Path(path)
        if not folder.is_dir():
            return []
        files = [
            f.name for f in sorted(folder.iterdir())
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        return files

    @staticmethod
    def create_output_dirs(output_path: str | Path):
        base = Path(output_path)
        (base / "frames").mkdir(parents=True, exist_ok=True)
        (base / "annotations").mkdir(parents=True, exist_ok=True)
        (base / "crops").mkdir(parents=True, exist_ok=True)

    @staticmethod
    def load_image(path: str | Path) -> Optional[np.ndarray]:
        img = cv2.imread(str(path))
        return img

    @staticmethod
    def crop_region(image: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
        h_img, w_img = image.shape[:2]
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(w_img, x + w)
        y2 = min(h_img, y + h)
        return image[y1:y2, x1:x2].copy()

    @staticmethod
    def save_image(image: np.ndarray, path: str | Path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(p), image)
