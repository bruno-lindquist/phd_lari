from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class DistanceValidation:
    status: str
    mean_abs_delta_px: float | None


def build_distance_transform(
    image_shape_hw: tuple[int, int], ideal_points: np.ndarray, draw_thickness: int = 1
) -> np.ndarray:
    h, w = image_shape_hw
    mask = np.full((h, w), 255, dtype=np.uint8)
    pts_int = np.round(ideal_points).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(
        mask,
        [pts_int],
        isClosed=True,
        color=0,
        thickness=max(1, int(draw_thickness)),
        lineType=cv2.LINE_AA,
    )
    dist_map = cv2.distanceTransform(mask, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    return dist_map.astype(np.float32)


def sample_distance_map_bilinear(dist_map: np.ndarray, points: np.ndarray) -> np.ndarray:
    h, w = dist_map.shape[:2]
    x = np.clip(points[:, 0], 0, w - 1)
    y = np.clip(points[:, 1], 0, h - 1)

    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)

    wx = x - x0
    wy = y - y0

    top = (1.0 - wx) * dist_map[y0, x0] + wx * dist_map[y0, x1]
    bottom = (1.0 - wx) * dist_map[y1, x0] + wx * dist_map[y1, x1]
    values = (1.0 - wy) * top + wy * bottom
    return values.astype(np.float32)


def sample_distance_map_nearest(dist_map: np.ndarray, points: np.ndarray) -> np.ndarray:
    h, w = dist_map.shape[:2]
    x = np.clip(np.round(points[:, 0]).astype(np.int32), 0, w - 1)
    y = np.clip(np.round(points[:, 1]).astype(np.int32), 0, h - 1)
    return dist_map[y, x].astype(np.float32)


def distances_via_kdtree(real_points: np.ndarray, ideal_points: np.ndarray) -> np.ndarray:
    try:
        from scipy.spatial import cKDTree
    except ImportError:
        return _distances_bruteforce(real_points, ideal_points)
    tree = cKDTree(ideal_points.astype(np.float64))
    dist, _ = tree.query(real_points.astype(np.float64), k=1)
    return dist.astype(np.float32)


def validate_distance_methods(
    dt_distances: np.ndarray, kd_distances: np.ndarray, tolerance_px: float
) -> DistanceValidation:
    if dt_distances.shape != kd_distances.shape or dt_distances.size == 0:
        return DistanceValidation(status="invalid_inputs", mean_abs_delta_px=None)
    mean_delta = float(np.mean(np.abs(dt_distances.astype(np.float64) - kd_distances.astype(np.float64))))
    status = "ok" if mean_delta <= tolerance_px else "mismatch"
    return DistanceValidation(status=status, mean_abs_delta_px=mean_delta)


def _distances_bruteforce(real_points: np.ndarray, ideal_points: np.ndarray) -> np.ndarray:
    if real_points.size == 0 or ideal_points.size == 0:
        return np.empty((0,), dtype=np.float32)
    rp = real_points.astype(np.float64)
    ip = ideal_points.astype(np.float64)
    out = np.empty((rp.shape[0],), dtype=np.float64)
    chunk = 512
    for i in range(0, rp.shape[0], chunk):
        batch = rp[i : i + chunk]
        diff = batch[:, None, :] - ip[None, :, :]
        d2 = np.sum(diff * diff, axis=2)
        out[i : i + chunk] = np.sqrt(np.min(d2, axis=1))
    return out.astype(np.float32)
