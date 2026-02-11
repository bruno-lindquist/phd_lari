import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from cut_precision.distance import (
    build_distance_transform,
    sample_distance_map_nearest,
    validate_distance_methods,
)


def test_distance_transform_zero_on_contour():
    points = np.array([[10, 10], [90, 10], [90, 90], [10, 90]], dtype=np.float32)
    dist_map = build_distance_transform((120, 120), points, draw_thickness=1)
    sampled = sample_distance_map_nearest(dist_map, points)
    assert np.all(sampled <= 1.5)


def test_distance_validation_ok():
    dt = np.array([1.0, 1.2, 0.8], dtype=np.float32)
    kd = np.array([1.1, 1.3, 0.7], dtype=np.float32)
    check = validate_distance_methods(dt, kd, tolerance_px=0.2)
    assert check.status == "ok"
