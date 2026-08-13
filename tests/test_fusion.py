"""Fusion model and the residualisation transformer.

The load-bearing test is leak-safety. `VolumeResidualiser` fits a regression;
if that regression ever sees the test split, test information enters every fold
through the coefficients and inflates every score in the ablation without
anything looking wrong.
"""
import numpy as np
import pytest
from sklearn.model_selection import cross_val_predict

from src.data.loading import load_config
from src.models.fusion import VolumeResidualiser, build_estimator, make_model


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def volume_confounded():
    """A feature that is pure volume plus noise, and the proxy itself."""
    rng = np.random.default_rng(0)
    proxy = rng.uniform(10, 500, 200)
    signal = rng.normal(0, 1, 200)
    confounded = 0.02 * proxy + signal
    X = np.column_stack([confounded, signal, proxy])
    return X, proxy, signal


class TestResidualiser:
    def test_removes_the_volume_component(self, volume_confounded):
        X, proxy, _ = volume_confounded
        out = VolumeResidualiser(2).fit_transform(X)
        before = abs(np.corrcoef(X[:, 0], proxy)[0, 1])
        after = abs(np.corrcoef(out[:, 0], proxy)[0, 1])
        assert before > 0.5
        assert after < 1e-6

    def test_leaves_an_uncorrelated_feature_essentially_alone(self, volume_confounded):
        X, _, signal = volume_confounded
        out = VolumeResidualiser(2).fit_transform(X)
        assert np.corrcoef(out[:, 1], signal)[0, 1] > 0.99

    def test_drops_the_proxy_column(self, volume_confounded):
        X, _, _ = volume_confounded
        out = VolumeResidualiser(2).fit_transform(X)
        assert out.shape == (len(X), 2)

    def test_proxy_cannot_re_enter_as_a_feature(self, volume_confounded):
        """The arm exists to remove volume; returning it would defeat that."""
        X, proxy, _ = volume_confounded
        out = VolumeResidualiser(2).fit_transform(X)
        for j in range(out.shape[1]):
            assert not np.allclose(out[:, j], proxy)


class TestNoLeakage:
    def test_transform_uses_only_coefficients_fitted_on_train(self, volume_confounded):
        """Transforming unseen rows must not refit. If it did, the residuals of
        a held-out row would change depending on which other rows came with it."""
        X, _, _ = volume_confounded
        res = VolumeResidualiser(2).fit(X[:150])
        alone = res.transform(X[150:151])
        with_others = res.transform(X[150:])[0:1]
        assert np.allclose(alone, with_others)

    def test_refitting_on_a_different_split_changes_the_output(self, volume_confounded):
        """Confirms the transform is genuinely data-dependent, so fitting it
        outside the CV loop would leak rather than being a harmless no-op."""
        X, _, _ = volume_confounded
        a = VolumeResidualiser(2).fit(X[:100]).transform(X[100:110])
        b = VolumeResidualiser(2).fit(X[100:]).transform(X[100:110])
        assert not np.allclose(a, b)

    def test_pipeline_puts_the_residualiser_inside_cross_validation(self, cfg,
                                                                    volume_confounded):
        X, _, _ = volume_confounded
        y = (X[:, 1] + np.random.default_rng(1).normal(0, 0.5, len(X)) > 0).astype(int)
        est = build_estimator(cfg, n_residualised=2)
        assert est.steps[0][0] == "residualise"
        p = cross_val_predict(est, X, y, cv=3, method="predict_proba")[:, 1]
        assert len(p) == len(y) and np.isfinite(p).all()


class TestModelFactory:
    def test_regularised_has_lower_capacity(self, cfg):
        plain = make_model(cfg, "default").get_params()
        reg = make_model(cfg, "regularised").get_params()
        assert reg["max_leaf_nodes"] < plain["max_leaf_nodes"]
        assert reg["l2_regularization"] > plain["l2_regularization"]
        assert reg["min_samples_leaf"] > plain["min_samples_leaf"]

    def test_seed_is_taken_from_config(self, cfg):
        assert make_model(cfg).get_params()["random_state"] == cfg["seed"]

    def test_n_jobs_is_one_for_determinism(self, cfg):
        assert cfg["model"]["n_jobs"] == 1

    def test_predictions_are_reproducible(self, cfg, volume_confounded):
        X, _, _ = volume_confounded
        y = (X[:, 1] > 0).astype(int)
        a = make_model(cfg).fit(X[:, :2], y).predict_proba(X[:, :2])[:, 1]
        b = make_model(cfg).fit(X[:, :2], y).predict_proba(X[:, :2])[:, 1]
        assert np.allclose(a, b)

    def test_no_residualiser_when_the_arm_does_not_ask(self, cfg):
        assert not hasattr(build_estimator(cfg, n_residualised=0), "steps")
