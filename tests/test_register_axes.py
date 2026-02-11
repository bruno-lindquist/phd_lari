import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from cut_precision.config import RegistrationConfig
from cut_precision.register import estimate_homography_axes, warp_points


def test_axes_fallback_translation():
    template = np.zeros((300, 300, 3), dtype=np.uint8)
    test = np.zeros((300, 300, 3), dtype=np.uint8)

    # Template axes.
    cv2.line(template, (20, 250), (280, 250), (255, 255, 255), 3)
    cv2.line(template, (50, 20), (50, 280), (255, 255, 255), 3)

    # Test axes translated by (+20, -10) in relation to template.
    cv2.line(test, (40, 240), (299, 240), (255, 255, 255), 3)
    cv2.line(test, (70, 10), (70, 270), (255, 255, 255), 3)

    cfg = RegistrationConfig(
        use_axes_fallback=True,
        axes_hough_threshold=60,
        axes_min_line_ratio=0.4,
        axes_max_line_gap=8,
        axes_angle_tolerance_deg=15.0,
    )
    reg = estimate_homography_axes(template, test, cfg)
    assert reg.success
    assert reg.method == "axes_fallback"

    pts = np.array([[70.0, 240.0], [100.0, 240.0], [70.0, 200.0]], dtype=np.float32)
    warped = warp_points(pts, reg.homography)
    expected = np.array([[50.0, 250.0], [80.0, 250.0], [50.0, 210.0]], dtype=np.float32)
    assert np.allclose(warped, expected, atol=3.0)
