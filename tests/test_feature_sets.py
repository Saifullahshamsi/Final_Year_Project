"""Ablation arm assignment.

"Structure beats volume" is the H1 claim, so the structure arm must not be
able to contain a node count. On these fragmented graphs n_components (149.6
vs 31.0) and n_communities (151.6 vs 31.3) track n_nodes (250.3 vs 51.2)
almost exactly — assign either to structure and H1 could pass on arithmetic.
"""
import copy

import pytest

from src.data.loading import load_config
from src.features.feature_sets import (
    FeatureSetError,
    arms,
    resolve,
    validate,
)


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def columns(cfg):
    """Every feature the config claims to assign."""
    return sorted({c for cols in cfg["features"].values() for c in cols})


class TestRealConfig:
    def test_assignment_is_complete_and_disjoint(self, cfg, columns):
        validate(cfg, columns)

    def test_every_declared_arm_resolves(self, cfg):
        for arm in arms(cfg):
            resolve(cfg, arm)

    def test_chance_arm_has_no_features(self, cfg):
        assert resolve(cfg, "chance") == []

    def test_volume_baseline_is_minimal(self, cfg):
        assert resolve(cfg, "volume_only") == [
            "window_tweets", "unique_users", "tweets_per_active_bin"]

    def test_h1_arm_is_volume_plus_structure(self, cfg):
        vol = set(resolve(cfg, "volume_only"))
        struct = set(resolve(cfg, "structure_size_free"))
        both = set(resolve(cfg, "volume_plus_structure"))
        assert both == vol | struct
        assert not vol & struct


class TestStructureArmContainsNoCounts:
    @pytest.mark.parametrize("banned", [
        "n_nodes", "n_edges", "n_components", "n_communities",
        "window_tweets", "unique_users", "tweets_per_active_bin",
        "max_in_degree", "max_out_degree", "max_core", "mean_core",
        "community_entropy", "mean_component_size",
    ])
    def test_named_count_is_not_in_the_structure_arm(self, cfg, banned):
        assert banned not in resolve(cfg, "structure_size_free")

    @pytest.mark.parametrize("inverse_size", [
        "density", "largest_wcc_frac", "largest_community_frac", "max_pagerank",
    ])
    def test_mechanically_inverse_size_features_are_not_structure(
            self, cfg, inverse_size):
        """~1/N quantities are size in disguise, just with the sign flipped."""
        assert inverse_size not in resolve(cfg, "structure_size_free")

    def test_no_structure_feature_starts_with_n_(self, cfg):
        assert not [c for c in resolve(cfg, "structure_size_free")
                    if c.startswith("n_")]

    def test_validator_rejects_a_count_moved_into_structure(self, cfg, columns):
        bad = copy.deepcopy(cfg)
        bad["features"]["size_dependent"].remove("n_components")
        bad["features"]["structure_size_free"].append("n_components")
        with pytest.raises(FeatureSetError, match="count-like"):
            validate(bad, columns)


class TestValidatorCatchesConfigDrift:
    def test_unassigned_feature_fails(self, cfg, columns):
        with pytest.raises(FeatureSetError, match="not assigned"):
            validate(cfg, columns + ["a_brand_new_feature"])

    def test_feature_in_two_sets_fails(self, cfg, columns):
        bad = copy.deepcopy(cfg)
        bad["features"]["volume_baseline"].append("reciprocity")
        with pytest.raises(FeatureSetError, match="more than one set"):
            validate(bad, columns)

    def test_config_naming_a_missing_column_fails(self, cfg, columns):
        with pytest.raises(FeatureSetError, match="does not have"):
            validate(cfg, [c for c in columns if c != "reciprocity"])

    def test_unknown_arm_fails(self, cfg):
        with pytest.raises(FeatureSetError, match="unknown ablation arm"):
            resolve(cfg, "no_such_arm")

    def test_arm_naming_an_unknown_set_fails(self, cfg):
        bad = copy.deepcopy(cfg)
        bad["ablation"].append({"name": "broken", "sets": ["nonexistent"]})
        with pytest.raises(FeatureSetError, match="unknown set"):
            resolve(bad, "broken")
