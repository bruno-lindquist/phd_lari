from __future__ import annotations

from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def save_mask(path: str | Path, mask: np.ndarray) -> None:
    cv2.imwrite(str(path), mask)


def save_overlay(
    path: str | Path,
    background_bgr: np.ndarray,
    ideal_points: np.ndarray,
    real_points: np.ndarray,
) -> None:
    canvas = background_bgr.copy()
    if ideal_points.size:
        cv2.polylines(
            canvas,
            [np.round(ideal_points).astype(np.int32).reshape(-1, 1, 2)],
            isClosed=True,
            color=(0, 255, 0),
            thickness=2,
        )
    if real_points.size:
        cv2.polylines(
            canvas,
            [np.round(real_points).astype(np.int32).reshape(-1, 1, 2)],
            isClosed=True,
            color=(0, 0, 255),
            thickness=2,
        )
    cv2.imwrite(str(path), canvas)


def save_error_map(
    path: str | Path,
    background_bgr: np.ndarray,
    points: np.ndarray,
    distances: np.ndarray,
) -> None:
    canvas = cv2.cvtColor(background_bgr, cv2.COLOR_BGR2RGB)
    plt.figure(figsize=(8, 8))
    plt.imshow(canvas)
    if points.size and distances.size:
        sc = plt.scatter(points[:, 0], points[:, 1], c=distances, s=7, cmap="turbo")
        plt.colorbar(sc, label="Error (px)")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def save_histogram(path: str | Path, distances: np.ndarray) -> None:
    plt.figure(figsize=(8, 4))
    plt.hist(distances, bins=40, color="#1f77b4", edgecolor="white")
    plt.xlabel("Distance (px)")
    plt.ylabel("Count")
    plt.title("Distance Distribution")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def save_distance_map(path: str | Path, dist_map: np.ndarray) -> None:
    norm = cv2.normalize(dist_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    color = cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)
    cv2.imwrite(str(path), color)
