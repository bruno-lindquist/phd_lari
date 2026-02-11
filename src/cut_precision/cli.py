from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import json
import subprocess

import numpy as np

from . import __version__
from .calibration import estimate_mm_per_px_from_ruler
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
from .metrics import (
    bbox_diagonal,
    compute_bidirectional_diagnostics,
    compute_ipn,
    compute_statistics,
    to_mm,
)
from .register import (
    RegistrationResult,
    estimate_homography_axes,
    estimate_homography_ecc,
    estimate_homography_orb,
    warp_points,
)
from .report import write_report
from .resample import resample_closed_contour
from .tau import (
    TAU_POLICY_PRESETS,
    calibrate_tau_from_labeled_reports,
    build_labeled_tau_curve,
    calibrate_tau_from_reports,
    collect_report_paths,
    resolve_labeled_policy,
)
from .tau_export import write_tau_curve_csv, write_tau_curve_png
from .visualize import (
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
    parser.add_argument("--tau", type=float, default=None, help="IPN tolerance factor (relative)")
    parser.add_argument(
        "--tau-auto-reports",
        nargs="+",
        default=None,
        help="Glob patterns for report.json files used to auto-calibrate tau",
    )
    parser.add_argument(
        "--tau-auto-target-ipn",
        type=float,
        default=80.0,
        help="Target IPN used when auto-calibrating tau from reports",
    )
    parser.add_argument(
        "--tau-auto-statistic",
        choices=["median", "mean", "p75"],
        default="median",
        help="Statistic for auto-calibration over multiple reports",
    )
    parser.add_argument(
        "--tau-auto-good-reports",
        nargs="+",
        default=None,
        help="Glob patterns for 'good' labeled reports (class-based tau calibration)",
    )
    parser.add_argument(
        "--tau-auto-bad-reports",
        nargs="+",
        default=None,
        help="Glob patterns for 'bad' labeled reports (class-based tau calibration)",
    )
    parser.add_argument(
        "--tau-auto-accept-ipn",
        type=float,
        default=70.0,
        help="IPN acceptance threshold used for class-based tau calibration",
    )
    parser.add_argument(
        "--tau-auto-policy",
        choices=sorted(TAU_POLICY_PRESETS.keys()),
        default=None,
        help="Preset constraints/objective for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-objective",
        choices=["balanced_accuracy", "balanced_accuracy_then_gap", "gap_then_balanced_accuracy"],
        default=None,
        help="Objective used for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-max-mean-ipn-bad",
        type=float,
        default=None,
        help="Optional constraint for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-min-mean-ipn-gap",
        type=float,
        default=None,
        help="Optional constraint for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-min-tpr",
        type=float,
        default=None,
        help="Optional TPR constraint for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-min-tnr",
        type=float,
        default=None,
        help="Optional TNR constraint for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-prefer-px",
        action="store_true",
        help="Prefer px-based report metrics for tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-min",
        type=float,
        default=0.005,
        help="Lower bound when auto-calibrating tau",
    )
    parser.add_argument(
        "--tau-auto-max",
        type=float,
        default=0.5,
        help="Upper bound when auto-calibrating tau",
    )
    parser.add_argument(
        "--tau-auto-curve-csv",
        default=None,
        help="Save labeled tau calibration curve CSV (only labeled auto mode)",
    )
    parser.add_argument(
        "--tau-auto-curve-png",
        default=None,
        help="Save labeled tau calibration curve PNG (only labeled auto mode)",
    )
    parser.add_argument(
        "--tau-auto-curve-max-points",
        type=int,
        default=400,
        help="Max points for labeled tau calibration curve export",
    )
    parser.add_argument(
        "--manual-mm-per-px",
        type=float,
        default=None,
        help="Override automatic ruler calibration",
    )
    parser.add_argument("--no-kd-validate", action="store_true", help="Disable KDTree validation")
    parser.add_argument("--debug", action="store_true", help="Save intermediate artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = AppConfig.from_path(args.config)
    tau_context = {
        "mode": "fixed",
        "source": "config_or_cli",
        "policy": "custom",
        "target_ipn": None,
        "accept_ipn": None,
        "reports_used": 0,
        "good_reports_used": 0,
        "bad_reports_used": 0,
        "report_patterns": [],
        "good_report_patterns": [],
        "bad_report_patterns": [],
        "report_paths": [],
        "good_report_paths": [],
        "bad_report_paths": [],
        "statistic": None,
        "units": None,
        "objective": None,
        "max_mean_ipn_bad": None,
        "min_mean_ipn_gap": None,
        "min_tpr": None,
        "min_tnr": None,
        "constraints_satisfied": None,
        "feasible_points": None,
        "fallback_reason": None,
        "balanced_accuracy": None,
        "tpr": None,
        "tnr": None,
        "mean_ipn_good": None,
        "mean_ipn_bad": None,
        "mean_ipn_gap": None,
        "tp": None,
        "fn": None,
        "tn": None,
        "fp": None,
        "curve_csv": None,
        "curve_png": None,
        "curve_points": None,
    }
    if args.step_px is not None:
        cfg.sampling.step_px = args.step_px
    if args.num_points is not None:
        cfg.sampling.num_points = args.num_points
    if args.tau is not None:
        cfg.metrics.tau = args.tau
        tau_context["source"] = "cli_tau"
    if args.tau_auto_reports and (args.tau_auto_good_reports or args.tau_auto_bad_reports):
        raise ValueError(
            "Use either --tau-auto-reports OR (--tau-auto-good-reports with --tau-auto-bad-reports)"
        )
    if args.tau_auto_reports:
        if args.tau_auto_curve_csv or args.tau_auto_curve_png:
            raise ValueError(
                "--tau-auto-curve-csv/--tau-auto-curve-png are only valid with labeled auto mode"
            )
        paths = collect_report_paths(args.tau_auto_reports)
        calibration = calibrate_tau_from_reports(
            report_paths=paths,
            target_ipn=args.tau_auto_target_ipn,
            prefer_mm=not args.tau_auto_prefer_px,
            statistic_name=args.tau_auto_statistic,
            tau_min=args.tau_auto_min,
            tau_max=args.tau_auto_max,
        )
        cfg.metrics.tau = calibration.tau
        tau_context = {
            "mode": "auto_from_reports",
            "source": "reports",
            "policy": "custom",
            "target_ipn": calibration.target_ipn,
            "accept_ipn": None,
            "reports_used": calibration.reports_used,
            "good_reports_used": 0,
            "bad_reports_used": 0,
            "report_patterns": list(args.tau_auto_reports),
            "good_report_patterns": [],
            "bad_report_patterns": [],
            "report_paths": [item.report_path for item in calibration.candidates],
            "good_report_paths": [],
            "bad_report_paths": [],
            "statistic": calibration.statistic,
            "units": calibration.units,
            "objective": None,
            "max_mean_ipn_bad": None,
            "min_mean_ipn_gap": None,
            "min_tpr": None,
            "min_tnr": None,
            "constraints_satisfied": None,
            "feasible_points": None,
            "fallback_reason": None,
            "balanced_accuracy": None,
            "tpr": None,
            "tnr": None,
            "mean_ipn_good": None,
            "mean_ipn_bad": None,
            "mean_ipn_gap": None,
            "tp": None,
            "fn": None,
            "tn": None,
            "fp": None,
            "curve_csv": None,
            "curve_png": None,
            "curve_points": None,
        }
    if args.tau_auto_good_reports or args.tau_auto_bad_reports:
        if not (args.tau_auto_good_reports and args.tau_auto_bad_reports):
            raise ValueError(
                "Both --tau-auto-good-reports and --tau-auto-bad-reports are required together"
            )
        good_paths = collect_report_paths(args.tau_auto_good_reports)
        bad_paths = collect_report_paths(args.tau_auto_bad_reports)
        policy_cfg = resolve_labeled_policy(
            policy=args.tau_auto_policy,
            objective=args.tau_auto_objective,
            max_mean_ipn_bad=args.tau_auto_max_mean_ipn_bad,
            min_mean_ipn_gap=args.tau_auto_min_mean_ipn_gap,
            min_tpr=args.tau_auto_min_tpr,
            min_tnr=args.tau_auto_min_tnr,
        )
        labeled = calibrate_tau_from_labeled_reports(
            good_report_paths=good_paths,
            bad_report_paths=bad_paths,
            accept_ipn=args.tau_auto_accept_ipn,
            prefer_mm=not args.tau_auto_prefer_px,
            tau_min=args.tau_auto_min,
            tau_max=args.tau_auto_max,
            objective=policy_cfg["objective"],
            max_mean_ipn_bad=policy_cfg["max_mean_ipn_bad"],
            min_mean_ipn_gap=policy_cfg["min_mean_ipn_gap"],
            min_tpr=policy_cfg["min_tpr"],
            min_tnr=policy_cfg["min_tnr"],
        )
        curve = build_labeled_tau_curve(
            good_report_paths=good_paths,
            bad_report_paths=bad_paths,
            accept_ipn=args.tau_auto_accept_ipn,
            prefer_mm=not args.tau_auto_prefer_px,
            tau_min=args.tau_auto_min,
            tau_max=args.tau_auto_max,
            max_points=args.tau_auto_curve_max_points,
        )
        curve_csv = None
        curve_png = None
        if args.tau_auto_curve_csv:
            curve_csv = write_tau_curve_csv(args.tau_auto_curve_csv, curve)
        if args.tau_auto_curve_png:
            curve_png = write_tau_curve_png(args.tau_auto_curve_png, curve, best_tau=labeled.tau)
        cfg.metrics.tau = labeled.tau
        tau_context = {
            "mode": "auto_from_labeled_reports",
            "source": "reports_labeled",
            "policy": policy_cfg["policy"],
            "target_ipn": None,
            "accept_ipn": labeled.accept_ipn,
            "reports_used": labeled.good_reports_used + labeled.bad_reports_used,
            "good_reports_used": labeled.good_reports_used,
            "bad_reports_used": labeled.bad_reports_used,
            "report_patterns": [],
            "good_report_patterns": list(args.tau_auto_good_reports),
            "bad_report_patterns": list(args.tau_auto_bad_reports),
            "report_paths": [],
            "good_report_paths": labeled.good_paths,
            "bad_report_paths": labeled.bad_paths,
            "statistic": None,
            "units": labeled.units,
            "objective": labeled.objective,
            "max_mean_ipn_bad": labeled.max_mean_ipn_bad,
            "min_mean_ipn_gap": labeled.min_mean_ipn_gap,
            "min_tpr": labeled.min_tpr,
            "min_tnr": labeled.min_tnr,
            "constraints_satisfied": labeled.constraints_satisfied,
            "feasible_points": labeled.feasible_points,
            "fallback_reason": labeled.fallback_reason,
            "balanced_accuracy": labeled.balanced_accuracy,
            "tpr": labeled.tpr,
            "tnr": labeled.tnr,
            "mean_ipn_good": labeled.mean_ipn_good,
            "mean_ipn_bad": labeled.mean_ipn_bad,
            "mean_ipn_gap": labeled.mean_ipn_gap,
            "tp": labeled.tp,
            "fn": labeled.fn,
            "tn": labeled.tn,
            "fp": labeled.fp,
            "curve_csv": curve_csv,
            "curve_png": curve_png,
            "curve_points": len(curve.points),
        }
    if args.manual_mm_per_px is not None:
        cfg.calibration.manual_mm_per_px = args.manual_mm_per_px
    if args.no_kd_validate:
        cfg.distance.validate_with_kdtree = False

    out_dir = ensure_dir(args.out)
    template = read_bgr_image(args.template)
    test = read_bgr_image(args.test)

    ideal = extract_ideal_contour(template, cfg.extraction)
    real = extract_real_contour(test, cfg.extraction)
    if args.debug:
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
    registration, reg_selection_mad_px, reg_candidates = _select_registration_with_contour_score(
        template=template,
        test=test,
        cfg=cfg,
        ideal_contour=ideal.contour,
        real_contour=real.contour,
        first_attempt=registration,
    )
    homography = registration.homography if registration.success else np.eye(3, dtype=np.float32)
    real_points_aligned = warp_points(real.contour, homography)

    ideal_points = resample_closed_contour(
        ideal.contour,
        step_px=cfg.sampling.step_px,
        num_points=cfg.sampling.num_points,
        max_points=cfg.sampling.max_points,
    )
    real_points = resample_closed_contour(
        real_points_aligned,
        step_px=cfg.sampling.step_px,
        num_points=cfg.sampling.num_points,
        max_points=cfg.sampling.max_points,
    )

    dist_map = build_distance_transform(
        template.shape[:2], ideal_points, draw_thickness=cfg.distance.draw_thickness
    )
    if cfg.distance.use_bilinear:
        dist_px = sample_distance_map_bilinear(dist_map, real_points)
    else:
        dist_px = sample_distance_map_nearest(dist_map, real_points)

    kd_real_to_ideal = distances_via_kdtree(real_points, ideal_points)
    kd_ideal_to_real = distances_via_kdtree(ideal_points, real_points)
    diagnostics_px = compute_bidirectional_diagnostics(kd_real_to_ideal, kd_ideal_to_real)

    kd_validation = {"status": "disabled", "mean_abs_delta_px": None}
    if cfg.distance.validate_with_kdtree:
        check = validate_distance_methods(dist_px, kd_real_to_ideal, cfg.distance.validation_tolerance_px)
        kd_validation = {
            "status": check.status,
            "mean_abs_delta_px": check.mean_abs_delta_px,
        }

    stats_px = compute_statistics(dist_px)
    calib = estimate_mm_per_px_from_ruler(template, cfg.calibration)
    dist_mm = to_mm(dist_px, calib.mm_per_px)
    stats_mm = compute_statistics(dist_mm) if dist_mm is not None else None
    if calib.mm_per_px is not None:
        kd_real_to_ideal_mm = kd_real_to_ideal.astype(np.float64) * calib.mm_per_px
        kd_ideal_to_real_mm = kd_ideal_to_real.astype(np.float64) * calib.mm_per_px
        diagnostics_mm = compute_bidirectional_diagnostics(kd_real_to_ideal_mm, kd_ideal_to_real_mm)
    else:
        diagnostics_mm = None

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
            "selection_strategy": "min_contour_mad_kdtree",
            "selection_mad_px": reg_selection_mad_px,
            "candidates": reg_candidates,
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
        "diagnostics": {
            "directed_mad_real_to_ideal_px": diagnostics_px.mad_real_to_ideal,
            "directed_mad_ideal_to_real_px": diagnostics_px.mad_ideal_to_real,
            "bidirectional_mad_px": diagnostics_px.bidirectional_mad,
            "hausdorff_px": diagnostics_px.hausdorff,
            "directed_mad_real_to_ideal_mm": (
                diagnostics_mm.mad_real_to_ideal if diagnostics_mm else None
            ),
            "directed_mad_ideal_to_real_mm": (
                diagnostics_mm.mad_ideal_to_real if diagnostics_mm else None
            ),
            "bidirectional_mad_mm": diagnostics_mm.bidirectional_mad if diagnostics_mm else None,
            "hausdorff_mm": diagnostics_mm.hausdorff if diagnostics_mm else None,
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
        "tau_calibration": {
            "mode": tau_context["mode"],
            "source": tau_context["source"],
            "policy": tau_context["policy"],
            "target_ipn": tau_context["target_ipn"],
            "accept_ipn": tau_context["accept_ipn"],
            "reports_used": tau_context["reports_used"],
            "good_reports_used": tau_context["good_reports_used"],
            "bad_reports_used": tau_context["bad_reports_used"],
            "report_patterns": tau_context["report_patterns"],
            "good_report_patterns": tau_context["good_report_patterns"],
            "bad_report_patterns": tau_context["bad_report_patterns"],
            "report_paths": tau_context["report_paths"],
            "good_report_paths": tau_context["good_report_paths"],
            "bad_report_paths": tau_context["bad_report_paths"],
            "statistic": tau_context["statistic"],
            "units": tau_context["units"],
            "objective": tau_context["objective"],
            "max_mean_ipn_bad": tau_context["max_mean_ipn_bad"],
            "min_mean_ipn_gap": tau_context["min_mean_ipn_gap"],
            "min_tpr": tau_context["min_tpr"],
            "min_tnr": tau_context["min_tnr"],
            "constraints_satisfied": tau_context["constraints_satisfied"],
            "feasible_points": tau_context["feasible_points"],
            "fallback_reason": tau_context["fallback_reason"],
            "balanced_accuracy": tau_context["balanced_accuracy"],
            "tpr": tau_context["tpr"],
            "tnr": tau_context["tnr"],
            "mean_ipn_good": tau_context["mean_ipn_good"],
            "mean_ipn_bad": tau_context["mean_ipn_bad"],
            "mean_ipn_gap": tau_context["mean_ipn_gap"],
            "tp": tau_context["tp"],
            "fn": tau_context["fn"],
            "tn": tau_context["tn"],
            "fp": tau_context["fp"],
            "curve_csv": tau_context["curve_csv"],
            "curve_png": tau_context["curve_png"],
            "curve_points": tau_context["curve_points"],
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


def _select_registration_with_contour_score(
    template: np.ndarray,
    test: np.ndarray,
    cfg: AppConfig,
    ideal_contour: np.ndarray,
    real_contour: np.ndarray,
    first_attempt: RegistrationResult,
) -> tuple[RegistrationResult, float | None, list[dict[str, float | int | str | bool | None]]]:
    candidates: list[RegistrationResult] = [first_attempt]
    if cfg.registration.use_axes_fallback:
        candidates.append(estimate_homography_axes(template, test, cfg.registration))
    if cfg.registration.use_ecc_fallback:
        candidates.append(estimate_homography_ecc(template, test, cfg.registration))

    ideal_points = resample_closed_contour(
        ideal_contour,
        step_px=cfg.sampling.step_px,
        num_points=cfg.sampling.num_points,
        max_points=cfg.sampling.max_points,
    )
    return _pick_best_registration_for_contour(
        candidates=candidates,
        real_contour=real_contour,
        ideal_points=ideal_points,
        cfg=cfg,
    )


def _pick_best_registration_for_contour(
    candidates: list[RegistrationResult],
    real_contour: np.ndarray,
    ideal_points: np.ndarray,
    cfg: AppConfig,
) -> tuple[RegistrationResult, float | None, list[dict[str, float | int | str | bool | None]]]:
    debug_rows: list[dict[str, float | int | str | bool | None]] = []
    best_candidate: RegistrationResult | None = None
    best_mad: float | None = None

    for reg in candidates:
        mad_px = None
        if reg.success:
            mad_px = _registration_mad_px(
                real_contour=real_contour,
                ideal_points=ideal_points,
                homography=reg.homography,
                cfg=cfg,
            )
            if best_mad is None or mad_px < best_mad:
                best_mad = mad_px
                best_candidate = reg
        debug_rows.append(
            {
                "method": reg.method,
                "success": reg.success,
                "reason": reg.reason,
                "matches_total": reg.matches_total,
                "matches_used": reg.matches_used,
                "inlier_ratio": reg.inlier_ratio,
                "reprojection_error_px": reg.reprojection_error_px,
                "selection_mad_px": mad_px,
            }
        )

    if best_candidate is not None:
        return best_candidate, best_mad, debug_rows
    return candidates[0], None, debug_rows


def _registration_mad_px(
    real_contour: np.ndarray,
    ideal_points: np.ndarray,
    homography: np.ndarray,
    cfg: AppConfig,
) -> float:
    warped = warp_points(real_contour, homography)
    warped_points = resample_closed_contour(
        warped,
        step_px=cfg.sampling.step_px,
        num_points=cfg.sampling.num_points,
        max_points=cfg.sampling.max_points,
    )
    distances = distances_via_kdtree(warped_points, ideal_points)
    return float(compute_statistics(distances).mad)


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
