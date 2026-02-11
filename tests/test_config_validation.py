import json

import pytest

from cut_precision.config import AppConfig, ExtractionConfig, RegistrationConfig


def test_default_app_config_is_valid():
    cfg = AppConfig.from_path(None)
    assert cfg.metrics.tau > 0.0


def test_extraction_config_requires_odd_adaptive_block_size():
    with pytest.raises(ValueError, match="extraction.ideal_adaptive_block_size"):
        ExtractionConfig(ideal_adaptive_block_size=10)


def test_registration_config_validates_ecc_motion():
    with pytest.raises(ValueError, match="registration.ecc_motion"):
        RegistrationConfig(ecc_motion="projective")


def test_app_config_from_path_rejects_invalid_tau(tmp_path):
    payload = {"metrics": {"tau": 0.0}}
    cfg_path = tmp_path / "invalid_tau.json"
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="metrics.tau"):
        AppConfig.from_path(cfg_path)


def test_app_config_from_path_rejects_invalid_canny_order(tmp_path):
    payload = {"registration": {"axes_canny_low": 180, "axes_canny_high": 120}}
    cfg_path = tmp_path / "invalid_canny.json"
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="registration.axes_canny_low"):
        AppConfig.from_path(cfg_path)
