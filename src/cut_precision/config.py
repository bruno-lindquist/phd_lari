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

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _ensure_odd("extraction.ideal_adaptive_block_size", self.ideal_adaptive_block_size, min_value=3)
        _ensure_positive_int("extraction.ideal_close_kernel", self.ideal_close_kernel)
        _ensure_positive_int("extraction.ideal_dilate_kernel", self.ideal_dilate_kernel)
        _ensure_positive_int("extraction.ideal_group_close_kernel", self.ideal_group_close_kernel)
        _ensure_ratio("extraction.ideal_min_area_ratio", self.ideal_min_area_ratio, min_inclusive=False)
        _ensure_ratio(
            "extraction.ideal_group_area_ratio_to_max",
            self.ideal_group_area_ratio_to_max,
            min_inclusive=False,
        )
        _ensure_ratio(
            "extraction.ideal_group_center_radius_ratio",
            self.ideal_group_center_radius_ratio,
            min_inclusive=False,
        )
        _ensure_ratio(
            "extraction.line_removal_min_length_ratio",
            self.line_removal_min_length_ratio,
            min_inclusive=False,
        )
        _ensure_positive_int("extraction.line_removal_thickness", self.line_removal_thickness)
        _ensure_uint8("extraction.real_lab_l_threshold", self.real_lab_l_threshold)
        _ensure_uint8("extraction.real_hsv_v_threshold", self.real_hsv_v_threshold)
        _ensure_positive_int("extraction.real_close_kernel", self.real_close_kernel)
        _ensure_positive_int("extraction.real_open_kernel", self.real_open_kernel)


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
    axes_segment_min_line_ratio: float = 0.05
    axes_max_line_gap: int = 15
    axes_angle_tolerance_deg: float = 20.0
    axes_horizontal_roi_min_y_ratio: float = 0.65
    axes_vertical_roi_max_x_ratio: float = 0.35
    use_ecc_fallback: bool = True
    ecc_motion: str = "affine"
    ecc_iterations: int = 1500
    ecc_eps: float = 1e-6

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _ensure_positive_int("registration.orb_nfeatures", self.orb_nfeatures)
        _ensure_float_between("registration.knn_ratio", self.knn_ratio, 0.0, 1.0, inclusive_low=False)
        _ensure_positive_float("registration.ransac_reproj_threshold", self.ransac_reproj_threshold)
        _ensure_int_at_least("registration.min_matches", self.min_matches, minimum=4)
        _ensure_float_between("registration.min_inlier_ratio", self.min_inlier_ratio, 0.0, 1.0)
        _ensure_uint8("registration.axes_canny_low", self.axes_canny_low)
        _ensure_uint8("registration.axes_canny_high", self.axes_canny_high)
        if self.axes_canny_low >= self.axes_canny_high:
            _raise_config_error(
                "registration.axes_canny_low",
                "must be lower than registration.axes_canny_high",
                self.axes_canny_low,
            )
        _ensure_positive_int("registration.axes_hough_threshold", self.axes_hough_threshold)
        _ensure_ratio(
            "registration.axes_segment_min_line_ratio",
            self.axes_segment_min_line_ratio,
            min_inclusive=False,
        )
        _ensure_non_negative_int("registration.axes_max_line_gap", self.axes_max_line_gap)
        _ensure_float_between(
            "registration.axes_angle_tolerance_deg",
            self.axes_angle_tolerance_deg,
            0.0,
            90.0,
            inclusive_low=False,
            inclusive_high=False,
        )
        _ensure_ratio("registration.axes_horizontal_roi_min_y_ratio", self.axes_horizontal_roi_min_y_ratio)
        _ensure_ratio("registration.axes_vertical_roi_max_x_ratio", self.axes_vertical_roi_max_x_ratio)
        _ensure_positive_int("registration.ecc_iterations", self.ecc_iterations)
        _ensure_positive_float("registration.ecc_eps", self.ecc_eps)
        allowed_motion = {"translation", "euclidean", "affine", "homography"}
        motion = self.ecc_motion.strip().lower()
        if motion not in allowed_motion:
            _raise_config_error(
                "registration.ecc_motion",
                f"must be one of {sorted(allowed_motion)}",
                self.ecc_motion,
            )
        self.ecc_motion = motion


