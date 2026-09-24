# Literature 2023–2026 — candidate sources for the revised review

Review feedback on both the preliminary and draft reports said the same thing:
the literature review has nothing later than a 2022 conference paper, and is
limited in scope as well as in time. This file is a **search result, not a
chapter** — each entry says what the source claims and where it would sit in
the report, so the writing stays yours.

Ordered by how directly each one bears on a decision this project actually
made. The sources in §C, §D and §E matter most: they are the ones that let the
review engage critically with work that **disagrees** with choices made here,
which is a separate marking criterion from merely knowing the field.

**Verification status is marked on every entry.** `[verified]` means the paper
page was fetched and the title, authors and year read off it. `[search-only]`
means it came back in search results and the bibliographic details have **not**
been confirmed — resolve the DOI before citing. Do not cite a `[search-only]`
entry without checking it.

---

## A. Closest prior work — topic-level trend prediction

### Wu, Z., Liao, Y., Luo, C., Shi, J., & Yang, Y. (2025)
*Predicting emerging trends: a machine learning approach to topic popularity on
social media.* PeerJ Computer Science, 11:e3245. `[search-only — confirm the
author list and article number]`
<https://peerj.com/articles/cs-3245/>

The nearest neighbour to this project in the recent literature: unit of
analysis is a **topic**, the task is framed as **binary classification** of
whether a topic will become popular, and the features combine traditional,
temporal and textual channels, compared across several models.

**Where it goes:** the review's "gap" argument, and the design chapter. It is
the strongest single citation available for the claim that topic-level
prediction is a live problem rather than a solved one. It also sharpens the
gap: it classifies topic popularity, but does not condition on a **lead time
before peak**, which is where this project differs. State that difference
precisely — a reviewer who knows this paper will check whether the gap claimed
is the gap that exists.

### Xu, Y., Wu, J., Wan, H., Li, Y., Hou, Z., & Kan, M.-Y. (2025)
*Forecasting the Buzz: Enriching Hashtag Popularity Prediction with LLM
Reasoning.* arXiv:2510.08481. `[verified]`

BuzzProphet: an LLM articulates topical virality, audience reach and timing
advantage as text, and those rationales are fed into classical tabular
regressors. Reports up to 2.8% RMSE reduction and ~30% correlation improvement
over baselines on a 7,532-hashtag benchmark.

**Where it goes:** the review (current direction of the field) and the
conclusion's further-work section. Note the modest headline gain — 2.8% RMSE —
alongside this project's own finding that fusion did not beat a well-specified
volume baseline. Two independent observations that the marginal return on added
signal in this task is small.

---

## B. Modern cascade and popularity prediction — context for the network channel

### Survey of deep-learning-based information cascade prediction (2024)
*Symmetry*, 16(11):1436. `[search-only — MDPI blocked the fetch; confirm
authors and article number via DOI]`
<https://www.mdpi.com/2073-8994/16/11/1436>

**Where it goes:** the review's structural-signals section, as the up-to-date
replacement for citing Weng et al. (2013) alone. A 2024 survey is the cheapest
way to demonstrate currency across a whole subfield.

### HierCas: Hierarchical Temporal Graph Attention Networks for Popularity Prediction in Information Cascades
IJCNN 2024. arXiv:2310.13219. `[search-only]`

### Multi-view temporal graph neural network for miniature cascade popularity prediction (2025)
*The Journal of Supercomputing.* `[search-only]`

Both are GNN-based cascade models. The second is worth reading specifically
because it targets **sparse and small cascades** — the regime this project
found itself in, and documented as a limitation.

**Where it goes:** the design chapter's justification for *not* using a GNN,
and the further-work section. This project has 129 units; these models are
trained on cascade corpora orders of magnitude larger. Citing them makes the
"no deep sequence model" decision an informed choice rather than an omission.

### Goel, S., Anderson, A., Hofman, J., & Watts, D. J. (2016)
*The Structural Virality of Online Diffusion.* Management Science, 62(1).
`[search-only]`

Older, but it is the canonical formalisation of structural virality and it
pairs with Weng et al. (2013) and Cheng et al. (2014), which are already cited.
Include only if the review needs the structural-vs-broadcast distinction; do
not pad the currency problem with more pre-2022 work.

---

## C. The language confound has a name in the literature — use it

