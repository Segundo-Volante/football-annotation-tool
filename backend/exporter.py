import json
import shutil
import unicodedata
from pathlib import Path
from typing import Optional

from backend.database import DatabaseManager
from backend.file_manager import FileManager
from backend.models import (
    BoundingBox, Category, CATEGORY_NAMES, FrameAnnotation, FrameStatus,
    METADATA_KEYS,
)


def _ascii_normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ASCII", "ignore").decode("ASCII")


def _extract_lastname(full_name: str) -> str:
    parts = full_name.strip().split()
    return _ascii_normalize(parts[-1]) if parts else "Unknown"


class Exporter:
    def __init__(self, db: DatabaseManager, input_folder: str | Path,
                 output_folder: str | Path):
        self.db = db
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        FileManager.create_output_dirs(self.output_folder)

    def validate_metadata(self, frame: FrameAnnotation) -> Optional[str]:
        """Return error message if metadata incomplete, else None."""
        for key in METADATA_KEYS:
            if not getattr(frame, key, None):
                return f"Set {key.replace('_', ' ')} before exporting"
        return None

    def export_frame(self, frame: FrameAnnotation, session_id: int) -> str:
        seq = self.db.get_next_seq(session_id)
        exported_name = self._build_frame_name(frame, seq)

        # 1. Copy original frame
        src = self.input_folder / frame.original_filename
        dst = self.output_folder / "frames" / exported_name
        shutil.copy2(str(src), str(dst))

        # 2. Generate per-frame COCO JSON
        json_name = Path(exported_name).stem + ".json"
        json_path = self.output_folder / "annotations" / json_name
        coco_data = self._build_coco_json(frame, exported_name)
        json_path.write_text(json.dumps(coco_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # 3. Crop bounding boxes
        image = FileManager.load_image(src)
        if image is not None:
            self._export_crops(image, frame, seq)

        # 4. Update combined dataset
        self._update_combined_dataset(coco_data)

        # 5. Update summary
        self._update_summary(session_id)

        # 6. Mark frame as annotated
        self.db.set_frame_status(frame.id, FrameStatus.ANNOTATED)
        self.db.set_exported_filename(frame.id, exported_name)

        return exported_name

    def _build_frame_name(self, frame: FrameAnnotation, seq: int) -> str:
        source = frame.source or "Unknown"
        rnd = frame.match_round or "R00"
        weather = frame.weather or "unknown"
        lighting = frame.lighting or "unknown"
        shot = frame.shot_type or "unknown"
        cam = frame.camera_motion or "unknown"
        situation = (frame.game_situation or "unknown").replace("_", "-")
        return f"{source}_{rnd}_{weather}_{lighting}_{shot}_{cam}_{situation}_{seq:04d}.png"

    def _build_coco_json(self, frame: FrameAnnotation, exported_name: str) -> dict:
        annotations = []
        for i, box in enumerate(frame.boxes, 1):
            ann = {
                "id": i,
                "bbox": [box.x, box.y, box.width, box.height],
                "area": box.width * box.height,
                "category_id": box.category.value,
                "category_name": CATEGORY_NAMES[box.category],
                "occlusion": box.occlusion.value,
                "truncated": box.truncated,
            }
            if box.jersey_number is not None:
                ann["jersey_number"] = box.jersey_number
            if box.player_name:
                ann["player_name"] = box.player_name
            annotations.append(ann)

        return {
            "image": {
                "file_name": exported_name,
                "width": frame.image_width,
                "height": frame.image_height,
            },
            "frame_metadata": {
                "source": frame.source,
                "round": frame.match_round,
                "opponent": frame.opponent,
                "weather": frame.weather,
                "lighting": frame.lighting,
                "shot_type": frame.shot_type,
                "camera_motion": frame.camera_motion,
                "ball_status": frame.ball_status,
                "game_situation": frame.game_situation,
                "pitch_zone": frame.pitch_zone,
                "frame_quality": frame.frame_quality,
            },
            "annotations": annotations,
        }

    def _export_crops(self, image, frame: FrameAnnotation, seq: int):
        source = frame.source or "Unknown"
        rnd = frame.match_round or "R00"
        opp_idx = 0
        ref_idx = 0

        for box in frame.boxes:
            crop = FileManager.crop_region(image, box.x, box.y, box.width, box.height)
            if crop.size == 0:
                continue

            cat = box.category
            occ = box.occlusion.value

            if cat in (Category.ATLETICO_PLAYER, Category.ATLETICO_GK):
                num = box.jersey_number or 0
                lastname = _extract_lastname(box.player_name) if box.player_name else "Unknown"
                folder_name = f"{num:02d}_{lastname}"
                crop_name = f"{source}_{rnd}_{seq:04d}_{num:02d}_{lastname}_{occ}.png"
                crop_path = self.output_folder / "crops" / folder_name / crop_name

            elif cat == Category.OPPONENT:
                opp_idx += 1
                crop_name = f"{source}_{rnd}_{seq:04d}_opp_{opp_idx:03d}_{occ}.png"
                crop_path = self.output_folder / "crops" / "opponent" / crop_name

            elif cat == Category.OPPONENT_GK:
                opp_idx += 1
                crop_name = f"{source}_{rnd}_{seq:04d}_opp_{opp_idx:03d}_{occ}.png"
                crop_path = self.output_folder / "crops" / "opponent_gk" / crop_name

            elif cat == Category.REFEREE:
                ref_idx += 1
                crop_name = f"{source}_{rnd}_{seq:04d}_ref_{ref_idx:03d}_{occ}.png"
                crop_path = self.output_folder / "crops" / "referee" / crop_name

            elif cat == Category.BALL:
                crop_name = f"{source}_{rnd}_{seq:04d}_ball_{occ}.png"
                crop_path = self.output_folder / "crops" / "ball" / crop_name

            else:
                continue

            FileManager.save_image(crop, crop_path)

    def _update_combined_dataset(self, frame_coco: dict):
        dataset_path = self.output_folder / "coco_dataset.json"
        if dataset_path.exists():
            dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
        else:
            dataset = {
                "images": [],
                "annotations": [],
                "categories": [
                    {"id": cat.value, "name": CATEGORY_NAMES[cat]}
                    for cat in Category
                ],
            }

        image_id = len(dataset["images"]) + 1
        image_entry = frame_coco["image"].copy()
        image_entry["id"] = image_id
        dataset["images"].append(image_entry)

        ann_offset = len(dataset["annotations"])
        for ann in frame_coco["annotations"]:
            entry = ann.copy()
            entry["id"] = ann_offset + entry["id"]
            entry["image_id"] = image_id
            entry["iscrowd"] = 0
            dataset["annotations"].append(entry)

        dataset_path.write_text(
            json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _update_summary(self, session_id: int):
        stats = self.db.get_session_stats(session_id)
        session = self.db.get_session(session_id)

        rows = self.db.conn.execute(
            "SELECT b.category, b.jersey_number, b.player_name, COUNT(*) as cnt "
            "FROM boxes b JOIN frames f ON b.frame_id = f.id "
            "WHERE f.session_id = ? AND f.status = 'annotated' "
            "GROUP BY b.category, b.jersey_number, b.player_name",
            (session_id,),
        ).fetchall()

        by_category = {}
        by_player = {}
        total_boxes = 0
        for r in rows:
            cat_name = CATEGORY_NAMES.get(Category(r["category"]), "unknown")
            by_category[cat_name] = by_category.get(cat_name, 0) + r["cnt"]
            total_boxes += r["cnt"]
            if r["jersey_number"] is not None and r["player_name"]:
                key = f"{r['jersey_number']:02d}_{_extract_lastname(r['player_name'])}"
                by_player[key] = by_player.get(key, 0) + r["cnt"]

        summary = {
            "session": {
                "source": session["source"] if session else "",
                "round": session["match_round"] if session else "",
                "opponent": session["opponent"] if session else "",
                "team": "Atletico de Madrid",
            },
            "frames": {
                "total": stats["total"],
                "annotated": stats["annotated"],
                "skipped": stats["skipped"],
                "remaining": stats["unviewed"] + stats["in_progress"],
            },
            "annotations": {
                "total_boxes": total_boxes,
                "by_category": by_category,
                "by_player": by_player,
            },
        }

        summary_path = self.output_folder / "summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )
