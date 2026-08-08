#!/usr/bin/env python3
"""
Prototype: network-diffusion feature extractor for trend-emergence prediction.

For each topic (a hashtag), takes the first WINDOW seconds of activity from the
topic's first observed tweet, builds a directed user-interaction graph from
mentions and replies (NOT retweets, whose capture is weak in this corpus), and
computes graph-structural features. Trending hashtags -> label 1, non-trending
hashtags -> label 0.
"""
import pandas as pd, numpy as np, ast, time, json
import networkx as nx

TREND = "/tmp/ds/dataset/tweets_25_tendencia_raw.csv"
NONTR = "/tmp/ds/dataset/tweets_25_notendencias_raw.csv"
K_EARLY = 150          # build the graph from each topic's EARLIEST 150 tweets
MIN_TOTAL = 150        # topic must have >= this many tweets overall (so early sample is full)
N_PER_CLASS = 140      # target topics per class
CHUNK = 300000

def to_sec(s):
    try:
        h, m, sec = s.split(":")
        return int(h) * 3600 + int(m) * 60 + int(sec)
    except Exception:
        return None

def screen_names(cell):
    """Parse a twint mentions/reply_to cell -> list of lowercased screen_names."""
    if not isinstance(cell, str) or cell in ("", "[]", "nan"):
        return []
    try:
        lst = ast.literal_eval(cell)
    except Exception:
        return []
    out = []
    if isinstance(lst, list):
        for d in lst:
            if isinstance(d, dict) and d.get("screen_name"):
                out.append(str(d["screen_name"]).lower())
    return out

# ---------- PASS A: per-topic count + min second ----------
def scan_trend_counts():
    cnt, mins = {}, {}
    for ch in pd.read_csv(TREND, usecols=["trend", "time"], chunksize=CHUNK,
                          dtype=str, on_bad_lines="skip", engine="c"):
        ch["sec"] = ch["time"].map(to_sec)
        for tr, sc in zip(ch["trend"].values, ch["sec"].values):
            if not isinstance(tr, str) or sc is None:
                continue
            cnt[tr] = cnt.get(tr, 0) + 1
            if tr not in mins or sc < mins[tr]:
                mins[tr] = sc
    return cnt, mins

def scan_nontrend_counts(exclude):
    cnt, mins = {}, {}
    for ch in pd.read_csv(NONTR, usecols=["hashtags", "time"], chunksize=CHUNK,
                          dtype=str, on_bad_lines="skip", engine="c"):
        secs = ch["time"].map(to_sec).values
        for hs, sc in zip(ch["hashtags"].values, secs):
            if sc is None or not isinstance(hs, str) or hs in ("", "[]"):
                continue
            try:
                tags = ast.literal_eval(hs)
            except Exception:
                continue
            if not isinstance(tags, list):
                continue
            for t in tags:
                t = str(t).lower()
                key = "#" + t
                if key in exclude:        # skip anything that actually trended
                    continue
                cnt[key] = cnt.get(key, 0) + 1
                if key not in mins or sc < mins[key]:
                    mins[key] = sc
    return cnt, mins

t0 = time.time()
print("Pass A: trending counts ...")
tr_cnt, tr_min = scan_trend_counts()
trend_names = set(n.lower() for n in tr_cnt)           # for exclusion in negatives
print(f"  {len(tr_cnt)} trends, {time.time()-t0:.0f}s")

print("Pass A2: non-trending hashtag counts ...")
nt_cnt, nt_min = scan_nontrend_counts(trend_names)
print(f"  {len(nt_cnt)} candidate non-trending hashtags, {time.time()-t0:.0f}s")

# ---------- selection ----------
def pick(cnt, target):
    elig = [k for k, c in cnt.items() if c >= MIN_TOTAL]
    elig.sort(key=lambda k: -cnt[k])
    # stratified across the size range: take evenly spaced ranks for diversity
    if len(elig) <= target:
        return set(elig)
    idx = np.linspace(0, len(elig) - 1, target).astype(int)
    return set(elig[i] for i in idx)

sel_tr = pick(tr_cnt, N_PER_CLASS)
sel_nt = pick(nt_cnt, N_PER_CLASS)
print(f"Selected {len(sel_tr)} trending, {len(sel_nt)} non-trending topics")

# ---------- PASS B: keep each topic's EARLIEST K tweets (bounded max-heaps) ----------
import heapq
def push_early(heap, sec, payload, ctr):
    # max-heap on sec via negation; keep only K_EARLY smallest secs
    if len(heap) < K_EARLY:
        heapq.heappush(heap, (-sec, ctr, payload))
    elif -heap[0][0] > sec:
        heapq.heapreplace(heap, (-sec, ctr, payload))

def collect_trend(sel):
    heaps = {k: [] for k in sel}
    ctr = 0
    for ch in pd.read_csv(TREND, usecols=["trend", "time", "username", "mentions", "reply_to"],
                          chunksize=CHUNK, dtype=str, on_bad_lines="skip", engine="c"):
        ch["sec"] = ch["time"].map(to_sec)
        sub = ch[ch["trend"].isin(sel)]
        for tr, sc, u, men, rep in zip(sub["trend"], sub["sec"], sub["username"],
                                        sub["mentions"], sub["reply_to"]):
            if sc is None:
                continue
            ctr += 1
            push_early(heaps[tr], sc, (str(u).lower(), men, rep), ctr)
    return heaps

