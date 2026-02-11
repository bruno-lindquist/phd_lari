from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass
class ExtractionConfig:
    ideal_adaptive_block_size: int = 35
    ideal_adaptive_c: int = 7
    ideal_close_kernel: int = 5
    ideal_dilate_kernel: int = 3
    ideal_min_area_ratio: float = 0.001
    ideal_group_area_ratio_to_max: float = 0.35
    ideal_group_center_radius_ratio: float = 0.45
    ideal_group_close_kernel: int = 9
    line_removal_min_length_ratio: float = 0.3
    line_removal_thickness: int = 3
    real_lab_l_threshold: int = 95
    real_hsv_v_threshold: int = 90
    real_close_kernel: int = 5
    real_open_kernel: int = 3


@dataclass
class RegistrationConfig:
    orb_nfeatures: int = 3000
    knn_ratio: float = 0.75
    ransac_reproj_threshold: float = 3.0
    min_matches: int = 20
    min_inlier_ratio: float = 0.2
    use_axes_fallback: bool = True
    axes_canny_low: int = 50
    axes_canny_high: int = 150
    axes_hough_threshold: int = 120
    axes_min_line_ratio: float = 0.20
    axes_segment_min_line_ratio: float = 0.05
    axes_max_line_gap: int = 15
    axes_angle_tolerance_deg: float = 20.0
    axes_horizontal_roi_min_y_ratio: float = 0.65
    axes_vertical_roi_max_x_ratio: float = 0.35
    use_ecc_fallback: bool = True
    ecc_motion: str = "affine"
    ecc_iterations: int = 1500
    ecc_eps: float = 1e-6


@dataclass
class CalibrationConfig:
    manual_mm_per_px: float | None = None
    ruler_mm: float = 120.0
    canny_low: int = 50
    canny_high: int = 150
    hough_threshold: int = 80
    hough_max_gap: int = 10
    ruler_min_line_ratio: float = 0.2


@dataclass
class DistanceConfig:
    draw_thickness: int = 1
    use_bilinear: bool = True
    validate_with_kdtree: bool = True
    validation_tolerance_px: float = 1.5


@dataclass
class MetricsConfig:
    tau: float = 0.02
    clamp_low: float = 0.0
    clamp_high: float = 100.0


@dataclass
class SamplingConfig:
    step_px: float = 1.5
    num_points: int | None = None
    max_points: int = 20000


@dataclass
class AppConfig:
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    registration: RegistrationConfig = field(default_factory=RegistrationConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    distance: DistanceConfig = field(default_factory=DistanceConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    sampling: SamplingConfig = field(default_factory=SamplingConfig)

    @classmethod
    def from_path(cls, path: str | Path | None) -> "AppConfig":
        if path is None:
            return cls()

        cfg_path = Path(path)
        if not cfg_path.exists():
            raise FileNotFoundError(f"Config file not found: {cfg_path}")

        payload = _read_config_file(cfg_path)
        defaults = asdict(cls())
        merged = _merge_dict(defaults, payload)
        return _from_merged_dict(merged)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_config_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in {".json"}:
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "YAML config requested but PyYAML is not installed. "
                "Use JSON or install pyyaml."
            ) from exc
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
            if not isinstance(data, dict):
                raise ValueError("YAML config root must be a mapping")
            return data
    raise ValueError(f"Unsupported config extension: {path.suffix}")


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _from_merged_dict(merged: dict[str, Any]) -> AppConfig:
    return AppConfig(
        extraction=ExtractionConfig(**merged.get("extraction", {})),
        registration=RegistrationConfig(**merged.get("registration", {})),
        calibration=CalibrationConfig(**merged.get("calibration", {})),
        distance=DistanceConfig(**merged.get("distance", {})),
        metrics=MetricsConfig(**merged.get("metrics", {})),
        sampling=SamplingConfig(**merged.get("sampling", {})),
    )
