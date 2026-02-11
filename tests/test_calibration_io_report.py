import json

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from cut_precision.calibration import estimate_mm_per_px_from_ruler
from cut_precision.config import CalibrationConfig
from cut_precision.io_utils import ensure_dir, read_bgr_image
from cut_precision.report import write_report


def test_calibration_manual_override_returns_manual_result():
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    cfg = CalibrationConfig(manual_mm_per_px=0.42, ruler_mm=120.0)

    result = estimate_mm_per_px_from_ruler(image, cfg)

    assert result.status == "ok"
    assert result.method == "manual"
    assert result.mm_per_px == pytest.approx(0.42)
    assert result.details["ruler_mm"] == pytest.approx(120.0)


def test_calibration_returns_missing_when_no_ruler_lines_detected():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    cfg = CalibrationConfig(manual_mm_per_px=None)

    result = estimate_mm_per_px_from_ruler(image, cfg)

    assert result.status == "missing"
    assert result.method == "ruler_detection"
    assert result.mm_per_px is None
    assert result.details["reason"] == 1.0


def test_ensure_dir_creates_nested_directory(tmp_path):
    out_dir = ensure_dir(tmp_path / "nested" / "output")

    assert out_dir.exists()
    assert out_dir.is_dir()


def test_read_bgr_image_loads_written_image(tmp_path):
    image_path = tmp_path / "sample.png"
    sample = np.zeros((12, 16, 3), dtype=np.uint8)
    sample[2:4, 5:8, :] = 255
    write_ok = cv2.imwrite(str(image_path), sample)
    assert write_ok is True

    loaded = read_bgr_image(image_path)

    assert loaded.shape == sample.shape
    assert loaded.dtype == np.uint8


def test_read_bgr_image_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="Could not load image"):
        read_bgr_image(tmp_path / "missing.png")


def test_write_report_creates_parent_directory_and_json(tmp_path):
    out_path = tmp_path / "reports" / "run" / "report.json"
    payload = {"status": "ok", "message": "métrica válida"}

    write_report(payload, out_path)

    assert out_path.exists()
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written == payload
