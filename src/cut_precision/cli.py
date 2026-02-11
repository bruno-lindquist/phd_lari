from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import json
import subprocess
import sys

import numpy as np

from . import __version__
from .calibration import CalibrationResult, estimate_mm_per_px_from_ruler
from .config import AppConfig
from .distance import (
    build_distance_transform,
    distances_via_kdtree,
    sample_distance_map_bilinear,
    sample_distance_map_nearest,
    validate_distance_methods,
)
from .extract import extract_ideal_contour, extract_real_contour
from .io_utils import ensure_dir, read_bgr_image
from .metrics import bbox_diagonal, compute_ipn, compute_statistics, to_mm
from .register import estimate_homography_orb, warp_points
from .report import write_report
from .resample import resample_closed_contour
from .visualize import (
    save_distance_map,
    save_error_map,
    save_histogram,
    save_mask,
    save_overlay,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cut precision pipeline")
    parser.add_argument("--template", required=True, help="Path to template image")
    parser.add_argument("--test", required=True, help="Path to real cut image")
    parser.add_argument("--out", default="out", help="Output directory")
    parser.add_argument("--config", default=None, help="Config file (json/yaml)")
    parser.add_argument("--step-px", type=float, default=None, help="Resampling step in px")
    parser.add_argument("--num-points", type=int, default=None, help="Fixed number of contour points")
    parser.add_argument("--no-kd-validate", action="store_true", help="Disable KDTree validation")
    parser.add_argument("--debug", action="store_true", help="Save intermediate artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = AppConfig.from_path(args.config)
    if args.step_px is not None:
        cfg.sampling.step_px = args.step_px
    if args.num_points is not None:
        cfg.sampling.num_points = args.num_points
    if args.no_kd_validate:
        cfg.distance.validate_with_kdtree = False

    out_dir = ensure_dir(args.out)
    template = read_bgr_image(args.template)
    test = read_bgr_image(args.test)

    ideal = extract_ideal_contour(template, cfg.extraction)
    real = extract_real_contour(test, cfg.extraction)
    if args.debug:
        save_mask(out_dir / "ideal_mask.png", ideal.cleaned_mask)
        save_mask(out_dir / "real_mask.png", real.cleaned_mask)

    if not ideal.success or not real.success:
        report = _build_failure_report(
            args=args,
            cfg=cfg,
            ideal_ok=ideal.success,
            real_ok=real.success,
            ideal_reason=ideal.reason,
            real_reason=real.reason,
        )
        write_report(report, out_dir / "report.json")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 2

    registration = estimate_homography_orb(template, test, cfg.registration)
    real_points_aligned = warp_points(real.contour, registration.homography)

    ideal_points = resample_closed_contour(
        ideal.contour, step_px=cfg.sampling.step_px, num_points=cfg.sampling.num_points
    )
    real_points = resample_closed_contour(
        real_points_aligned, step_px=cfg.sampling.step_px, num_points=cfg.sampling.num_points
    )

    dist_map = build_distance_transform(
        template.shape[:2], ideal_points, draw_thickness=cfg.distance.draw_thickness
    )
    if cfg.distance.use_bilinear:
        dist_px = sample_distance_map_bilinear(dist_map, real_points)
    else:
        dist_px = sample_distance_map_nearest(dist_map, real_points)

    kd_validation = {"status": "disabled", "mean_abs_delta_px": None}
    if cfg.distance.validate_with_kdtree:
        kd_dist = distances_via_kdtree(real_points, ideal_points)
        check = validate_distance_methods(dist_px, kd_dist, cfg.distance.validation_tolerance_px)
        kd_validation = {
            "status": check.status,
            "mean_abs_delta_px": check.mean_abs_delta_px,
        }

    stats_px = compute_statistics(dist_px)
    calib = estimate_mm_per_px_from_ruler(template, cfg.calibration)
    dist_mm = to_mm(dist_px, calib.mm_per_px)
    stats_mm = compute_statistics(dist_mm) if dist_mm is not None else None

    scale_px = bbox_diagonal(ideal_points)
    ipn_px, tolerance_px = compute_ipn(
        stats_px.mad, scale_px, cfg.metrics.tau, cfg.metrics.clamp_low, cfg.metrics.clamp_high
    )

    if calib.mm_per_px is not None:
        scale_mm = scale_px * calib.mm_per_px
        ipn_mm, tolerance_mm = compute_ipn(
            stats_mm.mad if stats_mm else 0.0,
            scale_mm,
            cfg.metrics.tau,
            cfg.metrics.clamp_low,
            cfg.metrics.clamp_high,
        )
    else:
        scale_mm = None
        ipn_mm = None
        tolerance_mm = None

    save_overlay(out_dir / "overlay.png", template, ideal_points, real_points)
    save_error_map(out_dir / "error_map.png", template, real_points, dist_px)
    save_histogram(out_dir / "error_hist.png", dist_px)
    if args.debug:
        save_distance_map(out_dir / "dist_map.png", dist_map)
    _write_distances_csv(out_dir / "distances.csv", real_points, dist_px, calib.mm_per_px)

    report = {
        "status": "ok",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "inputs": {
            "template": str(Path(args.template).resolve()),
            "test": str(Path(args.test).resolve()),
        },
        "registration": {
            "status": "ok" if registration.success else "warning",
            "method": registration.method,
            "matches_total": registration.matches_total,
            "matches_used": registration.matches_used,
            "inlier_ratio": registration.inlier_ratio,
            "reprojection_error_px": registration.reprojection_error_px,
            "reason": registration.reason,
        },
        "calibration": {
            "status": calib.status,
            "method": calib.method,
            "mm_per_px": calib.mm_per_px,
            "details": calib.details,
        },
        "distance_method": {
            "primary": "distance_transform",
            "validation": "kdtree" if cfg.distance.validate_with_kdtree else "disabled",
            "validation_status": kd_validation["status"],
            "validation_mean_abs_delta_px": kd_validation["mean_abs_delta_px"],
        },
        "metrics": {
            "mad_px": stats_px.mad,
            "std_px": stats_px.std,
            "p95_px": stats_px.p95,
            "max_px": stats_px.max_error,
            "mad_mm": stats_mm.mad if stats_mm else None,
            "std_mm": stats_mm.std if stats_mm else None,
            "p95_mm": stats_mm.p95 if stats_mm else None,
            "max_mm": stats_mm.max_error if stats_mm else None,
            "scale_px": scale_px,
            "scale_mm": scale_mm,
            "tau": cfg.metrics.tau,
            "tolerance_px": tolerance_px,
            "tolerance_mm": tolerance_mm,
            "ipn_px": ipn_px,
            "ipn_mm": ipn_mm,
        },
        "artifacts": {
            "report_json": str((out_dir / "report.json").resolve()),
            "overlay_png": str((out_dir / "overlay.png").resolve()),
            "error_map_png": str((out_dir / "error_map.png").resolve()),
            "error_hist_png": str((out_dir / "error_hist.png").resolve()),
            "distances_csv": str((out_dir / "distances.csv").resolve()),
        },
        "config": cfg.to_dict(),
        "git": {"commit": _git_commit()},
    }
    write_report(report, out_dir / "report.json")
    print(json.dumps(report["metrics"], indent=2, ensure_ascii=False))
    return 0


def _write_distances_csv(
    path: Path, points: np.ndarray, distances_px: np.ndarray, mm_per_px: float | None
) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["idx", "x", "y", "d_px", "d_mm"])
        if mm_per_px is None:
            for idx, (pt, dpx) in enumerate(zip(points, distances_px, strict=True)):
                writer.writerow([idx, float(pt[0]), float(pt[1]), float(dpx), ""])
        else:
            for idx, (pt, dpx) in enumerate(zip(points, distances_px, strict=True)):
                writer.writerow([idx, float(pt[0]), float(pt[1]), float(dpx), float(dpx * mm_per_px)])


def _git_commit() -> str | None:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return None


def _build_failure_report(
    args: argparse.Namespace,
    cfg: AppConfig,
    ideal_ok: bool,
    real_ok: bool,
    ideal_reason: str | None,
    real_reason: str | None,
) -> dict:
    return {
        "status": "failed",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "inputs": {
            "template": str(Path(args.template).resolve()),
            "test": str(Path(args.test).resolve()),
        },
        "stages": {
            "ideal_extraction": {"success": ideal_ok, "reason": ideal_reason},
            "real_extraction": {"success": real_ok, "reason": real_reason},
        },
        "config": cfg.to_dict(),
    }


if __name__ == "__main__":
    raise SystemExit(main())
