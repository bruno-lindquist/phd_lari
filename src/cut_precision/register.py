from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import RegistrationConfig


@dataclass
class RegistrationResult:
    success: bool
    homography: np.ndarray
    method: str
    matches_total: int
    matches_used: int
    inlier_ratio: float
    reprojection_error_px: float | None
    reason: str | None = None


def estimate_homography_orb(
    template_bgr: np.ndarray, test_bgr: np.ndarray, cfg: RegistrationConfig
) -> RegistrationResult:
    template_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
    test_gray = cv2.cvtColor(test_bgr, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(nfeatures=cfg.orb_nfeatures)
    kp_t, des_t = orb.detectAndCompute(template_gray, None)
    kp_s, des_s = orb.detectAndCompute(test_gray, None)
    identity = np.eye(3, dtype=np.float32)

    if des_t is None or des_s is None:
        return RegistrationResult(
            success=False,
            homography=identity,
            method="identity_fallback",
            matches_total=0,
            matches_used=0,
            inlier_ratio=0.0,
            reprojection_error_px=None,
            reason="missing_descriptors",
        )

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    knn_matches = matcher.knnMatch(des_s, des_t, k=2)

    good: list[cv2.DMatch] = []
    for pair in knn_matches:
        if len(pair) != 2:
            continue
        m, n = pair
        if m.distance < cfg.knn_ratio * n.distance:
            good.append(m)

    if len(good) < cfg.min_matches:
        return RegistrationResult(
            success=False,
            homography=identity,
            method="identity_fallback",
            matches_total=len(knn_matches),
            matches_used=len(good),
            inlier_ratio=0.0,
            reprojection_error_px=None,
            reason="not_enough_matches",
        )

    src_pts = np.float32([kp_s[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp_t[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    hmat, inlier_mask = cv2.findHomography(
        src_pts, dst_pts, cv2.RANSAC, cfg.ransac_reproj_threshold
    )
    if hmat is None or inlier_mask is None:
        return RegistrationResult(
            success=False,
            homography=identity,
            method="identity_fallback",
            matches_total=len(knn_matches),
            matches_used=len(good),
            inlier_ratio=0.0,
            reprojection_error_px=None,
            reason="homography_failed",
        )

    inliers = inlier_mask.ravel().astype(bool)
    inlier_ratio = float(inliers.mean()) if inliers.size else 0.0
    reproj = _compute_reprojection_error(src_pts[inliers], dst_pts[inliers], hmat)
    success = inlier_ratio >= cfg.min_inlier_ratio
    method = "orb_homography" if success else "orb_homography_low_inliers"
    return RegistrationResult(
        success=success,
        homography=hmat.astype(np.float32),
        method=method,
        matches_total=len(knn_matches),
        matches_used=len(good),
        inlier_ratio=inlier_ratio,
        reprojection_error_px=reproj,
        reason=None if success else "low_inlier_ratio",
    )


def warp_points(points: np.ndarray, homography: np.ndarray) -> np.ndarray:
    if points.size == 0:
        return points
    pts = points.reshape(-1, 1, 2).astype(np.float32)
    warped = cv2.perspectiveTransform(pts, homography)
    return warped[:, 0, :].astype(np.float32)


def _compute_reprojection_error(
    src_pts: np.ndarray, dst_pts: np.ndarray, homography: np.ndarray
) -> float | None:
    if src_pts.size == 0:
        return None
    pred = cv2.perspectiveTransform(src_pts, homography)
    diff = pred[:, 0, :] - dst_pts[:, 0, :]
    err = np.linalg.norm(diff, axis=1)
    return float(np.mean(err))
