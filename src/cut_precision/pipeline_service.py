from __future__ import annotations

from pathlib import Path
import argparse
import csv
import json
import subprocess

import numpy as np

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
from .logging_config import build_run_id, log_stage, setup_logging
from .metrics import (
    bbox_diagonal,
    compute_bidirectional_diagnostics,
    compute_ipn,
    compute_statistics,
    to_mm,
)
from .pipeline_context import TauCalibrationContext
from .register import (
    RegistrationResult,
    estimate_homography_axes,
    estimate_homography_ecc,
    estimate_homography_orb,
    warp_points,
)
from .report import write_report
from .report_builder import build_failure_report, build_success_report
from .resample import resample_closed_contour
from .tau_service import calibrate_labeled_tau_from_patterns, calibrate_target_tau_from_patterns
from .visualize import save_error_map, save_histogram, save_mask, save_overlay


def run_pipeline(args: argparse.Namespace) -> int:
    out_dir = ensure_dir(args.out)
    run_id = build_run_id()
    log = setup_logging(out_dir=out_dir, run_id=run_id, debug=args.debug)
    log.bind(event="pipeline.start", stage="pipeline", status="started").info("pipeline_started")

    cfg = AppConfig.from_path(args.config)
    log.bind(event="config.loaded", stage="config", status="ok").info("config_loaded")
    tau_context = TauCalibrationContext.fixed()
    if args.step_px is not None:
        cfg.sampling.step_px = args.step_px
    if args.num_points is not None:
        cfg.sampling.num_points = args.num_points
    if args.tau is not None:
        cfg.metrics.tau = args.tau
        tau_context.source = "cli_tau"

    if args.tau_auto_reports and (args.tau_auto_good_reports or args.tau_auto_bad_reports):
        raise ValueError(
            "Use either --tau-auto-reports OR (--tau-auto-good-reports with --tau-auto-bad-reports)"
        )

    if args.tau_auto_reports:
        with log_stage(log, "tau.auto_reports"):
            if args.tau_auto_curve_csv or args.tau_auto_curve_png:
                raise ValueError(
                    "--tau-auto-curve-csv/--tau-auto-curve-png are only valid with labeled auto mode"
                )
            target_calibration = calibrate_target_tau_from_patterns(
                report_patterns=args.tau_auto_reports,
                target_ipn=args.tau_auto_target_ipn,
                prefer_px=args.tau_auto_prefer_px,
                statistic_name=args.tau_auto_statistic,
                tau_min=args.tau_auto_min,
                tau_max=args.tau_auto_max,
            )
            cfg.metrics.tau = target_calibration.result.tau
            tau_context = TauCalibrationContext.from_auto_reports(
                report_patterns=target_calibration.report_patterns,
                calibration=target_calibration.result,
            )

    if args.tau_auto_good_reports or args.tau_auto_bad_reports:
        with log_stage(log, "tau.auto_labeled_reports"):
            if not (args.tau_auto_good_reports and args.tau_auto_bad_reports):
                raise ValueError(
                    "Both --tau-auto-good-reports and --tau-auto-bad-reports are required together"
                )
            labeled_calibration = calibrate_labeled_tau_from_patterns(
                good_report_patterns=args.tau_auto_good_reports,
                bad_report_patterns=args.tau_auto_bad_reports,
                accept_ipn=args.tau_auto_accept_ipn,
                prefer_px=args.tau_auto_prefer_px,
                tau_min=args.tau_auto_min,
                tau_max=args.tau_auto_max,
                curve_max_points=args.tau_auto_curve_max_points,
                policy=args.tau_auto_policy,
                objective=args.tau_auto_objective,
                max_mean_ipn_bad=args.tau_auto_max_mean_ipn_bad,
                min_mean_ipn_gap=args.tau_auto_min_mean_ipn_gap,
                min_tpr=args.tau_auto_min_tpr,
                min_tnr=args.tau_auto_min_tnr,
                curve_csv_path=args.tau_auto_curve_csv,
                curve_png_path=args.tau_auto_curve_png,
            )
            if labeled_calibration.curve_csv:
                log.bind(
                    event="artifact.write",
                    stage="tau.auto_labeled_reports",
                    status="ok",
                    artifact="tau_curve_csv",
                    path=str(Path(labeled_calibration.curve_csv).resolve()),
                ).info("artifact_written")
            if labeled_calibration.curve_png:
                log.bind(
                    event="artifact.write",
                    stage="tau.auto_labeled_reports",
                    status="ok",
                    artifact="tau_curve_png",
                    path=str(Path(labeled_calibration.curve_png).resolve()),
                ).info("artifact_written")
            cfg.metrics.tau = labeled_calibration.result.tau
            tau_context = TauCalibrationContext.from_auto_labeled_reports(
                good_report_patterns=labeled_calibration.good_report_patterns,
                bad_report_patterns=labeled_calibration.bad_report_patterns,
                policy_name=labeled_calibration.policy_cfg["policy"],
                labeled=labeled_calibration.result,
                curve_csv=labeled_calibration.curve_csv,
                curve_png=labeled_calibration.curve_png,
                curve_points=labeled_calibration.curve_points,
            )

    if args.manual_mm_per_px is not None:
        cfg.calibration.manual_mm_per_px = args.manual_mm_per_px
    if args.no_kd_validate:
        cfg.distance.validate_with_kdtree = False

    with log_stage(log, "image.load"):
        template = read_bgr_image(args.template)
        test = read_bgr_image(args.test)

    with log_stage(log, "extract.ideal"):
        ideal = extract_ideal_contour(template, cfg.extraction)
    with log_stage(log, "extract.real"):
        real = extract_real_contour(test, cfg.extraction)
    if args.debug:
        save_mask(out_dir / "real_mask.png", real.cleaned_mask)
        log.bind(
            event="artifact.write",
            stage="extract.real",
            status="ok",
            artifact="real_mask_png",
            path=str((out_dir / "real_mask.png").resolve()),
        ).debug("artifact_written")

    if not ideal.success or not real.success:
        report = build_failure_report(
            args=args,
            cfg=cfg,
            ideal_ok=ideal.success,
            real_ok=real.success,
            ideal_reason=ideal.reason,
            real_reason=real.reason,
            run_id=run_id,
        )
        write_report(report, out_dir / "report.json")
        log.bind(
            event="artifact.write",
            stage="report.write",
            status="ok",
            artifact="report_json",
            path=str((out_dir / "report.json").resolve()),
        ).info("artifact_written")
        log.bind(
            event="pipeline.end",
            stage="pipeline",
            status="failed",
            reason="contour_extraction_failed",
        ).warning("pipeline_finished_with_failure")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 2

    with log_stage(log, "register"):
        registration = estimate_homography_orb(template, test, cfg.registration)
        registration, reg_selection_mad_px, reg_candidates = _select_registration_with_contour_score(
            template=template,
            test=test,
            cfg=cfg,
            ideal_contour=ideal.contour,
            real_contour=real.contour,
            first_attempt=registration,
        )
        log.bind(
            event="register.selected",
            stage="register",
            status="ok" if registration.success else "warning",
            method=registration.method,
            reason=registration.reason,
            selection_mad_px=reg_selection_mad_px,
        ).info("registration_selected")
    homography = registration.homography if registration.success else np.eye(3, dtype=np.float32)
    real_points_aligned = warp_points(real.contour, homography)

    with log_stage(log, "resample"):
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

    with log_stage(log, "distance.compute"):
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
            if check.status != "ok":
                log.bind(
                    event="distance.validation",
                    stage="distance.compute",
                    status="warning",
                    validation_status=check.status,
                    mean_abs_delta_px=check.mean_abs_delta_px,
                ).warning("distance_validation_warning")

    with log_stage(log, "metrics.compute"):
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

    with log_stage(log, "artifacts.write"):
        save_overlay(out_dir / "overlay.png", template, ideal_points, real_points)
        log.bind(
            event="artifact.write",
            stage="artifacts.write",
            status="ok",
            artifact="overlay_png",
            path=str((out_dir / "overlay.png").resolve()),
        ).info("artifact_written")
        save_error_map(out_dir / "error_map.png", template, real_points, dist_px)
        log.bind(
            event="artifact.write",
            stage="artifacts.write",
            status="ok",
            artifact="error_map_png",
            path=str((out_dir / "error_map.png").resolve()),
        ).info("artifact_written")
        save_histogram(out_dir / "error_hist.png", dist_px)
        log.bind(
            event="artifact.write",
            stage="artifacts.write",
            status="ok",
            artifact="error_hist_png",
            path=str((out_dir / "error_hist.png").resolve()),
        ).info("artifact_written")
        _write_distances_csv(out_dir / "distances.csv", real_points, dist_px, calib.mm_per_px)
        log.bind(
            event="artifact.write",
            stage="artifacts.write",
            status="ok",
            artifact="distances_csv",
            path=str((out_dir / "distances.csv").resolve()),
        ).info("artifact_written")

    report = build_success_report(
        args=args,
        cfg=cfg,
        out_dir=out_dir,
        run_id=run_id,
        registration=registration,
        reg_selection_mad_px=reg_selection_mad_px,
        reg_candidates=reg_candidates,
        calib=calib,
        kd_validation=kd_validation,
        diagnostics_px=diagnostics_px,
        diagnostics_mm=diagnostics_mm,
        stats_px=stats_px,
        stats_mm=stats_mm,
        scale_px=scale_px,
        scale_mm=scale_mm,
        tolerance_px=tolerance_px,
        tolerance_mm=tolerance_mm,
        ipn_px=ipn_px,
        ipn_mm=ipn_mm,
        tau_context=tau_context,
        git_commit=_git_commit(),
    )
    write_report(report, out_dir / "report.json")
    log.bind(
        event="artifact.write",
        stage="report.write",
        status="ok",
        artifact="report_json",
        path=str((out_dir / "report.json").resolve()),
    ).info("artifact_written")
    log.bind(
        event="pipeline.end",
        stage="pipeline",
        status="ok",
        ipn_px=ipn_px,
        ipn_mm=ipn_mm,
    ).info("pipeline_finished")
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
    except (FileNotFoundError, OSError, subprocess.CalledProcessError):
        return None
