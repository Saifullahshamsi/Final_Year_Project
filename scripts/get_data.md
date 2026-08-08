# Obtaining and placing the dataset

The corpus is **not** in this repository. It is ~1.2 GB, and republishing raw
tweet text would breach the Twitter/X terms it was collected under. The
pipeline is fully reproducible by anyone who holds the same corpus.

## What the dataset is

Two CSVs scraped with [`twint`](https://github.com/twintproject/twint),
covering a single day, **2020-02-25**.

| File | Size | Rows (verified) | Contents |
|---|---|---|---|
| `tweets_25_tendencia_raw.csv` | 668 MB | 1,275,917 | tweets belonging to a labelled **trending** topic |
| `tweets_25_notendencias_raw.csv` | 558 MB | 1,090,280 | tweets **not** belonging to any trending topic |

## Where to put it

```
trend-emergence/
└── dataset/
    ├── tweets_25_tendencia_raw.csv
    └── tweets_25_notendencias_raw.csv
```

Paths are configured in [`config.yaml`](../config.yaml) under `paths:` and
resolve relative to the repository root, so no code changes are needed.

## Schema

Both files use the twint column set. The trending file adds a `trend` column;
the non-trending file **has no `trend` column** — negative topic identity comes
from `hashtags` alone. Both carry two index-like columns (`Unnamed: 0.1` and
`Unnamed: 0`) in *different positions*, so always select columns by name.

```
Unnamed: 0.1, id, conversation_id, created_at, date, time, timezone, user_id,
username, name, place, tweet, language, mentions, urls, photos, replies_count,
retweets_count, likes_count, hashtags, cashtags, link, retweet, quote_url,
video, thumbnail, near, geo, source, user_rt_id, user_rt, retweet_id, reply_to,
retweet_date, translate, trans_src, trans_dest, trend, Unnamed: 0
```

Columns this project reads: `id, trend, date, time, language, username,
mentions, reply_to, hashtags`.

## Quirks the loaders must handle

These are verified properties of the files, not guesses. `src/data/loading.py`
handles all of them; see [`FINDINGS.md`](../FINDINGS.md) for how each was found.

1. **`trend` labels arrive in three mixed forms.** Of 322 distinct names, 83
   end in `.csv`, 137 start with `#`, 25 do both, the rest are bare. Normalise
   with `clean_topic()` before *any* comparison.
2. **`mentions` / `reply_to` are stringified Python lists of dicts.** Parse with
   `ast.literal_eval`, read `screen_name`, lowercase.
3. **Retweet capture is broken** — `retweet`, `retweet_id`, `user_rt` are mostly
   empty. The interaction graph is built from mentions and replies only.
4. **The two files cover different hours.** Only `16:00–23:59` is covered by
   both. All modelling is restricted to that band.
5. **De-duplicate on `(id, topic)`, never `id` alone** — one tweet legitimately
   belongs to several trends.
6. A handful of malformed rows exist (3 trending, 1 non-trending). Read with
   `on_bad_lines="skip"`.

## Verifying your copy

```bash
python -m src.data.units --sweep
```

Should report `1,275,917` and `1,090,280` rows scanned, `322` trending topics
and `76,705` candidate non-trending hashtags on the band grid. Different
numbers mean a different corpus.