@dataclass
class CalibrationConfig:
    manual_mm_per_px: float | None = None
    ruler_mm: float = 120.0
    canny_low: int = 50
    canny_high: int = 150
    hough_threshold: int = 80
    hough_max_gap: int = 10
    ruler_min_line_ratio: float = 0.2

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.manual_mm_per_px is not None:
            _ensure_positive_float("calibration.manual_mm_per_px", self.manual_mm_per_px)
        _ensure_positive_float("calibration.ruler_mm", self.ruler_mm)
        _ensure_uint8("calibration.canny_low", self.canny_low)
        _ensure_uint8("calibration.canny_high", self.canny_high)
        if self.canny_low >= self.canny_high:
            _raise_config_error(
                "calibration.canny_low",
                "must be lower than calibration.canny_high",
                self.canny_low,
            )
        _ensure_positive_int("calibration.hough_threshold", self.hough_threshold)
        _ensure_non_negative_int("calibration.hough_max_gap", self.hough_max_gap)
        _ensure_ratio("calibration.ruler_min_line_ratio", self.ruler_min_line_ratio, min_inclusive=False)


@dataclass
class DistanceConfig:
    draw_thickness: int = 1
    use_bilinear: bool = True
    validate_with_kdtree: bool = True
    validation_tolerance_px: float = 1.5

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _ensure_positive_int("distance.draw_thickness", self.draw_thickness)
        _ensure_non_negative_float("distance.validation_tolerance_px", self.validation_tolerance_px)


@dataclass
class MetricsConfig:
    tau: float = 0.02
    clamp_low: float = 0.0
    clamp_high: float = 100.0

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _ensure_positive_float("metrics.tau", self.tau)
        if float(self.clamp_low) > float(self.clamp_high):
            _raise_config_error(
                "metrics.clamp_low",
                "must be <= metrics.clamp_high",
                self.clamp_low,
            )


@dataclass
class SamplingConfig:
    step_px: float = 1.5
    num_points: int | None = None
    max_points: int = 20000

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _ensure_positive_float("sampling.step_px", self.step_px)
        _ensure_int_at_least("sampling.max_points", self.max_points, minimum=8)
        if self.num_points is not None:
            _ensure_int_at_least("sampling.num_points", self.num_points, minimum=8)


@dataclass
class AppConfig:
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    registration: RegistrationConfig = field(default_factory=RegistrationConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    distance: DistanceConfig = field(default_factory=DistanceConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    sampling: SamplingConfig = field(default_factory=SamplingConfig)

    def __post_init__(self) -> None:
        self.validate()

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
        config = _from_merged_dict(merged)
        config.validate()
        return config

    def validate(self) -> None:
        self.extraction.validate()
        self.registration.validate()
        self.calibration.validate()
        self.distance.validate()
        self.metrics.validate()
        self.sampling.validate()

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


def _raise_config_error(field_name: str, rule: str, value: Any) -> None:
    raise ValueError(f"Invalid config '{field_name}': {rule}. Got {value!r}")


def _ensure_positive_int(field_name: str, value: int) -> None:
    if int(value) <= 0:
        _raise_config_error(field_name, "must be > 0", value)


def _ensure_non_negative_int(field_name: str, value: int) -> None:
    if int(value) < 0:
        _raise_config_error(field_name, "must be >= 0", value)


def _ensure_int_at_least(field_name: str, value: int, minimum: int) -> None:
    if int(value) < int(minimum):
        _raise_config_error(field_name, f"must be >= {minimum}", value)


def _ensure_positive_float(field_name: str, value: float) -> None:
    if float(value) <= 0.0:
        _raise_config_error(field_name, "must be > 0", value)


def _ensure_non_negative_float(field_name: str, value: float) -> None:
    if float(value) < 0.0:
        _raise_config_error(field_name, "must be >= 0", value)


def _ensure_odd(field_name: str, value: int, min_value: int) -> None:
    _ensure_int_at_least(field_name, value, minimum=min_value)
    if int(value) % 2 == 0:
        _raise_config_error(field_name, "must be odd", value)


def _ensure_uint8(field_name: str, value: int) -> None:
    if int(value) < 0 or int(value) > 255:
        _raise_config_error(field_name, "must be within [0, 255]", value)


def _ensure_ratio(field_name: str, value: float, min_inclusive: bool = True) -> None:
    low_ok = float(value) >= 0.0 if min_inclusive else float(value) > 0.0
    if not low_ok or float(value) > 1.0:
        rule = "must be within [0, 1]" if min_inclusive else "must be within (0, 1]"
        _raise_config_error(field_name, rule, value)


def _ensure_float_between(
    field_name: str,
    value: float,
    low: float,
    high: float,
    inclusive_low: bool = True,
    inclusive_high: bool = True,
) -> None:
    value_f = float(value)
    low_ok = value_f >= low if inclusive_low else value_f > low
    high_ok = value_f <= high if inclusive_high else value_f < high
    if not (low_ok and high_ok):
        low_bracket = "[" if inclusive_low else "("
        high_bracket = "]" if inclusive_high else ")"
        _raise_config_error(field_name, f"must be in {low_bracket}{low}, {high}{high_bracket}", value)
