import subprocess

import numpy as np
import pytest

pytest.importorskip("cv2")

from cut_precision.pipeline_service import _git_commit
from cut_precision.visualize import save_mask, save_overlay


def test_git_commit_returns_none_when_git_unavailable(monkeypatch):
    def _raise_git_error(*_args, **_kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=["git", "rev-parse", "HEAD"])

    monkeypatch.setattr("cut_precision.pipeline_service.subprocess.check_output", _raise_git_error)
    assert _git_commit() is None


def test_save_mask_raises_when_image_write_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("cut_precision.visualize.cv2.imwrite", lambda *_args, **_kwargs: False)

    mask = np.zeros((8, 8), dtype=np.uint8)
    with pytest.raises(OSError, match="Could not write image artifact"):
        save_mask(tmp_path / "mask.png", mask)


def test_save_overlay_raises_when_image_write_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("cut_precision.visualize.cv2.imwrite", lambda *_args, **_kwargs: False)

    image = np.zeros((8, 8, 3), dtype=np.uint8)
    ideal_points = np.array([[1.0, 1.0], [6.0, 1.0], [6.0, 6.0], [1.0, 6.0]], dtype=np.float32)
    real_points = np.array([[1.5, 1.5], [5.5, 1.5], [5.5, 5.5], [1.5, 5.5]], dtype=np.float32)

    with pytest.raises(OSError, match="Could not write image artifact"):
        save_overlay(tmp_path / "overlay.png", image, ideal_points, real_points)
