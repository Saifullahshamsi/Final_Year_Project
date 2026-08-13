"""Temporal shape and ARIMA features.

The scale-invariance tests here are the ones that matter. Twelve temporal
features were *designed* to be scale-free by dividing through by the window
level, and eight of them still tracked volume — because for count data the
noise scales with the mean too. These tests pin the invariance that genuinely
holds and document the boundary where it stops.
"""
import numpy as np
import pandas as pd
import pytest

from src.data.loading import load_config
from src.features.temporal import arima_features, shape_features, size_proxy_audit


@pytest.fixture
def cfg():
    return load_config()


RISING = np.array([1, 1, 2, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 22, 27, 33, 40, 48])
FLAT = np.full(18, 10)
FALLING = RISING[::-1].copy()


class TestShapeDirection:
    def test_rising_curve_has_positive_slope(self):
        assert shape_features(RISING)["slope_norm"] > 0

    def test_falling_curve_has_negative_slope(self):
        assert shape_features(FALLING)["slope_norm"] < 0

    def test_flat_curve_has_no_slope_and_no_burstiness(self):
        f = shape_features(FLAT)
        assert f["slope_norm"] == pytest.approx(0.0, abs=1e-9)
        assert f["burstiness"] == pytest.approx(0.0, abs=1e-9)
        assert f["peakedness"] == pytest.approx(1.0)

    def test_mass_centroid_moves_late_when_volume_arrives_late(self):
        assert (shape_features(RISING)["mass_centroid"]
                > shape_features(FALLING)["mass_centroid"])

    def test_log_half_ratio_is_signed_by_direction(self):
        assert shape_features(RISING)["log_half_ratio"] > 0
        assert shape_features(FALLING)["log_half_ratio"] < 0
        assert shape_features(FLAT)["log_half_ratio"] == pytest.approx(0.0, abs=1e-6)

    def test_frac_last_quarter_detects_a_late_burst(self):
        late = np.concatenate([np.ones(14), np.full(4, 50)])
        assert shape_features(late)["frac_last_quarter"] > 0.8

    def test_accelerating_curve_has_positive_acceleration(self):
        assert shape_features(RISING)["accel_norm"] > 0


class TestScaleInvariance:
    """Multiplying every bin by a constant must not move these features."""

    @pytest.mark.parametrize("factor", [2, 10, 100])
    @pytest.mark.parametrize("curve", [RISING, FALLING, FLAT])
    def test_shape_features_are_invariant_to_a_constant_factor(self, curve, factor):
        a = shape_features(curve)
        b = shape_features(curve * factor)
        for k in a:
            assert a[k] == pytest.approx(b[k], abs=1e-6), k

    def test_invariance_does_NOT_extend_to_resampled_counts(self):
        """The boundary that caught eight features.

        Scaling a curve leaves the shape identical, but *realising* a lower
        count from the same process changes dispersion and zero-share — which
        is why algebraic scale-freedom was not enough and the audit is done by
        measurement.
        """
        rng = np.random.default_rng(0)
        big = rng.poisson(60, 18)
        small = rng.poisson(2, 18)
        assert (shape_features(small)["burstiness"]
                > shape_features(big)["burstiness"])
        assert (shape_features(small)["zero_bin_frac"]
                > shape_features(big)["zero_bin_frac"])


class TestDegenerateInput:
    def test_all_zero_window_returns_zeros_not_nan(self):
        f = shape_features(np.zeros(18))
        assert all(v == 0.0 for v in f.values())

    def test_short_window_returns_zeros(self):
        assert all(v == 0.0 for v in shape_features(np.array([1, 2])).values())

    def test_every_shape_value_is_finite(self):
        for curve in (RISING, FALLING, FLAT, np.array([0, 0, 0, 5, 0, 0] * 3)):
            assert all(np.isfinite(v) for v in shape_features(curve).values())


class TestArima:
    def test_fits_a_reasonable_series_and_reports_convergence(self):
        rng = np.random.default_rng(1)
        y = np.cumsum(rng.normal(2, 1, 60)).clip(0)
        f = arima_features(y)
        assert f["meta_arima_converged"] == 1
        assert all(np.isfinite(v) for v in f.values())

    def test_too_short_a_series_is_refused_not_faked(self):
        f = arima_features(np.array([1.0, 2.0, 3.0]))
        assert f["meta_arima_converged"] == 0
        assert f["arima_ar1"] == 0.0

    def test_all_zero_history_is_refused(self):
        assert arima_features(np.zeros(40))["meta_arima_converged"] == 0

    def test_residual_dispersion_is_normalised_by_level(self):
        """Otherwise arima_resid_cv would be a raw volume feature."""
        rng = np.random.default_rng(2)
        base = np.cumsum(rng.normal(2, 1, 60)).clip(0.1)
        a = arima_features(base)
        b = arima_features(base * 10)
        if a["meta_arima_converged"] and b["meta_arima_converged"]:
            assert a["arima_resid_cv"] == pytest.approx(b["arima_resid_cv"], rel=0.25)

    def test_convergence_flag_is_metadata_not_a_feature(self):
        f = arima_features(np.zeros(40))
        assert "meta_arima_converged" in f
        assert "arima_converged" not in f


class TestSizeProxyAudit:
    def test_flags_a_feature_that_tracks_volume(self, cfg):
        size = np.arange(1, 51, dtype=float)
        df = pd.DataFrame({"proxy": size * 3 + 1, "clean": np.tile([1.0, -1.0], 25)})
        res = size_proxy_audit(df, ["proxy", "clean"], size, 0.4)
        assert res["proxy"]["flagged"]
        assert not res["clean"]["flagged"]

    def test_catches_monotone_nonlinear_proxies(self, cfg):
        """Spearman, not Pearson — a log-shaped proxy still counts."""
        size = np.arange(1, 51, dtype=float)
        df = pd.DataFrame({"log_proxy": np.log(size)})
        assert size_proxy_audit(df, ["log_proxy"], size, 0.4)["log_proxy"]["flagged"]

    def test_constant_feature_is_not_flagged(self, cfg):
        size = np.arange(1, 51, dtype=float)
        df = pd.DataFrame({"const": np.ones(50)})
        res = size_proxy_audit(df, ["const"], size, 0.4)
        assert res["const"]["spearman_with_volume"] == 0.0
        assert not res["const"]["flagged"]

    def test_threshold_is_configurable_and_applied(self, cfg):
        assert cfg["audit"]["size_proxy_spearman_threshold"] == 0.4
