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
    if inlier_ratio < cfg.min_inlier_ratio:
        return RegistrationResult(
            success=False,
            homography=identity,
            method="identity_fallback",
            matches_total=len(knn_matches),
            matches_used=len(good),
            inlier_ratio=inlier_ratio,
            reprojection_error_px=reproj,
            reason="low_inlier_ratio",
        )
    return RegistrationResult(
        success=True,
        homography=hmat.astype(np.float32),
        method="orb_homography",
        matches_total=len(knn_matches),
        matches_used=len(good),
        inlier_ratio=inlier_ratio,
        reprojection_error_px=reproj,
        reason=None,
    )


def warp_points(points: np.ndarray, homography: np.ndarray) -> np.ndarray:
    if points.size == 0:
        return points
    pts = points.reshape(-1, 1, 2).astype(np.float32)
    warped = cv2.perspectiveTransform(pts, homography)
    return warped[:, 0, :].astype(np.float32)


def estimate_homography_ecc(
    template_bgr: np.ndarray, test_bgr: np.ndarray, cfg: RegistrationConfig
) -> RegistrationResult:
    template_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
    test_gray = cv2.cvtColor(test_bgr, cv2.COLOR_BGR2GRAY)

    h_t, w_t = template_gray.shape[:2]
    h_s, w_s = test_gray.shape[:2]
    sx = w_t / float(w_s)
    sy = h_t / float(h_s)
    test_resized = cv2.resize(test_gray, (w_t, h_t), interpolation=cv2.INTER_LINEAR)

    template_f = template_gray.astype(np.float32) / 255.0
    test_f = test_resized.astype(np.float32) / 255.0

    motion = _ecc_motion_mode(cfg.ecc_motion)
    if motion == cv2.MOTION_HOMOGRAPHY:
        warp = np.eye(3, dtype=np.float32)
    else:
        warp = np.eye(2, 3, dtype=np.float32)

    criteria = (
        cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
        int(cfg.ecc_iterations),
        float(cfg.ecc_eps),
    )

    try:
        cc, warp = cv2.findTransformECC(
            template_f,
            test_f,
            warp,
            motion,
            criteria,
            inputMask=None,
            gaussFiltSize=5,
        )
    except cv2.error:
        return RegistrationResult(
            success=False,
            homography=np.eye(3, dtype=np.float32),
            method="identity_fallback",
            matches_total=0,
            matches_used=0,
            inlier_ratio=0.0,
            reprojection_error_px=None,
            reason="ecc_failed",
        )

    if motion == cv2.MOTION_HOMOGRAPHY:
        h_ecc = warp.astype(np.float32)
    else:
        h_ecc = np.vstack([warp, np.array([0.0, 0.0, 1.0], dtype=np.float32)])

    # Convert from resized-test coordinates back to original test coordinates.
    scale = np.array([[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
    homography = h_ecc @ scale
    return RegistrationResult(
        success=True,
        homography=homography.astype(np.float32),
        method="ecc_fallback",
        matches_total=0,
        matches_used=0,
        inlier_ratio=float(cc),
        reprojection_error_px=None,
        reason=None,
    )


def _compute_reprojection_error(
    src_pts: np.ndarray, dst_pts: np.ndarray, homography: np.ndarray
) -> float | None:
    if src_pts.size == 0:
        return None
    pred = cv2.perspectiveTransform(src_pts, homography)
    diff = pred[:, 0, :] - dst_pts[:, 0, :]
    err = np.linalg.norm(diff, axis=1)
    return float(np.mean(err))


def _ecc_motion_mode(name: str) -> int:
    normalized = name.strip().lower()
    if normalized == "translation":
        return cv2.MOTION_TRANSLATION
    if normalized == "euclidean":
        return cv2.MOTION_EUCLIDEAN
    if normalized == "homography":
        return cv2.MOTION_HOMOGRAPHY
    return cv2.MOTION_AFFINE
