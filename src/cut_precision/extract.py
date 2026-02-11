from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import ExtractionConfig


@dataclass
class ExtractionResult:
    contour: np.ndarray
    binary_mask: np.ndarray
    cleaned_mask: np.ndarray
    success: bool
    reason: str | None = None


def extract_ideal_contour(image_bgr: np.ndarray, cfg: ExtractionConfig) -> ExtractionResult:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    block_size = cfg.ideal_adaptive_block_size
    if block_size % 2 == 0:
        block_size += 1

    binary = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        cfg.ideal_adaptive_c,
    )

    cleaned = _remove_long_lines(binary, cfg)
    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (cfg.ideal_close_kernel, cfg.ideal_close_kernel)
    )
    dilate_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (cfg.ideal_dilate_kernel, cfg.ideal_dilate_kernel)
    )
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, close_kernel)
    cleaned = cv2.dilate(cleaned, dilate_kernel, iterations=1)

    contour = _select_best_contour(cleaned, cfg.ideal_min_area_ratio)
    if contour is None:
        return ExtractionResult(
            contour=np.empty((0, 2), dtype=np.float32),
            binary_mask=binary,
            cleaned_mask=cleaned,
            success=False,
            reason="no_ideal_contour_found",
        )

    return ExtractionResult(
        contour=contour,
        binary_mask=binary,
        cleaned_mask=cleaned,
        success=True,
    )


def extract_real_contour(image_bgr: np.ndarray, cfg: ExtractionConfig) -> ExtractionResult:
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

    l_chan = lab[:, :, 0]
    v_chan = hsv[:, :, 2]
    dark_mask = np.where(
        (l_chan < cfg.real_lab_l_threshold) | (v_chan < cfg.real_hsv_v_threshold),
        255,
        0,
    ).astype(np.uint8)

    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (cfg.real_close_kernel, cfg.real_close_kernel)
    )
    open_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (cfg.real_open_kernel, cfg.real_open_kernel)
    )
    cleaned = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, close_kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, open_kernel)
    cleaned = _fill_holes(cleaned)

    contour = _largest_external_contour(cleaned)
    if contour is None:
        return ExtractionResult(
            contour=np.empty((0, 2), dtype=np.float32),
            binary_mask=dark_mask,
            cleaned_mask=cleaned,
            success=False,
            reason="no_real_contour_found",
        )

    return ExtractionResult(
        contour=contour,
        binary_mask=dark_mask,
        cleaned_mask=cleaned,
        success=True,
    )


def _remove_long_lines(binary: np.ndarray, cfg: ExtractionConfig) -> np.ndarray:
    h, w = binary.shape[:2]
    min_len = int(max(h, w) * cfg.line_removal_min_length_ratio)
    lines = cv2.HoughLinesP(
        binary,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=min_len,
        maxLineGap=10,
    )
    if lines is None:
        return binary

    mask = np.zeros_like(binary)
    for line in lines[:, 0, :]:
        x1, y1, x2, y2 = map(int, line.tolist())
        cv2.line(mask, (x1, y1), (x2, y2), 255, thickness=cfg.line_removal_thickness)

    out = binary.copy()
    out[mask > 0] = 0
    return out


def _select_best_contour(mask: np.ndarray, min_area_ratio: float) -> np.ndarray | None:
    h, w = mask.shape[:2]
    min_area = float(min_area_ratio * h * w)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        (mask > 0).astype(np.uint8), connectivity=8
    )
    if num_labels <= 1:
        return None

    center = np.array([w / 2.0, h / 2.0], dtype=np.float64)
    best_idx: int | None = None
    best_score = float("-inf")

    for comp_idx in range(1, num_labels):
        area = float(stats[comp_idx, cv2.CC_STAT_AREA])
        if area < min_area:
            continue

        x = int(stats[comp_idx, cv2.CC_STAT_LEFT])
        y = int(stats[comp_idx, cv2.CC_STAT_TOP])
        cw = int(stats[comp_idx, cv2.CC_STAT_WIDTH])
        ch = int(stats[comp_idx, cv2.CC_STAT_HEIGHT])
        centroid = centroids[comp_idx].astype(np.float64)

        dist_center = float(np.linalg.norm(centroid - center))
        touches_border = x <= 1 or y <= 1 or (x + cw) >= (w - 1) or (y + ch) >= (h - 1)
        border_penalty = 0.5 * area if touches_border else 0.0
        score = area - 1.5 * dist_center - border_penalty
        if score > best_score:
            best_score = score
            best_idx = comp_idx

    # Fallback: if strict threshold removes all candidates, use largest component.
    if best_idx is None:
        areas = stats[1:, cv2.CC_STAT_AREA]
        if areas.size == 0:
            return None
        best_idx = int(np.argmax(areas) + 1)

    component_mask = np.where(labels == best_idx, 255, 0).astype(np.uint8)
    contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    contour = max(contours, key=lambda c: c.shape[0])
    return contour[:, 0, :].astype(np.float32)


def _largest_external_contour(mask: np.ndarray) -> np.ndarray | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    return contour[:, 0, :].astype(np.float32)


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape[:2]
    flood = mask.copy()
    ff_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(flood, ff_mask, (0, 0), 255)
    holes = cv2.bitwise_not(flood)
    return cv2.bitwise_or(mask, holes)
