from __future__ import annotations

import numpy as np


def ensure_closed(points: np.ndarray) -> np.ndarray:
    if points.shape[0] == 0:
        return points
    if np.allclose(points[0], points[-1]):
        return points
    return np.vstack([points, points[0]])


def contour_to_points(contour: np.ndarray) -> np.ndarray:
    if contour.ndim == 3 and contour.shape[1] == 1 and contour.shape[2] == 2:
        return contour[:, 0, :].astype(np.float32)
    if contour.ndim == 2 and contour.shape[1] == 2:
        return contour.astype(np.float32)
    raise ValueError(f"Unsupported contour shape: {contour.shape}")


def resample_closed_contour(
    points: np.ndarray,
    step_px: float | None = 1.5,
    num_points: int | None = None,
    max_points: int | None = 20000,
) -> np.ndarray:
    if points.shape[0] < 3:
        raise ValueError("Contour needs at least 3 points")

    closed = ensure_closed(points.astype(np.float64))
    segments = closed[1:] - closed[:-1]
    seg_len = np.linalg.norm(segments, axis=1)
    arc = np.concatenate(([0.0], np.cumsum(seg_len)))
    total_len = float(arc[-1])

    if total_len <= 0:
        raise ValueError("Contour has zero perimeter")

    if num_points is None:
        if step_px is None:
            raise ValueError("Provide either step_px or num_points")
        num_points = max(8, int(np.ceil(total_len / float(step_px))))
    if max_points is not None:
        num_points = min(int(num_points), int(max_points))

    target = np.linspace(0.0, total_len, num_points, endpoint=False)
    idx = np.searchsorted(arc, target, side="right") - 1
    idx = np.clip(idx, 0, len(seg_len) - 1)

    seg_start = closed[idx]
    seg_delta = segments[idx]
    denom = np.where(seg_len[idx] == 0.0, 1.0, seg_len[idx])
    local_t = ((target - arc[idx]) / denom).reshape(-1, 1)
    sampled = seg_start + local_t * seg_delta
    return sampled.astype(np.float32)
