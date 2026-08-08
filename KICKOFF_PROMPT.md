# Kickoff prompt — paste this as your first message to Claude Code

> Prerequisite: put `CLAUDE.md` in the repo root, the two CSVs under `dataset/`, and the two prototype scripts under `prototype/`.

---

Read `CLAUDE.md` first — it has the full project context, the data gotchas, and the prototype results you must not regress.

I'm continuing a final-year data science project. The network-diffusion feature channel is already built and validated as a prototype (see `prototype/`). Now I'm building the full pipeline: proper pre-peak topic units, plus the temporal and sentiment channels, then the fusion model and evaluation.

**Do not write the whole pipeline in one go.** Work in the order below, and stop after each step so I can check the output before you continue.

**Step 1 — orient.** Read `prototype/prototype_extract.py` and `prototype/prototype_eval.py` so you know what exists. Then confirm the dataset files are present and print the actual column names and row counts. Don't trust the numbers in `CLAUDE.md` — verify them and tell me about any mismatch.

**Step 2 — scaffold.** Set up the repo layout from `CLAUDE.md`, plus `config.yaml` holding every tunable (bin size, lead-time window, min topic size, seeds, paths). No magic numbers inside code.

**Step 3 — the critical path: `src/data/units.py`.** This is the most important piece and everything else depends on it. It must:
- stream both CSVs (chunked — do not load whole files) and clean as it goes (strip the `.csv` suffix from `trend`, drop malformed rows, de-duplicate);
- bin each topic's activity into fixed time bins and identify its peak (max-volume bin);
- **exclude left-censored topics** — anything already at or past peak when collection starts, i.e. whose rising phase isn't observed. Report how many topics survive this filter;
- emit `(topic, window)` units where the window ends a configurable 1–3 hours **before** the peak, so features only ever see pre-peak data;
- build negatives from non-trending hashtags that never trended;
- print a summary: topics in / topics surviving / class balance / per-language breakdown.

Then tell me how many usable topics we have. **If the count is too low to model, stop and tell me** — the fallbacks are in `CLAUDE.md` §Contingency (widen window, define peak relative to available span, or reframe as early-escalation vs non-escalation). I want to decide that with you, not have you silently pick one.

**Step 4 — language balancing + negative control.** Implement class balancing by language in `src/data/cleaning.py`, and a language-only classifier in `src/eval/` that *should fail*. If a language-only model performs well on our units, the confound isn't controlled and we fix it before going further.

Stop after Step 4 and show me the numbers. Then we'll do the network refactor, sentiment, temporal, fusion and evaluation in turn.

Constraints to respect throughout: stream everything, `n_jobs=1`, cache expensive intermediates (especially sentiment) to disk, set seeds, and never invent a number.
