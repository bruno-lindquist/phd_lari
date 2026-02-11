from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import argparse

from . import __version__
from .calibration import CalibrationResult
from .config import AppConfig
from .metrics import ContourDiagnostics, MetricsSummary
from .pipeline_context import TauCalibrationContext
from .register import RegistrationResult


def build_failure_report(
    args: argparse.Namespace,
    cfg: AppConfig,
    ideal_ok: bool,
    real_ok: bool,
    ideal_reason: str | None,
    real_reason: str | None,
    run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "run_id": run_id,
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


def build_success_report(
    *,
    args: argparse.Namespace,
    cfg: AppConfig,
    out_dir: Path,
    run_id: str,
    registration: RegistrationResult,
    reg_selection_mad_px: float | None,
    reg_candidates: list[dict[str, float | int | str | bool | None]],
    calib: CalibrationResult,
    kd_validation: dict[str, str | float | None],
    diagnostics_px: ContourDiagnostics,
    diagnostics_mm: ContourDiagnostics | None,
    stats_px: MetricsSummary,
    stats_mm: MetricsSummary | None,
    scale_px: float,
    scale_mm: float | None,
    tolerance_px: float,
    tolerance_mm: float | None,
    ipn_px: float,
    ipn_mm: float | None,
    tau_context: TauCalibrationContext,
    git_commit: str | None,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "run_id": run_id,
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
            "directed_mad_real_to_ideal_mm": diagnostics_mm.mad_real_to_ideal if diagnostics_mm else None,
            "directed_mad_ideal_to_real_mm": diagnostics_mm.mad_ideal_to_real if diagnostics_mm else None,
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
        "tau_calibration": tau_context.to_dict(),
        "artifacts": {
            "report_json": str((out_dir / "report.json").resolve()),
            "overlay_png": str((out_dir / "overlay.png").resolve()),
            "error_map_png": str((out_dir / "error_map.png").resolve()),
            "error_hist_png": str((out_dir / "error_hist.png").resolve()),
            "distances_csv": str((out_dir / "distances.csv").resolve()),
            "run_log": str((out_dir / "run.log").resolve()),
            "run_jsonl": str((out_dir / "run.jsonl").resolve()),
        },
        "config": cfg.to_dict(),
        "git": {"commit": git_commit},
    }
