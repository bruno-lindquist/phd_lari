import numpy as np

from cut_precision.resample import resample_closed_contour


def test_resample_closed_contour_returns_requested_count():
    square = np.array(
        [
            [0.0, 0.0],
            [10.0, 0.0],
            [10.0, 10.0],
            [0.0, 10.0],
        ],
        dtype=np.float32,
    )
    out = resample_closed_contour(square, num_points=40)
    assert out.shape == (40, 2)


def test_resample_closed_contour_step_mode():
    triangle = np.array(
        [
            [0.0, 0.0],
            [6.0, 0.0],
            [3.0, 4.0],
        ],
        dtype=np.float32,
    )
    out = resample_closed_contour(triangle, step_px=1.0, num_points=None)
    assert out.shape[0] >= 8


def test_resample_respects_max_points():
    square = np.array(
        [
            [0.0, 0.0],
            [1000.0, 0.0],
            [1000.0, 1000.0],
            [0.0, 1000.0],
        ],
        dtype=np.float32,
    )
    out = resample_closed_contour(square, step_px=0.1, max_points=500)
    assert out.shape[0] == 500
