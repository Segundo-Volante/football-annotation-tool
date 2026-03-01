import os
import tempfile

import cv2
import numpy as np
import pytest

from backend.file_manager import FileManager


@pytest.fixture
def sample_folder():
    with tempfile.TemporaryDirectory() as d:
        for name in ["frame_001.png", "frame_002.jpg", "frame_003.bmp",
                      "readme.txt", "data.csv"]:
            path = os.path.join(d, name)
            if name.endswith((".png", ".jpg", ".bmp")):
                img = np.zeros((100, 100, 3), dtype=np.uint8)
                cv2.imwrite(path, img)
            else:
                open(path, "w").close()
        yield d


def test_scan_folder(sample_folder):
    files = FileManager.scan_folder(sample_folder)
    assert len(files) == 3
    assert "readme.txt" not in files
    assert "frame_001.png" in files


def test_scan_empty_folder():
    with tempfile.TemporaryDirectory() as d:
        files = FileManager.scan_folder(d)
        assert files == []


def test_scan_nonexistent_folder():
    files = FileManager.scan_folder("/nonexistent/path")
    assert files == []


def test_create_output_dirs():
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "output")
        FileManager.create_output_dirs(out)
        assert os.path.isdir(os.path.join(out, "frames"))
        assert os.path.isdir(os.path.join(out, "annotations"))
        assert os.path.isdir(os.path.join(out, "crops"))


def test_load_image(sample_folder):
    img = FileManager.load_image(os.path.join(sample_folder, "frame_001.png"))
    assert img is not None
    assert img.shape == (100, 100, 3)


def test_crop_region():
    img = np.arange(300, dtype=np.uint8).reshape(10, 10, 3)
    crop = FileManager.crop_region(img, 2, 3, 4, 5)
    assert crop.shape == (5, 4, 3)


def test_crop_region_clamp():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    crop = FileManager.crop_region(img, 90, 90, 50, 50)
    assert crop.shape == (10, 10, 3)


def test_save_image():
    with tempfile.TemporaryDirectory() as d:
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        path = os.path.join(d, "sub", "test.png")
        FileManager.save_image(img, path)
        assert os.path.exists(path)
        loaded = cv2.imread(path)
        assert loaded.shape == (50, 50, 3)