This is the highest-value section. The project's central unresolved limitation
is currently described in its own terms. It is a well-studied phenomenon with
an established vocabulary, and naming it correctly converts a confession into
an analysis.

### Steinmann, D., Divo, F., Kraus, M., Wüst, A., Struppek, L., Friedrich, F., & Kersting, K. (2024)
*Navigating Shortcuts, Spurious Correlations, and Confounders: From Origins via
Detection to Mitigation.* arXiv:2412.05152. `[verified]`

Gives a formal definition of a shortcut and a unifying taxonomy across the
scattered terminology (shortcut / spurious correlation / confounder / dataset
artifact), organised as origins → detection → mitigation, with links to bias
and causality.

**Where it goes:** the evaluation chapter, at the language-confound section,
and the review. The language confound in this corpus is a textbook **shortcut
with a collection-process origin**: Spanish share predicts the label at PR-AUC
0.897 without carrying any information about trend dynamics. The taxonomy also
supplies the structure this project's own control hierarchy already followed
without naming it — detection (the language-only classifier), then attempted
mitigation (topic-level matching, tweet-level filtering, within-language
restriction), then the finding that mitigation is unavailable because the
origin is in data collection, not in modelling.

### Navigating the Shortcut Maze: A Comprehensive Analysis of Shortcut Learning in Text Classification by Language Models (2024)
arXiv:2409.17455. `[search-only]`

### Explore Spurious Correlations at the Concept Level in Language Models for Text Classification
ACL 2024. arXiv:2311.08648. `[search-only]`

Either supports the narrower point that text classifiers latch onto
surface-level regularities that correlate with labels without reflecting the
task. Cite one, not both.

**The argument this section enables:** the project reports a negative control
that failed. Framed as shortcut learning with a documented origin, the failure
becomes a measured, diagnosed and bounded limitation — and the demonstration
that all three mitigations are impossible on this corpus is itself a result
about the corpus.

---

## D. The evaluation metric choice is contested — say so

### McDermott, M. B. A., Zhang, H., Hansen, L. H., Angelotti, G., & Gallifant, J. (2024)
*A Closer Look at AUROC and AUPRC under Class Imbalance.* NeurIPS 2024.
arXiv:2401.06091. `[verified]`

Directly refutes the widespread claim that AUPRC is superior to AUROC under
class imbalance. Argues AUPRC is not generally superior, and can be **harmful**,
because it unduly favours model improvements in subpopulations with more
frequent positive labels, which can widen algorithmic disparities.

**Where it goes:** the evaluation chapter, immediately after the existing
Saito & Rehmsmeier (2015) justification for PR-AUC. **This is the single most
valuable source in this file**, because the marking criteria reward *critical*
engagement with literature, not just coverage — and this paper argues against a
decision already made and defended in the draft.

What it does **not** do is invalidate the choice here. The report can hold both
positions honestly:

- Saito & Rehmsmeier's argument still applies to the original problem: a large
  negative pool suppresses FPR, so ROC-AUC flatters a model with poor precision.
- McDermott et al.'s objection is about **cross-subpopulation comparison** and
  about treating AUPRC as a universal default.
- This project reports PR-AUC, ROC-AUC, F1, precision and recall side by side
  in every table, and — critically — **the headline H1 conclusion does not rest
  on either curve metric.** It rests on an exact McNemar test on paired
  out-of-fold decisions, which is insensitive to this entire dispute.

That last point is worth making explicitly: after the ARIMA re-run the PR-AUC
gap and the decision-level test actively disagree (0.051 apart on PR-AUC, an
exact 10–10 tie on McNemar), and the report already states that McNemar is the
one to trust. This paper is the citation that justifies that preference rather
than merely asserting it.

---

## E. "Fusion did not beat the baseline" is a known and respected result

Review feedback did not ask for this, but the H1 null is the project's main
finding and it should be positioned inside a literature that takes such results
seriously — otherwise it reads as a failed experiment.

### Ferrari Dacrema, M., Boglio, S., Cremonesi, P., & Jannach, D. (2021)
*A Troubling Analysis of Reproducibility and Progress in Recommender Systems
Research.* ACM TOIS. arXiv:1911.07698. `[search-only — this is the extended
journal version of the RecSys 2019 paper; check which version to cite]`

