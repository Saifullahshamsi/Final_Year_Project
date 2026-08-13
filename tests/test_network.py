"""Network feature extraction.

The guard that matters here is not correctness of any single graph metric but
that nothing size-derived or outcome-derived reaches the feature matrix. The
first run of this module shipped `betweenness_exact` — a flag recording which
betweenness algorithm ran — as a modellable feature. Being a thresholded node
count, it separated the classes at AUC 0.79 while measuring nothing. These
tests exist so that class of mistake fails loudly.
"""
import networkx as nx
import numpy as np
import pandas as pd
import pytest

from src.data.loading import load_config
from src.features.network import (
    META_PREFIX,
    build_graph,
    centrality_features,
    community_features,
    feature_columns,
    growth_features,
    kcore_features,
    prototype_features,
    window_volume_features,
)


@pytest.fixture
def cfg():
    return load_config()


def records(edges, start_bin=0):
    """[(author, [targets]), ...] -> window records spread across bins."""
    return [(start_bin + i, a, t) for i, (a, t) in enumerate(edges)]


@pytest.fixture
def star():
    """One hub mentioned by five accounts — high concentration, no reciprocity."""
    return records([(f"u{i}", ["hub"]) for i in range(5)])


@pytest.fixture
def clique():
    """Mutual mentions — high reciprocity and clustering."""
    names = ["a", "b", "c", "d"]
    return records([(n, [m for m in names if m != n]) for n in names])


class TestGraphConstruction:
    def test_parallel_edges_collapse_to_a_weight(self):
        recs = records([("a", ["b"]), ("a", ["b"]), ("a", ["b"])])
        G = build_graph(recs)
        assert G.number_of_edges() == 1
        assert G["a"]["b"]["w"] == 3

    def test_authors_with_no_targets_still_become_nodes(self):
        G = build_graph(records([("lonely", [])]))
        assert "lonely" in G and G.number_of_edges() == 0

    def test_graph_is_directed(self):
        G = build_graph(records([("a", ["b"])]))
        assert G.has_edge("a", "b") and not G.has_edge("b", "a")


class TestStructuralFeatures:
    def test_star_concentrates_in_degree(self, star):
        f = prototype_features(build_graph(star), len(star))
        assert f["max_in_degree"] == 5
        assert f["reciprocity"] == 0.0

    def test_clique_is_reciprocal_and_clustered(self, clique):
        f = prototype_features(build_graph(clique), len(clique))
        assert f["reciprocity"] > 0.9
        assert f["mean_clustering"] > 0.5

    def test_degenerate_graph_returns_zeros_not_errors(self):
        f = prototype_features(build_graph(records([("a", [])])), 1)
        assert f["n_nodes"] == 1
        assert all(f[k] == 0.0 for k in ("reciprocity", "mean_clustering",
                                         "pagerank_gini", "max_in_degree"))

    def test_kcore_finds_the_dense_core(self, clique):
        f = kcore_features(build_graph(clique))
        assert f["max_core"] >= 3
        assert f["core2_frac"] == 1.0

    def test_kcore_of_a_star_is_shallow(self, star):
        assert kcore_features(build_graph(star))["max_core"] == 1

    def test_two_cliques_are_two_communities(self, cfg):
        recs = records([("a", ["b"]), ("b", ["a"]), ("c", ["d"]), ("d", ["c"])])
        f = community_features(build_graph(recs), cfg)
        assert f["n_communities"] == 2
        assert f["largest_community_frac"] == pytest.approx(0.5)

    def test_community_features_are_deterministic(self, cfg, clique):
        G = build_graph(clique)
        assert community_features(G, cfg) == community_features(G, cfg)

    def test_betweenness_zero_without_a_broker(self, cfg, clique):
        """Everyone adjacent to everyone: nobody brokers."""
        f = centrality_features(build_graph(clique), cfg)
        assert f["max_betweenness"] == pytest.approx(0.0, abs=1e-9)

    def test_betweenness_finds_a_broker(self, cfg):
        recs = records([("a", ["bridge"]), ("bridge", ["c"]),
                        ("c", ["bridge"]), ("bridge", ["a"])])
        f = centrality_features(build_graph(recs), cfg)
        assert f["max_betweenness"] > 0


class TestNoSizeProxiesInTheMatrix:
    """The defect this module actually shipped, as a regression test."""

    def test_betweenness_exact_is_metadata_not_a_feature(self, cfg, clique):
        f = centrality_features(build_graph(clique), cfg)
        assert META_PREFIX + "betweenness_exact" in f
        assert "betweenness_exact" not in f

    def test_feature_columns_drops_every_meta_column(self):
        df = pd.DataFrame({"topic": ["x"], "label": [1], "density": [0.5],
                           META_PREFIX + "peak_bin": [40],
                           META_PREFIX + "total_band_tweets": [900]})
        assert feature_columns(df) == ["density"]

    def test_no_whole_topic_volume_reaches_the_features(self):
        """Pre-peak claim: nothing counted outside the window may be modelled."""
        df = pd.DataFrame({"topic": ["x"], "label": [1],
                           "window_tweets": [30],
                           META_PREFIX + "total_band_tweets": [900],
                           META_PREFIX + "n_window_tweets_all_langs": [80]})
        cols = feature_columns(df)
        assert "window_tweets" in cols
        assert not any("total_band" in c or "all_langs" in c for c in cols)


class TestGrowth:
    def test_slopes_are_scale_free(self, cfg):
        """Doubling every count must not change the growth shape."""
        small = records([(f"u{i}", [f"v{i}"]) for i in range(12)])
        big = records([(f"u{i}", [f"v{i}"]) for i in range(12)] * 2)
        a = growth_features(small, 0, 12, cfg)
        b = growth_features(big, 0, 12, cfg)
        assert a["node_growth_slope"] == pytest.approx(b["node_growth_slope"],
                                                       abs=0.15)

    def test_front_loaded_graph_grows_more_slowly_than_back_loaded(self, cfg):
        front = [(0, f"u{i}", [f"v{i}"]) for i in range(10)]
        back = [(11, f"u{i}", [f"v{i}"]) for i in range(10)]
        assert (growth_features(front, 0, 12, cfg)["node_growth_slope"]
                < growth_features(back, 0, 12, cfg)["node_growth_slope"])

    def test_handles_an_empty_slice(self, cfg):
        f = growth_features(records([("a", ["b"])]), 0, 12, cfg)
        assert np.isfinite(list(f.values())).all()


class TestWindowVolume:
    def test_counts_only_what_it_is_given(self, star):
        f = window_volume_features(star)
        assert f["window_tweets"] == 5
        assert f["unique_users"] == 5

    def test_repeated_author_lowers_unique_users(self):
        f = window_volume_features(records([("a", []), ("a", []), ("b", [])]))
        assert f["window_tweets"] == 3 and f["unique_users"] == 2
        assert f["tweets_per_user"] == pytest.approx(1.5)


def test_networkx_louvain_is_available():
    """Guards the dependency, since community detection is silently optional."""
    assert hasattr(nx.community, "louvain_communities")
