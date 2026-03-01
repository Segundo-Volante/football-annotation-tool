import json
import os
import tempfile

import cv2
import numpy as np
import pytest

from backend.database import DatabaseManager
from backend.exporter import Exporter, _ascii_normalize, _extract_lastname
from backend.models import Category, FrameStatus, Occlusion


def test_ascii_normalize():
    assert _ascii_normalize("Álvarez") == "Alvarez"
    assert _ascii_normalize("Griezmann") == "Griezmann"


def test_extract_lastname():
    assert _extract_lastname("Julián Álvarez") == "Alvarez"
    assert _extract_lastname("Koke") == "Koke"
    assert _extract_lastname("") == "Unknown"


@pytest.fixture
def export_env():
    with tempfile.TemporaryDirectory() as input_dir, \
         tempfile.TemporaryDirectory() as output_dir:
        # Create a sample image
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        cv2.imwrite(os.path.join(input_dir, "frame_001.png"), img)

        # Create DB with V2 schema
        db_path = os.path.join(output_dir, "test.db")
        db = DatabaseManager(db_path)
        sid = db.create_session(input_dir, "LaLiga", "R15",
                                opponent="Real Madrid",
                                weather="clear", lighting="floodlight")
        fid = db.add_frame(sid, "frame_001.png", 0, 1920, 1080)
        db.save_frame_metadata(fid,
                               shot_type="wide",
                               camera_motion="static",
                               ball_status="visible",
                               game_situation="open_play",
                               pitch_zone="middle_third",
                               frame_quality="clean")
        db.add_box(fid, 100, 200, 50, 80, Category.ATLETICO_PLAYER,
                   jersey_number=19, player_name="Julián Álvarez")
        db.add_box(fid, 500, 300, 40, 70, Category.OPPONENT)
        db.add_box(fid, 800, 400, 20, 20, Category.BALL)

        exporter = Exporter(db, input_dir, output_dir)
        frame = db.get_frame(fid)

        yield {
            "db": db, "exporter": exporter, "frame": frame,
            "session_id": sid, "input_dir": input_dir, "output_dir": output_dir,
        }

        db.close()


def test_validate_metadata(export_env):
    env = export_env
    # With all metadata set, should be valid
    assert env["exporter"].validate_metadata(env["frame"]) is None


def test_validate_metadata_missing(export_env):
    env = export_env
    frame = env["frame"]
    frame.shot_type = None
    error = env["exporter"].validate_metadata(frame)
    assert error is not None
    assert "shot type" in error.lower()


def test_export_frame(export_env):
    env = export_env
    exported_name = env["exporter"].export_frame(env["frame"], env["session_id"])

    # Check renamed frame exists
    assert os.path.exists(os.path.join(env["output_dir"], "frames", exported_name))
    assert "LaLiga" in exported_name
    assert "R15" in exported_name

    # V2 naming includes weather, lighting, shot, camera, situation
    assert "clear" in exported_name
    assert "floodlight" in exported_name
    assert "wide" in exported_name
    assert "static" in exported_name

    # Check JSON annotation exists
    json_name = exported_name.replace(".png", ".json")
    json_path = os.path.join(env["output_dir"], "annotations", json_name)
    assert os.path.exists(json_path)
    with open(json_path) as f:
        data = json.load(f)
    assert len(data["annotations"]) == 3
    assert data["annotations"][0]["category_name"] == "atletico_player"

    # Check frame_metadata in COCO JSON
    assert "frame_metadata" in data
    assert data["frame_metadata"]["source"] == "LaLiga"
    assert data["frame_metadata"]["opponent"] == "Real Madrid"
    assert data["frame_metadata"]["weather"] == "clear"
    assert data["frame_metadata"]["shot_type"] == "wide"

    # Check crops
    alvarez_crops = os.path.join(env["output_dir"], "crops", "19_Alvarez")
    assert os.path.isdir(alvarez_crops)
    assert len(os.listdir(alvarez_crops)) == 1

    opp_crops = os.path.join(env["output_dir"], "crops", "opponent")
    assert os.path.isdir(opp_crops)

    ball_crops = os.path.join(env["output_dir"], "crops", "ball")
    assert os.path.isdir(ball_crops)

    # Check combined dataset
    dataset_path = os.path.join(env["output_dir"], "coco_dataset.json")
    assert os.path.exists(dataset_path)

    # Check summary
    summary_path = os.path.join(env["output_dir"], "summary.json")
    assert os.path.exists(summary_path)
    with open(summary_path) as f:
        summary = json.load(f)
    assert summary["session"]["opponent"] == "Real Madrid"

    # Check frame status updated
    frame = env["db"].get_frame(env["frame"].id)
    assert frame.status == FrameStatus.ANNOTATED
    assert frame.exported_filename == exported_name