11 of 12 reproducible neural approaches were outperformed by conceptually
simple methods — nearest-neighbour heuristics or linear models — once the
baselines were properly tuned. Names the causes: **weak baselines**,
insufficient hyperparameter tuning, and problematic evaluation practice.

**Where it goes:** the evaluation chapter, at the `volume_extended` decision,
and the conclusion. This is the literature's strongest statement of the
principle this project independently arrived at — that **baseline specification
determines the conclusion**. Against a 3-feature `volume_only` baseline, fusion
wins at p = 0.0041 and H1 "passes". Against `volume_extended`, which holds the
33 features the size-proxy audit disqualified from the other channels, it ties
at p = 1.0000. Same model, same data, opposite conclusion.

Note the direction of the contribution: this project **built the strong
baseline against itself**, which is the practice Dacrema et al. found missing.
That is a methodological strength to claim explicitly, not a mishap to explain.

### Deep-learning-based gene perturbation effect prediction does not yet outperform simple linear baselines (2025)
PMC12328236. `[search-only]`

Optional. A second field reaching the same conclusion supports the general
claim; drop it if the word budget is tight, since it is far from the domain.

---

## F. Multilingual sentiment — the XLM-T lineage

### Barbieri, F., Espinosa Anke, L., & Camacho-Collados, J. (2022)
*XLM-T: Multilingual Language Models in Twitter for Sentiment Analysis and
Beyond.* LREC 2022. arXiv:2104.12250. `[search-only — already the model's own
citation; verify the LREC page numbers]`

The model actually used here, at pinned revision
`f2f1202b1bdeb07342385c3f807f9c07cd8f5cf8`. XLM-R further-pretrained on 198M
tweets across 30+ languages.

### Fine-tuning multilingual language models in Twitter/X sentiment analysis: a study on Eastern-European V4 languages (2024)
arXiv:2408.02044. `[search-only]`

Recent external evaluation. Reports XLM-T slightly underperforming monolingual
models such as BERTweet and TimeLMs, while remaining state of the art **among
multilingual Twitter-specific models**.

**Where it goes:** the design chapter's model-selection justification. It is a
better citation than the model card because it is an independent evaluation,
and because it states the trade-off honestly: a monolingual model would score
higher per language, but the corpus here is multilingual by construction, so a
per-language model zoo would introduce exactly the language-dependent
processing the confound analysis is trying to avoid.

---

## G. Why a 2020 corpus, and why it cannot be re-collected

### Murtfeldt, R., Paik, S., Alterman, N., Kahveci, I., & West, J. D. (2024)
*RIP Twitter API: A eulogy to its vast research contributions.* arXiv:2404.07340.
`[verified]`

Documents the February 2023 end of free API access and the June 2023
suspension of academic archive access, with enterprise pricing at $42,000/month.
Quantifies the effect: 33,306 studies with 610,738 citations across 16
disciplines between 2006 and 2024, study growth averaging 25% annually until
the shutdown, then a **13% drop in 2024**.

### Blakey, E. (2024)
*The Day Data Transparency Died: How Twitter/X Cut Off Access for Social
Research.* `[search-only — confirm the journal]`

**Where it goes:** the introduction (why this corpus), and the evaluation
chapter's limitations. It converts what looks like a weakness — a single-day
2020 corpus that cannot be extended — into a documented constraint of the
research environment. It also strengthens the reproducibility argument for the
repository: this code runs on a dataset that can no longer be collected, so
pinned dependencies, a fixed seed and generated result tables are not
box-ticking.

Be careful not to overclaim. The corpus predates the shutdown and its
limitations are its own — one day, two collection blocks, a language-imbalanced
negative pool. The API situation explains why the study was not re-run on
fresh data; it does not excuse the corpus's defects.

---

## H. Statistical comparison methodology

Review feedback asked for formulas to be given consistently: Saito &
Rehmsmeier's is present, McNemar's and Bonferroni's are not. These are the
standard references for supplying them.

### Demšar, J. (2006)
*Statistical Comparisons of Classifiers over Multiple Data Sets.* JMLR 7:1–30.
`[search-only]`

The standard reference for multiple-comparison correction when comparing
classifiers. Supports the Bonferroni α = 0.05 / 4 = 0.0125 used in the H2 test.

### Raschka, S. (2018)
*Model Evaluation, Model Selection, and Algorithm Selection in Machine
Learning.* arXiv:1811.12808. `[search-only]`

