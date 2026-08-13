"""Network-diffusion features over each unit's pre-peak window.

Refactor of the prototype extractor, with three changes that matter:

1. **The window is the real pre-peak window** from `src/data/units.py`, not the
   "earliest 150 tweets" proxy. Every tweet used falls strictly before
   (peak - lead).

2. **No whole-topic aggregates are emitted as features.** The prototype's
   single strongest feature was `total_count` — the topic's tweet count over
   the entire day. In a pre-peak setting that is leakage: it is largely
   determined by the peak the model is supposed to predict. Volume features
   here are computed from the window alone. Unit metadata that must not be
   modelled (peak position, whole-band volume) is written with a `meta_`
   prefix so it can never be selected by accident.

3. **New structure**: betweenness centrality, k-core decomposition, community
   detection (Louvain), and graph growth rate across the window.

The graph is directed, author -> each mentioned or replied-to account, with
parallel edges collapsed to a weight. Retweet cascades are deliberately not
built: retweet capture in this corpus is broken (`retweet`, `retweet_id`,
`user_rt` mostly empty). Weng et al. (2013) show the predictive structures are
clustering and community, computable from any interaction graph, and Cheng et
al. (2014) show early breadth matters more than cascade depth.

Run:  python -m src.features.network
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict

import networkx as nx
import numpy as np
import pandas as pd

from src.data.loading import (
    Band,
    band_from_config,
    clean_topic,
    load_config,
    parse_hashtags,
    parse_screen_names,
    stream,
)

# Features that describe the topic as a whole rather than its pre-peak window.
# Emitted for diagnostics, never modelled. Enforced by the meta_ prefix.
META_PREFIX = "meta_"


# ---------------------------------------------------------------------------
# Collect window tweets
# ---------------------------------------------------------------------------
def collect_window_tweets(cfg: dict, band: Band, units: pd.DataFrame
                          ) -> dict[str, list[tuple[int, str, list[str]]]]:
    """For each unit, the tweets inside its own window.

    Returns topic -> [(bin, author, [target screen names]), ...].
    De-duplicated on (id, topic); filtered to the feature language.
    """
    feat_lang = cfg["language"]["feature_language"]
    windows = {r.topic: (r.window_start_bin, r.window_end_bin, r.label)
               for r in units.itertuples()}
    pos = {t for t, w in windows.items() if w[2] == 1}
    neg = {t for t, w in windows.items() if w[2] == 0}
    out: dict[str, list] = defaultdict(list)
    seen: set[tuple[str, str]] = set()

    def keep(topic, tweet_id, b, author, men, rep):
        s, e, _ = windows[topic]
        if not (s <= b < e):                     # half-open: never the cutoff
            return
        if (tweet_id, topic) in seen:
            return
        seen.add((tweet_id, topic))
        author = str(author).strip().lower()
        targets = [t for t in parse_screen_names(men) + parse_screen_names(rep)
                   if t and t != author]
        out[topic].append((b, author, targets))

    if pos:
        for ch in stream(cfg["paths"]["trending_csv"],
                         ["id", "trend", "date", "time", "language",
                          "username", "mentions", "reply_to"], cfg):
            for i, t, d, tm, lg, u, men, rep in zip(
                    ch["id"].values, ch["trend"].values, ch["date"].values,
                    ch["time"].values, ch["language"].values,
                    ch["username"].values, ch["mentions"].values,
                    ch["reply_to"].values, strict=False):
                if feat_lang and lg != feat_lang:
                    continue
                topic = clean_topic(t)
                if topic not in pos:
                    continue
                b = band.bin_of(d, tm)
                if b is not None:
                    keep(topic, i, b, u, men, rep)

    if neg:
        for ch in stream(cfg["paths"]["nontrending_csv"],
                         ["id", "date", "time", "language", "hashtags",
                          "username", "mentions", "reply_to"], cfg):
            for i, d, tm, lg, hs, u, men, rep in zip(
                    ch["id"].values, ch["date"].values, ch["time"].values,
                    ch["language"].values, ch["hashtags"].values,
                    ch["username"].values, ch["mentions"].values,
                    ch["reply_to"].values, strict=False):
                if feat_lang and lg != feat_lang:
                    continue
                b = band.bin_of(d, tm)
                if b is None:
                    continue
                for topic in parse_hashtags(hs):
                    if topic in neg:
                        keep(topic, i, b, u, men, rep)

    return out


# ---------------------------------------------------------------------------
# Graph construction + features
# ---------------------------------------------------------------------------
def build_graph(records) -> nx.DiGraph:
    """Directed author -> target graph, parallel edges collapsed to weight."""
    G = nx.DiGraph()
    for _b, author, targets in records:
        G.add_node(author)
        for tgt in targets:
            if G.has_edge(author, tgt):
                G[author][tgt]["w"] += 1
            else:
                G.add_edge(author, tgt, w=1)
    return G


def _gini(x: np.ndarray) -> float:
    if len(x) == 0:
        return 0.0
    x = np.sort(np.asarray(x, dtype=float))
    total = x.sum()
    if total <= 0:
        return 0.0
    cum = np.cumsum(x)
    return float(1 - 2 * cum.sum() / (cum[-1] * len(x)) + 1 / len(x))


def prototype_features(G: nx.DiGraph, n_tweets: int) -> dict:
    """The 14 structural features validated in the prototype."""
    N, E = G.number_of_nodes(), G.number_of_edges()
    f = {
        "n_nodes": N,
        "n_edges": E,
        "density": nx.density(G) if N > 1 else 0.0,
        "edges_per_tweet": E / n_tweets if n_tweets else 0.0,
    }
    if N < 2:
        for k in ["max_in_degree", "mean_in_degree", "max_out_degree",
                  "n_components", "largest_wcc_frac", "mean_component_size",
                  "reciprocity", "pagerank_gini", "max_pagerank",
                  "mean_clustering"]:
            f[k] = 0.0
        return f

    indeg = np.array([d for _, d in G.in_degree()])
    outdeg = np.array([d for _, d in G.out_degree()])
    f["max_in_degree"] = float(indeg.max())
    f["mean_in_degree"] = float(indeg.mean())
    f["max_out_degree"] = float(outdeg.max())

    sizes = sorted((len(c) for c in nx.weakly_connected_components(G)),
                   reverse=True)
    f["n_components"] = len(sizes)
    f["largest_wcc_frac"] = sizes[0] / N
    f["mean_component_size"] = float(np.mean(sizes))

    try:
        f["reciprocity"] = float(nx.reciprocity(G) or 0.0)
    except Exception:
        f["reciprocity"] = 0.0
    try:
        pr = np.array(list(nx.pagerank(G, max_iter=100).values()))
        f["pagerank_gini"] = _gini(pr)
        f["max_pagerank"] = float(pr.max())
    except Exception:
        f["pagerank_gini"] = 0.0
        f["max_pagerank"] = 0.0
    try:
        f["mean_clustering"] = float(nx.average_clustering(G.to_undirected()))
    except Exception:
        f["mean_clustering"] = 0.0
    return f


def centrality_features(G: nx.DiGraph, cfg: dict) -> dict:
    """Betweenness — brokerage between otherwise disconnected groups.

    Exact betweenness is O(V*E); above `betweenness_k` nodes we sample pivots,
    seeded so the result is reproducible.

    Whether the exact algorithm ran is recorded as METADATA, not as a feature.
    It is a deterministic function of graph size, so modelling it would smuggle
    a thresholded node count into the matrix under a structural-sounding name —
    it separated the classes at AUC 0.79 on the first run purely for that
    reason.
    """
    N = G.number_of_nodes()
    if N < 3 or G.number_of_edges() == 0:
        return {"max_betweenness": 0.0, "mean_betweenness": 0.0,
                "betweenness_gini": 0.0, META_PREFIX + "betweenness_exact": 1}
    k = cfg["network"]["betweenness_k"]
    exact = k is None or N <= k
    try:
        bc = nx.betweenness_centrality(
            G, k=None if exact else k, normalized=True,
            seed=None if exact else cfg["seed"])
    except Exception:
        return {"max_betweenness": 0.0, "mean_betweenness": 0.0,
                "betweenness_gini": 0.0,
                META_PREFIX + "betweenness_exact": int(exact)}
    v = np.array(list(bc.values()))
    return {"max_betweenness": float(v.max()),
            "mean_betweenness": float(v.mean()),
            "betweenness_gini": _gini(v),
            META_PREFIX + "betweenness_exact": int(exact)}


def kcore_features(G: nx.DiGraph) -> dict:
    """k-core decomposition — how deep the densely-engaged core runs.

    Computed on the simple undirected projection; self-loops removed because
    core_number is undefined with them.
    """
    U = nx.Graph(G.to_undirected())
    U.remove_edges_from(nx.selfloop_edges(U))
    if U.number_of_nodes() == 0 or U.number_of_edges() == 0:
        return {"max_core": 0.0, "mean_core": 0.0, "core2_frac": 0.0,
                "core3_frac": 0.0}
    core = nx.core_number(U)
    v = np.array(list(core.values()), dtype=float)
    return {"max_core": float(v.max()),
            "mean_core": float(v.mean()),
            "core2_frac": float((v >= 2).mean()),
            "core3_frac": float((v >= 3).mean())}


def community_features(G: nx.DiGraph, cfg: dict) -> dict:
    """Louvain communities — Weng et al. (2013) predict trending from how far
    a topic escapes its originating community."""
    U = nx.Graph(G.to_undirected())
    U.remove_edges_from(nx.selfloop_edges(U))
    N = U.number_of_nodes()
    if N < 2 or U.number_of_edges() == 0:
        return {"n_communities": 0.0, "modularity": 0.0,
                "largest_community_frac": 0.0, "community_entropy": 0.0}
    try:
        comms = nx.community.louvain_communities(
            U, resolution=cfg["network"]["louvain_resolution"],
            seed=cfg["seed"])
        mod = nx.community.modularity(U, comms)
    except Exception:
        return {"n_communities": 0.0, "modularity": 0.0,
                "largest_community_frac": 0.0, "community_entropy": 0.0}
    sizes = np.array(sorted((len(c) for c in comms), reverse=True), dtype=float)
    p = sizes / sizes.sum()
    entropy = float(-(p * np.log(p)).sum())
    return {"n_communities": float(len(sizes)),
            "modularity": float(mod),
            "largest_community_frac": float(sizes[0] / N),
            "community_entropy": entropy}


def growth_features(records, win_start: int, win_end: int, cfg: dict) -> dict:
    """How fast the graph accretes across the window.

    The window is cut into equal slices and the graph rebuilt cumulatively.
    Slopes are normalised by the final value so they measure shape, not size —
    otherwise this would smuggle raw volume back in as a feature.
    """
    slices = cfg["network"]["growth_slices"]
    edges = np.linspace(win_start, win_end, slices + 1).astype(int)
    n_nodes, n_edges, authors_seen = [], [], []
    seen_authors: set[str] = set()
    for s in range(slices):
        upto = edges[s + 1]
        sub = [r for r in records if r[0] < upto]
        G = build_graph(sub)
        n_nodes.append(G.number_of_nodes())
        n_edges.append(G.number_of_edges())
        seen_authors |= {a for _b, a, _t in sub}
        authors_seen.append(len(seen_authors))

    final_n = max(n_nodes[-1], 1)
    final_e = max(n_edges[-1], 1)
    x = np.arange(slices, dtype=float)

    def slope(y, denom):
        y = np.asarray(y, dtype=float)
        if len(y) < 2 or np.allclose(y, y[0]):
            return 0.0
        return float(np.polyfit(x, y / denom, 1)[0])

    last_slice = [r for r in records if r[0] >= edges[-2]]
    new_authors = {a for _b, a, _t in last_slice} - {
        a for _b, a, _t in records if _b < edges[-2]}
    return {
        "node_growth_slope": slope(n_nodes, final_n),
        "edge_growth_slope": slope(n_edges, final_e),
        "author_growth_slope": slope(authors_seen, max(authors_seen[-1], 1)),
        "edge_node_ratio_final": final_e / final_n,
        "new_author_frac_last_slice": (len(new_authors) / final_n
                                       if final_n else 0.0),
    }


def window_volume_features(records) -> dict:
    """Volume, computed from the WINDOW only.

    Deliberately excludes any whole-topic count. The prototype's top feature
    was the topic's all-day total, which in a pre-peak setting is a proxy for
    the peak being predicted.
    """
    authors = {a for _b, a, _t in records}
    n = len(records)
    bins = [b for b, _a, _t in records]
    span = (max(bins) - min(bins) + 1) if bins else 1
    return {
        "window_tweets": float(n),
        "unique_users": float(len(authors)),
        "tweets_per_user": n / len(authors) if authors else 0.0,
        "tweets_per_active_bin": n / span if span else 0.0,
        "active_bin_frac": len(set(bins)) / span if span else 0.0,
    }


def features_for_unit(row, records, cfg: dict) -> dict:
    G = build_graph(records)
    f = {"topic": row.topic, "label": int(row.label)}
    f.update(window_volume_features(records))
    f.update(prototype_features(G, len(records)))
    f.update(centrality_features(G, cfg))
    f.update(kcore_features(G))
    f.update(community_features(G, cfg))
    f.update(growth_features(records, row.window_start_bin,
                             row.window_end_bin, cfg))
    # Diagnostics only — the meta_ prefix keeps these out of any feature matrix.
    f[META_PREFIX + "peak_bin"] = row.peak_bin
    f[META_PREFIX + "peak_clock"] = row.peak_clock
    f[META_PREFIX + "window_start_clock"] = row.window_start_clock
    f[META_PREFIX + "window_end_clock"] = row.window_end_clock
    f[META_PREFIX + "total_band_tweets"] = row.total_band_tweets
    f[META_PREFIX + "n_window_tweets_all_langs"] = row.n_window_tweets_all_langs
    return f


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Modellable columns: everything that is not an identifier or meta_."""
    return [c for c in df.columns
            if c not in ("topic", "label") and not c.startswith(META_PREFIX)]


