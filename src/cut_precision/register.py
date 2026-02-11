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


@dataclass
class _AxisFrame:
    origin: np.ndarray
    u_h: np.ndarray
    u_v: np.ndarray
    span_h: float
    span_v: float


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


def estimate_homography_axes(
    template_bgr: np.ndarray, test_bgr: np.ndarray, cfg: RegistrationConfig
) -> RegistrationResult:
    template_frame = _detect_axis_frame(template_bgr, cfg)
    test_frame = _detect_axis_frame(test_bgr, cfg)
    if template_frame is None or test_frame is None:
        return RegistrationResult(
            success=False,
            homography=np.eye(3, dtype=np.float32),
            method="identity_fallback",
            matches_total=0,
            matches_used=0,
            inlier_ratio=0.0,
            reprojection_error_px=None,
            reason="axis_detection_failed",
        )

    src_basis = np.column_stack(
        [test_frame.u_h * test_frame.span_h, test_frame.u_v * test_frame.span_v]
    ).astype(np.float64)
    dst_basis = np.column_stack(
        [template_frame.u_h * template_frame.span_h, template_frame.u_v * template_frame.span_v]
    ).astype(np.float64)

    det = float(np.linalg.det(src_basis))
    if abs(det) < 1e-6:
        return RegistrationResult(
            success=False,
            homography=np.eye(3, dtype=np.float32),
            method="identity_fallback",
            matches_total=0,
            matches_used=0,
            inlier_ratio=0.0,
            reprojection_error_px=None,
            reason="axis_singular_basis",
        )

    linear = dst_basis @ np.linalg.inv(src_basis)
    trans = template_frame.origin.reshape(2, 1) - linear @ test_frame.origin.reshape(2, 1)
    homography = np.array(
        [
            [linear[0, 0], linear[0, 1], trans[0, 0]],
            [linear[1, 0], linear[1, 1], trans[1, 0]],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )

    return RegistrationResult(
        success=True,
        homography=homography,
        method="axes_fallback",
        matches_total=0,
        matches_used=0,
        inlier_ratio=1.0,
        reprojection_error_px=None,
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


def _detect_axis_frame(image_bgr: np.ndarray, cfg: RegistrationConfig) -> _AxisFrame | None:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, cfg.axes_canny_low, cfg.axes_canny_high)
    h, w = edges.shape[:2]
    min_len = int(max(h, w) * cfg.axes_segment_min_line_ratio)
    lines = cv2.HoughLinesP(
        edges,
        rho=1.0,
        theta=np.pi / 180.0,
        threshold=max(30, int(round(cfg.axes_hough_threshold * 0.5))),
        minLineLength=min_len,
        maxLineGap=cfg.axes_max_line_gap,
    )
    if lines is None:
        return None

    horizontals: list[np.ndarray] = []
    verticals: list[np.ndarray] = []
    tol = float(cfg.axes_angle_tolerance_deg)
    min_y = float(h) * float(cfg.axes_horizontal_roi_min_y_ratio)
    max_x = float(w) * float(cfg.axes_vertical_roi_max_x_ratio)

    for line in lines[:, 0, :]:
        x1, y1, x2, y2 = map(float, line.tolist())
        dx, dy = x2 - x1, y2 - y1
        length = float(np.hypot(dx, dy))
        angle = float(np.degrees(np.arctan2(dy, dx)))
        angle_abs = abs(((angle + 180.0) % 180.0))
        cx = 0.5 * (x1 + x2)
        cy = 0.5 * (y1 + y2)
        line_vec = np.array([x1, y1, x2, y2, length, cx, cy], dtype=np.float64)
        if angle_abs <= tol or angle_abs >= (180.0 - tol):
            horizontals.append(line_vec)
        if abs(angle_abs - 90.0) <= tol:
            verticals.append(line_vec)

    if not horizontals or not verticals:
        return None

    horizontal_roi = [seg for seg in horizontals if float(seg[6]) >= min_y]
    vertical_roi = [seg for seg in verticals if float(seg[5]) <= max_x]
    if horizontal_roi:
        horizontals = horizontal_roi
    if vertical_roi:
        verticals = vertical_roi

    if not horizontals or not verticals:
        return None

    h_point, u_h = _fit_axis_line(horizontals)
    v_point, u_v = _fit_axis_line(verticals)
    if h_point is None or u_h is None or v_point is None or u_v is None:
        return None

    h_p1 = h_point - 1000.0 * u_h
    h_p2 = h_point + 1000.0 * u_h
    v_p1 = v_point - 1000.0 * u_v
    v_p2 = v_point + 1000.0 * u_v
    origin = _line_intersection(h_p1, h_p2, v_p1, v_p2)
    if origin is None:
        return None

    if u_h[0] < 0:
        u_h = -u_h
    if u_v[1] > 0:
        u_v = -u_v

    # Keep only near-orthogonal frames; rejects accidental long contour lines.
    ortho = float(abs(np.dot(u_h, u_v)))
    if ortho > np.cos(np.deg2rad(max(1.0, 90.0 - tol))):
        return None

    span_h = _estimate_axis_span(origin, u_h, horizontals)
    span_v = _estimate_axis_span(origin, u_v, verticals)
    if span_h <= 1.0 or span_v <= 1.0:
        return None

    return _AxisFrame(
        origin=origin.astype(np.float64),
        u_h=u_h.astype(np.float64),
        u_v=u_v.astype(np.float64),
        span_h=float(span_h),
        span_v=float(span_v),
    )


def _fit_axis_line(segments: list[np.ndarray]) -> tuple[np.ndarray | None, np.ndarray | None]:
    if not segments:
        return None, None
    pts: list[list[float]] = []
    for seg in segments:
        pts.append([float(seg[0]), float(seg[1])])
        pts.append([float(seg[2]), float(seg[3])])
    arr = np.array(pts, dtype=np.float32)
    if arr.shape[0] < 2:
        return None, None
    line = cv2.fitLine(arr, cv2.DIST_L2, 0, 0.01, 0.01)
    vx, vy, x0, y0 = [float(v) for v in line.flatten().tolist()]
    direction = np.array([vx, vy], dtype=np.float64)
    norm = float(np.linalg.norm(direction))
    if norm < 1e-8:
        return None, None
    point = np.array([x0, y0], dtype=np.float64)
    return point, direction / norm


def _estimate_axis_span(origin: np.ndarray, axis_u: np.ndarray, segments: list[np.ndarray]) -> float:
    projections: list[float] = []
    for seg in segments:
        p1 = np.array([float(seg[0]), float(seg[1])], dtype=np.float64)
        p2 = np.array([float(seg[2]), float(seg[3])], dtype=np.float64)
        projections.append(float(abs(np.dot(p1 - origin, axis_u))))
        projections.append(float(abs(np.dot(p2 - origin, axis_u))))
    if not projections:
        return 0.0
    return float(np.percentile(np.array(projections, dtype=np.float64), 95.0))


def _line_intersection(
    p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, p4: np.ndarray
) -> np.ndarray | None:
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-6:
        return None
    det1 = x1 * y2 - y1 * x2
    det2 = x3 * y4 - y3 * x4
    x = (det1 * (x3 - x4) - (x1 - x2) * det2) / den
    y = (det1 * (y3 - y4) - (y1 - y2) * det2) / den
    return np.array([x, y], dtype=np.float64)


def _unit_direction(p1: np.ndarray, p2: np.ndarray) -> np.ndarray | None:
    vec = (p2 - p1).astype(np.float64)
    norm = float(np.linalg.norm(vec))
    if norm < 1e-8:
        return None
    return vec / norm


def _ecc_motion_mode(name: str) -> int:
    normalized = name.strip().lower()
    if normalized == "translation":
        return cv2.MOTION_TRANSLATION
    if normalized == "euclidean":
        return cv2.MOTION_EUCLIDEAN
    if normalized == "homography":
        return cv2.MOTION_HOMOGRAPHY
    return cv2.MOTION_AFFINE
