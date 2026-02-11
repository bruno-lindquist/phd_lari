import numpy as np

from cut_precision.cli import _pick_best_registration_for_contour
from cut_precision.config import AppConfig
from cut_precision.register import RegistrationResult


def _make_registration(method: str, tx: float, ty: float, success: bool = True) -> RegistrationResult:
    homography = np.array(
        [
            [1.0, 0.0, tx],
            [0.0, 1.0, ty],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    return RegistrationResult(
        success=success,
        homography=homography if success else np.eye(3, dtype=np.float32),
        method=method,
        matches_total=0,
        matches_used=0,
        inlier_ratio=1.0 if success else 0.0,
        reprojection_error_px=None,
        reason=None if success else "failed",
    )


def test_pick_best_registration_for_contour_by_mad():
    cfg = AppConfig.from_path(None)
    top = [[float(x), 0.0] for x in range(0, 101)]
    right = [[100.0, float(y)] for y in range(1, 101)]
    bottom = [[float(x), 100.0] for x in range(99, -1, -1)]
    left = [[0.0, float(y)] for y in range(99, 0, -1)]
    ideal = np.array(top + right + bottom + left, dtype=np.float32)
    # Real contour is translated by (+20, -10), so best homography should undo that.
    real = ideal + np.array([20.0, -10.0], dtype=np.float32)

    good = _make_registration("good", tx=-20.0, ty=10.0, success=True)
    bad = _make_registration("bad", tx=0.0, ty=0.0, success=True)
    failed = _make_registration("failed", tx=0.0, ty=0.0, success=False)

    chosen, best_mad, rows = _pick_best_registration_for_contour(
        candidates=[bad, good, failed],
        real_contour=real,
        ideal_points=ideal,
        cfg=cfg,
    )
    assert chosen.method == "good"
    assert best_mad is not None
    assert best_mad < 0.5
    assert len(rows) == 3
    assert rows[0]["selection_mad_px"] is not None
    assert rows[2]["selection_mad_px"] is None
