"""YOLO format exporter for annotation data.

Exports annotations in YOLO TXT format with a ``data.yaml`` file
compatible with Ultralytics training pipelines.
"""

import json
import shutil
import yaml
from pathlib import Path
from typing import Optional

from backend.annotation_store import AnnotationStore
from backend.file_manager import FileManager
from backend.models import (
    Category, CATEGORY_NAMES, FrameAnnotation, FrameStatus,
)


class YOLOExporter:
    """Export annotations in YOLO detection format.

    Output structure::

        output_yolo/
          data.yaml           — dataset config for ultralytics
          images/
            train/            — image files
          labels/
            train/            — YOLO txt label files
    """

    def __init__(self, store: AnnotationStore, input_folder: str | Path,
                 output_folder: str | Path):
        self.store = store
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)

    def export(self, split: str = "train",
               include_skipped: bool = False) -> dict:
        """Export all annotated frames to YOLO format.

        Args:
            split: Dataset split name (train, val, test).
            include_skipped: Whether to include skipped frames.

        Returns:
            ``{frames_exported, labels_exported, output_path}``
        """
        images_dir = self.output_folder / "images" / split
        labels_dir = self.output_folder / "labels" / split
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)

        frames_exported = 0
        labels_exported = 0

        for frame in self.store.iter_all_frames():
            if frame.status == FrameStatus.ANNOTATED:
                pass  # always export
            elif frame.status == FrameStatus.SKIPPED and include_skipped:
                pass  # optionally export skipped
            else:
                continue

            if not frame.boxes:
                continue

            # Copy image
            src = self.input_folder / frame.original_filename
            if not src.exists():
                continue

            img_name = Path(frame.original_filename).stem + ".png"
            dst = images_dir / img_name
            shutil.copy2(str(src), str(dst))

            # Generate YOLO label file
            label_name = Path(frame.original_filename).stem + ".txt"
            label_path = labels_dir / label_name

            lines = []
            for box in frame.boxes:
                # Skip pending boxes
                if box.box_status.value == "pending":
                    continue

                # Convert to YOLO normalized format: class x_center y_center width height
                if frame.image_width <= 0 or frame.image_height <= 0:
                    continue

                x_center = (box.x + box.width / 2) / frame.image_width
                y_center = (box.y + box.height / 2) / frame.image_height
                w_norm = box.width / frame.image_width
                h_norm = box.height / frame.image_height

                # Clamp to [0, 1]
                x_center = max(0.0, min(1.0, x_center))
                y_center = max(0.0, min(1.0, y_center))
                w_norm = max(0.0, min(1.0, w_norm))
                h_norm = max(0.0, min(1.0, h_norm))

                class_id = box.category.value
                lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} "
                             f"{w_norm:.6f} {h_norm:.6f}")
                labels_exported += 1

            if lines:
                label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                frames_exported += 1

        # Write data.yaml
        self._write_data_yaml(split)

        return {
            "frames_exported": frames_exported,
            "labels_exported": labels_exported,
            "output_path": str(self.output_folder),
        }

    def _write_data_yaml(self, split: str = "train"):
        """Write YOLO data.yaml for ultralytics compatibility."""
        names = {}
        for cat in Category:
            names[cat.value] = CATEGORY_NAMES[cat]

        data = {
            "path": str(self.output_folder.resolve()),
            "train": f"images/{split}",
            "val": f"images/{split}",  # Same for single-split export
            "nc": len(Category),
            "names": names,
        }

        yaml_path = self.output_folder / "data.yaml"
        yaml_path.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