def collect_nontrend(sel):
    heaps = {k: [] for k in sel}
    sel_tags = {k[1:] for k in sel}
    ctr = 0
    for ch in pd.read_csv(NONTR, usecols=["hashtags", "time", "username", "mentions", "reply_to"],
                          chunksize=CHUNK, dtype=str, on_bad_lines="skip", engine="c"):
        ch["sec"] = ch["time"].map(to_sec)
        for hs, sc, u, men, rep in zip(ch["hashtags"], ch["sec"], ch["username"],
                                        ch["mentions"], ch["reply_to"]):
            if sc is None or not isinstance(hs, str) or hs in ("", "[]"):
                continue
            try:
                tags = [str(t).lower() for t in ast.literal_eval(hs)]
            except Exception:
                continue
            hit = sel_tags.intersection(tags)
            if not hit:
                continue
            ctr += 1
            payload = (str(u).lower(), men, rep)
            for t in hit:
                push_early(heaps["#" + t], sc, payload, ctr)
    return heaps

def heap_to_store(heaps, total_cnt):
    store = {}
    for k, hp in heaps.items():
        items = sorted(hp)  # ascending by -sec -> latest first; order irrelevant for graph
        src, edges = [], []
        for negsec, ctr, payload in items:
            u, men, rep = payload
            src.append(u)
            for tgt in screen_names(men) + screen_names(rep):
                if tgt and tgt != u:
                    edges.append((u, tgt))
        store[k] = {"src": src, "edges": edges, "n": len(items), "total": total_cnt.get(k, len(items))}
    return store

print("Pass B: collecting trending earliest tweets ...")
tr_store = heap_to_store(collect_trend(sel_tr), tr_cnt)
print(f"  done, {time.time()-t0:.0f}s")
print("Pass B2: collecting non-trending earliest tweets ...")
nt_store = heap_to_store(collect_nontrend(sel_nt), nt_cnt)
print(f"  done, {time.time()-t0:.0f}s")

# ---------- feature extraction ----------
def features(d):
    n_tweets = d["n"]
    authors = set(d["src"])
    edges = d["edges"]
    G = nx.DiGraph()
    G.add_nodes_from(authors)
    for s, t in edges:
        if G.has_edge(s, t):
            G[s][t]["w"] += 1
        else:
            G.add_edge(s, t, w=1)
    N = G.number_of_nodes()
    E = G.number_of_edges()
    feat = {
        "total_count": d["total"],
        "tweet_count": n_tweets,
        "unique_users": len(authors),
        "n_nodes": N,
        "n_edges": E,
        "density": nx.density(G) if N > 1 else 0.0,
        "edges_per_tweet": E / n_tweets if n_tweets else 0.0,
    }
    if N >= 2:
        indeg = np.array([dg for _, dg in G.in_degree()])
        outdeg = np.array([dg for _, dg in G.out_degree()])
        feat["max_in_degree"] = int(indeg.max())
        feat["mean_in_degree"] = float(indeg.mean())
        feat["max_out_degree"] = int(outdeg.max())
        # weakly connected components
        wccs = list(nx.weakly_connected_components(G))
        sizes = sorted((len(c) for c in wccs), reverse=True)
        feat["n_components"] = len(wccs)
        feat["largest_wcc_frac"] = sizes[0] / N
        feat["mean_component_size"] = float(np.mean(sizes))
        # reciprocity (guard for no edges)
        try:
            feat["reciprocity"] = nx.reciprocity(G) or 0.0
        except Exception:
            feat["reciprocity"] = 0.0
        # PageRank concentration (gini) -> hub dominance
        try:
            pr = np.array(list(nx.pagerank(G, max_iter=100).values()))
            pr.sort()
            cum = np.cumsum(pr)
            gini = 1 - 2 * np.sum(cum) / (cum[-1] * len(pr)) + 1 / len(pr) if cum[-1] > 0 else 0.0
            feat["pagerank_gini"] = float(gini)
            feat["max_pagerank"] = float(pr.max())
        except Exception:
            feat["pagerank_gini"] = 0.0; feat["max_pagerank"] = 0.0
        # clustering of undirected projection
        try:
            feat["mean_clustering"] = nx.average_clustering(G.to_undirected())
        except Exception:
            feat["mean_clustering"] = 0.0
    else:
        for k in ["max_in_degree","mean_in_degree","max_out_degree","n_components",
                  "largest_wcc_frac","mean_component_size","reciprocity",
                  "pagerank_gini","max_pagerank","mean_clustering"]:
            feat[k] = 0.0
    return feat

rows = []
for store, label in [(tr_store, 1), (nt_store, 0)]:
    for topic, d in store.items():
        if d["n"] < 30:          # need a minimum of early activity to form a graph
            continue
        f = features(d)
        f["topic"] = topic
        f["label"] = label
        rows.append(f)

df = pd.DataFrame(rows)
df.to_csv("/tmp/topic_features.csv", index=False)
print(f"\nFinal dataset: {len(df)} topics "
      f"({int(df.label.sum())} trending / {int((1-df.label).sum())} non-trending)")
print("Features:", [c for c in df.columns if c not in ("topic","label")])
print(f"Total time {time.time()-t0:.0f}s")