def main() -> int:
    t0 = time.time()
    cfg = load_config()
    band = band_from_config(cfg)
    units_path = f"{cfg['paths']['cache']}/units.csv"
    units = pd.read_csv(units_path)
    print(f"Loaded {len(units)} units from {units_path} "
          f"({int(units.label.sum())} trending / "
          f"{int((1 - units.label).sum())} non-trending)")
    print(f"Feature language: {cfg['language']['feature_language']!r}\n")

    print("Collecting window tweets ...")
    tweets = collect_window_tweets(cfg, band, units)
    print(f"  collected for {len(tweets)} units ({time.time() - t0:.0f}s)\n")

    rows, empty = [], []
    for row in units.itertuples():
        recs = tweets.get(row.topic, [])
        if not recs:
            empty.append(row.topic)
            continue
        rows.append(features_for_unit(row, recs, cfg))
    df = pd.DataFrame(rows)
    if empty:
        print(f"WARNING: {len(empty)} units had no tweets collected: "
              f"{empty[:10]}", file=sys.stderr)

    feats = feature_columns(df)
    out = f"{cfg['paths']['cache']}/network_features.csv"
    df.to_csv(out, index=False)

    print(f"FEATURE MATRIX: {len(df)} units x {len(feats)} features "
          f"({int(df.label.sum())} trending / {int((1 - df.label).sum())} "
          f"non-trending, prevalence {df.label.mean():.3f})\n")

    # Per-feature summary with a direction-agnostic univariate separation, so
    # obviously-dead features surface now rather than at model time.
    print(f"{'feature':<30}{'mean(+)':>11}{'mean(-)':>11}{'zeros%':>8}{'AUC':>7}")
    print("-" * 67)
    summary = {}
    y = df["label"].values
    for c in feats:
        v = df[c].values.astype(float)
        mp = float(v[y == 1].mean())
        mn = float(v[y == 0].mean())
        zeros = float((v == 0).mean())
        if len(np.unique(v)) > 1:
            from sklearn.metrics import roc_auc_score
            auc = roc_auc_score(y, v)
            auc = max(auc, 1 - auc)
        else:
            auc = 0.5
        summary[c] = {"mean_trending": mp, "mean_non_trending": mn,
                      "zero_frac": zeros, "univariate_auc": float(auc)}
        print(f"{c:<30}{mp:>11.3f}{mn:>11.3f}{zeros:>8.1%}{auc:>7.3f}")

    top = sorted(summary.items(), key=lambda kv: -kv[1]["univariate_auc"])[:8]
    print("\nTop univariate separators:")
    for c, d in top:
        print(f"   {c:<30} AUC={d['univariate_auc']:.3f}")

    with open(f"{cfg['paths']['tables']}/network_feature_summary.json", "w",
              encoding="utf-8") as fh:
        json.dump({"n_units": len(df), "n_features": len(feats),
                   "prevalence": float(df.label.mean()),
                   "features": feats, "summary": summary,
                   "units_with_no_tweets": empty,
                   "config_network": cfg["network"], "seed": cfg["seed"]},
                  fh, indent=2, ensure_ascii=False)
    print(f"\nWrote {out}")
    print(f"Wrote {cfg['paths']['tables']}/network_feature_summary.json")
    print(f"Total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
