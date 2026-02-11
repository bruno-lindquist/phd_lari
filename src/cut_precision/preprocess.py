from __future__ import annotations

import cv2
import numpy as np


def to_gray(image_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)


def denoise_gray(gray: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    return cv2.GaussianBlur(gray, (kernel_size, kernel_size), 0)


def apply_clahe(gray: np.ndarray, clip_limit: float = 2.0, tile_size: int = 8) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    return clahe.apply(gray)
