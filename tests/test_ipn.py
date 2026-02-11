import pytest

from cut_precision.metrics import compute_ipn


def test_ipn_perfect_score():
    ipn, tol = compute_ipn(mad=0.0, scale=100.0, tau=0.02)
    assert tol == 2.0
    assert ipn == 100.0


def test_ipn_clamped_to_zero():
    ipn, _ = compute_ipn(mad=10.0, scale=100.0, tau=0.02)
    assert ipn == 0.0


def test_ipn_requires_positive_scale():
    with pytest.raises(ValueError):
        compute_ipn(mad=1.0, scale=0.0, tau=0.02)
