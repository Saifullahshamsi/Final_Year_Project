"""Fusion model and the volume-residualisation transformer.

Gradient-boosted trees are the primary model, chosen in advance: 129 units
cannot support a sequence model, and an overfitted one would inflate the fusion
arm, which is the arm under test.

`VolumeResidualiser` exists so the residualised structure arm can be run
*without* leaking. It is an sklearn transformer, so when it sits in a Pipeline
the regression is fitted on each fold's training split only. Fitting it once on
the full matrix would push test-set information into every fold through the
regression coefficients and silently inflate every score.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline


class VolumeResidualiser(BaseEstimator, TransformerMixin):
    """Remove the linear volume component from each feature.

    Input columns are [features..., proxy]; the proxy is the LAST column and is
    dropped on output, so the arm cannot smuggle volume back in as a feature.

    Fitted per fold. `n_features` counts only the residualised outputs.
    """

    def __init__(self, n_features: int):
        self.n_features = n_features

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        proxy = X[:, [-1]]
        self.models_ = []
        for j in range(self.n_features):
            lr = LinearRegression().fit(proxy, X[:, j])
            self.models_.append(lr)
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        proxy = X[:, [-1]]
        out = np.empty((X.shape[0], self.n_features), dtype=float)
        for j, lr in enumerate(self.models_):
            out[:, j] = X[:, j] - lr.predict(proxy)
        return out


def make_model(cfg: dict, kind: str = "default"):
    """Gradient-boosted trees. `regularised` is the low-capacity variant used to
    separate overfitting from fusion benefit."""
    seed, n_jobs = cfg["seed"], cfg["model"]["n_jobs"]
    common = dict(random_state=seed, early_stopping=False,
                  class_weight="balanced")
    if kind == "regularised":
        return HistGradientBoostingClassifier(
            max_iter=120, learning_rate=0.05, max_leaf_nodes=4,
            min_samples_leaf=15, l2_regularization=1.0, max_depth=3, **common)
    return HistGradientBoostingClassifier(
        max_iter=250, learning_rate=0.1, max_leaf_nodes=31,
        min_samples_leaf=5, l2_regularization=0.0, **common)


def build_estimator(cfg: dict, n_residualised: int = 0,
                    kind: str = "default"):
    """Model, wrapped in the residualiser when the arm asks for one."""
    model = make_model(cfg, kind)
    if n_residualised:
        return Pipeline([("residualise", VolumeResidualiser(n_residualised)),
                         ("model", model)])
    return model


__all__ = ["VolumeResidualiser", "make_model", "build_estimator",
           "HistGradientBoostingClassifier", "Pipeline"]