Gives McNemar's statistic and the exact-test variant explicitly, and states why
McNemar is preferred for paired classifier comparison: it does not assume
independent samples and has a low Type I error rate. Also notes Cochran's Q as
the generalisation to three or more classifiers.

**Where it goes:** the evaluation chapter's methodology section. Two formulas
are needed to close the review's complaint, both on paired out-of-fold
decisions:

- McNemar's exact test on the discordant pairs (b, c), reported here as
  only-A-correct and only-B-correct counts in every table.
- Bonferroni: α' = α / m, with m = 4 leads in the H2 family.

**Worth stating explicitly in the report:** this study reports the **exact**
binomial McNemar test, not the chi-square approximation. With discordant counts
as low as 12, the chi-square approximation is not reliable, and the exact test
is the correct choice rather than a stylistic one. That is a defensible
methodological decision the draft currently leaves implicit.

---

## What this does not fix

Two review points are not addressable by adding sources:

1. **"The number of features in ablation and full fusion should be rechecked."**
   The counts are correct — `full_fusion` has 31 features and `volume_extended`
   has 33 — but the report never explains why the baseline has *more* features
   than the fused model and is not a subset of it. That is one paragraph of
   exposition, not a citation.

2. **"All recomputations should be listed, and if it is the same run, it cannot
   be listed separately."** This needs the draft itself to diagnose which pair
   of reported runs the reviewer read as duplicated.

---

## Sources

- [Wu et al. 2025, PeerJ CS — Predicting emerging trends](https://peerj.com/articles/cs-3245/)
- [Xu et al. 2025 — Forecasting the Buzz (BuzzProphet)](https://arxiv.org/abs/2510.08481)
- [Survey of Deep Learning-Based Information Cascade Prediction, Symmetry 2024](https://www.mdpi.com/2073-8994/16/11/1436)
- [HierCas, IJCNN 2024](https://arxiv.org/html/2310.13219)
- [Multi-view temporal GNN for miniature cascade popularity, J. Supercomputing 2025](https://link.springer.com/article/10.1007/s11227-025-07484-4)
- [Steinmann et al. 2024 — Navigating Shortcuts, Spurious Correlations, and Confounders](https://arxiv.org/pdf/2412.05152)
- [Navigating the Shortcut Maze 2024](https://arxiv.org/pdf/2409.17455)
- [Explore Spurious Correlations at the Concept Level, ACL 2024](https://aclanthology.org/2024.acl-long.28.pdf)
- [McDermott et al. 2024, NeurIPS — A Closer Look at AUROC and AUPRC under Class Imbalance](https://arxiv.org/abs/2401.06091)
- [Ferrari Dacrema et al. — A Troubling Analysis of Reproducibility and Progress in Recommender Systems Research](https://arxiv.org/pdf/1911.07698)
- [Deep-learning gene perturbation prediction vs linear baselines](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12328236/)
- [Barbieri et al. — XLM-T](https://arxiv.org/abs/2104.12250)
- [Fine-tuning multilingual LMs in Twitter/X sentiment analysis, V4 languages 2024](https://arxiv.org/pdf/2408.02044)
- [Murtfeldt et al. 2024 — RIP Twitter API](https://arxiv.org/abs/2404.07340)
- [Blakey 2024 — The Day Data Transparency Died](https://journals.sagepub.com/doi/10.1177/15365042241252125)
- [Golland et al. — From (almost) open to heavily restricted data access](https://journals.sagepub.com/doi/10.1177/20539517261419333)
- [Küpfer — Nonrandom Tweet Mortality and Data Access Restrictions, Political Analysis](https://www.cambridge.org/core/journals/political-analysis/article/nonrandom-tweet-mortality-and-data-access-restrictions-compromising-the-replication-of-sensitive-twitter-studies/17E618F1D395CBBB2360AA424DA5533A)
- [Demšar 2006, JMLR — Statistical Comparisons of Classifiers over Multiple Data Sets](https://www.jmlr.org/papers/volume7/demsar06a/demsar06a.pdf)
- [Raschka 2018 — Model Evaluation, Model Selection, and Algorithm Selection](https://arxiv.org/pdf/1811.12808)
- [Goel et al. — The Structural Virality of Online Diffusion](https://pubsonline.informs.org/doi/10.1287/mnsc.2015.2158)
