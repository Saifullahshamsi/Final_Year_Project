# Literature 2023–2026 — candidate sources for the revised review

Review feedback on both the preliminary and draft reports said the same thing:
the literature review has nothing later than a 2022 conference paper, and is
limited in scope as well as in time. This file is a **search result, not a
chapter** — each entry says what the source claims and where it would sit in
the report, so the writing stays yours.

Ordered by how directly each one bears on a decision this project actually
made. The sources in §C, §D and §E matter most: they let the review engage
critically with work that **disagrees** with choices made here, which is a
separate marking criterion from merely knowing the field.

## Verification

Every entry below was checked against a publisher, preprint or indexer page.
Bibliographic details are marked:

- `[verified]` — title, authors, venue and year read off a publisher, arXiv or
  independent indexer page.
- `[partial]` — the identifying details are confirmed but something specific
  (a page range, an issue number, the tail of an author list) is not. What is
  missing is stated in the entry.

Checking produced **two corrections to this file's own first draft**, both
recorded below at §F1 and §H1. Neither was visible from search snippets; both
only appeared on reading the source. That is the same failure mode this
project documents elsewhere — a plausible claim that nothing contradicts until
someone looks.

---

## A. Closest prior work — topic-level trend prediction

### A1. Wu, Z., Liao, Y., Luo, C., Shi, J., & Yang, Y. (2025) `[verified]`
*Predicting emerging trends: a machine learning approach to topic popularity on
social media.* PeerJ Computer Science, 11:e3245. DOI: 10.7717/peerj-cs.3245

The nearest neighbour to this project in the recent literature: unit of
analysis is a **topic**, the task is framed as **binary classification** of
whether a topic will become popular, and the features combine traditional,
temporal and textual channels, compared across several models.

**Where it goes:** the review's gap argument, and the design chapter. The
strongest single citation for topic-level prediction being a live problem
rather than a solved one. It also sharpens the gap: it classifies topic
popularity but does not condition on a **lead time before peak**, which is
where this project differs. State that difference precisely — a reviewer who
knows this paper will check whether the gap claimed is the gap that exists.

### A2. Xu, Y., Wu, J., Wan, H., Li, Y., Hou, Z., & Kan, M.-Y. (2025) `[verified]`
*Forecasting the Buzz: Enriching Hashtag Popularity Prediction with LLM
Reasoning.* arXiv:2510.08481.

BuzzProphet: an LLM articulates topical virality, audience reach and timing
advantage as text, and those rationales feed classical tabular regressors.
Reports up to 2.8% RMSE reduction and ~30% correlation improvement over
baselines on a 7,532-hashtag benchmark.

**Where it goes:** the review (current direction of the field) and the
conclusion's further-work section. Note the modest headline gain — 2.8% RMSE —
alongside this project's finding that fusion did not beat a well-specified
volume baseline. Two independent observations that marginal return on added
signal in this task is small.

---

## B. Modern cascade and popularity prediction — context for the network channel

### B1. Wang, Z., Wang, X., Xiong, F., & Chen, H. (2024) `[verified]`
*A Survey of Deep Learning-Based Information Cascade Prediction.* Symmetry,
16(11), 1436. DOI: 10.3390/sym16111436

Classifies the field by prediction target and prediction method, and reviews
the standard evaluation metrics and datasets.

**Where it goes:** the review's structural-signals section, as the current
replacement for citing Weng et al. (2013) alone. A 2024 survey is the cheapest
way to demonstrate currency across a whole subfield.

### B2. Zhang, Z., Xie, X., Zhang, Y., Zhang, L., & Jiang, Y. (2023/2024) `[verified]`
*HierCas: Hierarchical Temporal Graph Attention Networks for Popularity
Prediction in Information Cascades.* arXiv:2310.13219. Accepted at IJCNN 2024.

Dynamic graph modelling over whole cascade graphs, dropping hand-engineered
features in favour of temporal node representations and hierarchical pooling.

### B3. Wu, Y., Fu, C., He, Z., et al. (2025) `[partial — author list truncated at "et al." by the indexer; resolve the DOI for the full list]`
*Multi-view temporal graph neural network for numerous miniature cascade
popularity prediction.* The Journal of Supercomputing, 81. DOI:
10.1007/s11227-025-07484-4

**The most useful of the three for this project**, because of one number in its
motivation: **more than 61% of information propagation comes from miniature
cascades (size < 25)**, and existing methods handle them badly.

**Where it goes:** the evaluation chapter's sparse-graph limitation, and the
design chapter's justification for not using a GNN. This project documented
that its interaction graphs are too sparse for the added structural features to
bite on. B3 says the sparse regime is not a defect of this corpus — it is where
most real diffusion lives, and it is an acknowledged open problem in 2025. That
converts a limitation into a positioned one.

Note also that B2 and B3 train on cascade corpora orders of magnitude larger
than 129 units. Citing them makes the "no deep sequence model" decision an
informed choice rather than an omission.

### B4. Goel, S., Anderson, A., Hofman, J., & Watts, D. J. (2016) `[verified]`
*The Structural Virality of Online Diffusion.* Management Science, 62(1),
180–196. DOI: 10.1287/mnsc.2015.2158

Canonical formalisation of structural virality; pairs with Weng et al. (2013)
and Cheng et al. (2014), already cited. Include only if the review needs the
structural-versus-broadcast distinction — do not pad a currency problem with
more pre-2022 work.

---

## C. The language confound has a name in the literature — use it

The highest-value section. The project's central unresolved limitation is
currently described in its own terms. It is a well-studied phenomenon with an
established vocabulary, and naming it correctly converts a confession into an
analysis.

### C1. Steinmann, D., Divo, F., Kraus, M., Wüst, A., Struppek, L., Friedrich, F., & Kersting, K. (2024) `[verified]`
*Navigating Shortcuts, Spurious Correlations, and Confounders: From Origins via
Detection to Mitigation.* arXiv:2412.05152.

A formal definition of a shortcut and a unifying taxonomy across the scattered
terminology (shortcut / spurious correlation / confounder / dataset artifact),
organised as origins → detection → mitigation, with links to bias and
causality.

**Where it goes:** the evaluation chapter at the language-confound section, and
the review. The language confound here is a textbook **shortcut with a
collection-process origin**: Spanish share predicts the label at PR-AUC 0.897
while carrying no information about trend dynamics. The taxonomy also supplies
the structure this project's control hierarchy already followed without naming
it — detection (the language-only classifier), attempted mitigation
(topic-level matching, tweet-level filtering, within-language restriction),
then the finding that mitigation is unavailable **because the origin is in
data collection, not in modelling**.

### C2. Zhou, Y., Tang, R., Yao, Z., & Zhu, Z. (2024) `[verified]`
*Navigating the Shortcut Maze: A Comprehensive Analysis of Shortcut Learning in
Text Classification by Language Models.* Findings of EMNLP 2024.
arXiv:2409.17455.

Benchmarks shortcuts in three categories — occurrence-based, style-based,
concept-based — across classical LMs, LLMs and robust architectures.

### C3. Zhou, Y., Xu, P., Liu, X., An, B., Ai, W., & Huang, F. (2024) `[verified]`
*Explore Spurious Correlations at the Concept Level in Language Models for Text
Classification.* ACL 2024 (Main). arXiv:2311.08648.

Concept-level rather than token-level analysis, with counterfactual data
rebalancing as mitigation.

Cite C2 **or** C3, not both — they make the same point for this report's
purposes. C2 is the better fit if the review wants a taxonomy of shortcut
types; C3 if it wants the mitigation-by-rebalancing argument, which is
relevant because rebalancing is precisely what this corpus does not permit.

**The argument this section enables:** the project reports a negative control
that failed. Framed as shortcut learning with a documented origin, that failure
becomes a measured, diagnosed and bounded limitation — and the demonstration
that all three mitigations are impossible on this corpus is itself a result
about the corpus.

---

## D. The evaluation metric choice is contested — say so

### D1. McDermott, M. B. A., Zhang, H., Hansen, L. H., Angelotti, G., & Gallifant, J. (2024) `[verified]`
*A Closer Look at AUROC and AUPRC under Class Imbalance.* NeurIPS 2024.
arXiv:2401.06091.

Directly refutes the widespread claim that AUPRC is superior to AUROC under
class imbalance. Argues AUPRC is not generally superior and can be **harmful**,
because it unduly favours model improvements in subpopulations with more
frequent positive labels, which can widen algorithmic disparities.

**Where it goes:** the evaluation chapter, immediately after the existing
Saito & Rehmsmeier (2015) justification for PR-AUC. **The single most valuable
source in this file**, because the marking criteria reward *critical*
engagement with literature, not just coverage — and this argues against a
decision already made and defended in the draft.

It does not invalidate the choice. The report can hold both positions:

- Saito & Rehmsmeier's argument still applies to the original problem: a large
  negative pool suppresses FPR, so ROC-AUC flatters a model with poor precision.
- McDermott et al.'s objection is about **cross-subpopulation comparison** and
  about treating AUPRC as a universal default.
- This project reports PR-AUC, ROC-AUC, F1, precision and recall side by side
  in every table, and the headline H1 conclusion **does not rest on either
  curve metric**. It rests on an exact McNemar test on paired out-of-fold
  decisions, which is insensitive to this entire dispute.

That last point is worth making explicitly: after the ARIMA re-run the PR-AUC
gap and the decision-level test actively disagree (0.051 apart on PR-AUC, an
exact 10–10 tie on McNemar), and the report already states McNemar is the one
to trust. This is the citation that justifies that preference rather than
asserting it.

---

## E. "Fusion did not beat the baseline" is a known and respected result

Review feedback did not ask for this, but the H1 null is the project's main
finding and should be positioned inside a literature that takes such results
seriously — otherwise it reads as a failed experiment.

### E1. Ferrari Dacrema, M., Boglio, S., Cremonesi, P., & Jannach, D. (2021) `[verified]`
*A Troubling Analysis of Reproducibility and Progress in Recommender Systems
Research.* ACM Transactions on Information Systems, 39(2), Article 20, 49 pp.
DOI: 10.1145/3434185. (Preprint arXiv:1911.07698, 2019 — **cite the 2021 TOIS
version**, not the preprint.)

11 of 12 reproducible neural approaches were outperformed by conceptually
simple methods — nearest-neighbour heuristics or linear models — once baselines
were properly tuned. Names the causes: **weak baselines**, insufficient
hyperparameter tuning, and problematic evaluation practice.

**Where it goes:** the evaluation chapter at the `volume_extended` decision,
and the conclusion. The literature's strongest statement of the principle this
project independently arrived at — **baseline specification determines the
conclusion**. Against a 3-feature `volume_only` baseline, fusion wins at
p = 0.0041 and H1 "passes". Against `volume_extended`, holding the 33 features
the size-proxy audit disqualified from other channels, it ties at p = 1.0000.
Same model, same data, opposite conclusion.

Note the direction of the contribution: this project **built the strong
baseline against its own hypothesis**, which is the practice Dacrema et al.
found missing. A methodological strength to claim, not a mishap to explain.

### E2. Ahlmann-Eltze, C., Huber, W., & Anders, S. (2025) `[verified]`
*Deep-learning-based gene perturbation effect prediction does not yet
outperform simple linear baselines.* Nature Methods, 22(8). DOI:
10.1038/s41592-025-02772-6

Benchmarked five foundation models and two further deep-learning approaches
against deliberately simple baselines. **None outperformed the baselines.** A
trivial "no change" model matched or exceeded complex systems requiring
substantial compute.

This was filed as optional in the first draft of this file and that was a
misjudgement — it is *Nature Methods*, 2025, and it states the point more
starkly than E1 does. A second field reaching the same conclusion, in a venue
no examiner will treat as marginal, is worth the ~40 words.

---

## F. Multilingual sentiment — the XLM-T lineage

### F1. CORRECTION to this file's first draft

The first draft cited **arXiv:2408.02044** (Filip, Pavlíček & Sosík, 2024,
*Fine-tuning multilingual language models in Twitter/X sentiment analysis: a
study on Eastern-European V4 languages*) for the claim that *"XLM-T slightly
underperforms monolingual models such as BERTweet and TimeLMs while remaining
state of the art among multilingual Twitter-specific models."*

**That paper does not make that claim.** `[verified]` — it covers Czech,
Slovak, Polish and Hungarian, fine-tunes BERT, BERTweet, Llama2, Llama3 and
Mistral on sentiment toward Russia and Ukraine during the 2023 conflict, and
benchmarks against GPT-4. XLM-T is not its subject. The sentence came from a
search-engine summary that blended sources, and it survived into the draft
because nothing contradicted it.

**Do not cite it for that claim.** Either drop the claim, or find its real
source before using it. The claim itself is plausible and may well be
supportable — but "plausible and unsourced" is what the review already
penalised elsewhere in this project.

F1 stands here rather than being quietly deleted because it is the same defect
class the project logs in FINDINGS: a statement that looks right, that no check
was pointed at, found only by going to the source.

### F2. Barbieri, F., Espinosa Anke, L., & Camacho-Collados, J. (2022) `[verified]`
*XLM-T: Multilingual Language Models in Twitter for Sentiment Analysis and
Beyond.* LREC 2022. arXiv:2104.12250.

The model actually used here, at pinned revision
`f2f1202b1bdeb07342385c3f807f9c07cd8f5cf8`. XLM-R further-pretrained on 198M
tweets across 30+ languages.

**Where it goes:** the design chapter's model-selection justification. Cite the
LREC 2022 paper, not the Hugging Face model card. If the report wants to state
the monolingual-versus-multilingual trade-off, it needs a source that actually
evaluates it — see F1 — or it should be argued from this project's own design
instead: the corpus is multilingual by construction, so a per-language model
zoo would introduce exactly the language-dependent processing the confound
analysis exists to avoid.

---

## G. Why a 2020 corpus, and why it cannot be re-collected

### G1. Murtfeldt, R., Paik, S., Alterman, N., Kahveci, I., & West, J. D. (2024) `[verified]`
*RIP Twitter API: A eulogy to its vast research contributions.*
arXiv:2404.07340.

Documents the February 2023 end of free API access and the June 2023
suspension of academic archive access, with enterprise pricing at $42,000 per
month. Quantifies the effect: 33,306 studies with 610,738 citations across 16
disciplines between 2006 and 2024, study growth averaging 25% annually until
the shutdown, then a **13% drop in 2024**.

### G2. Blakey, E. (2024) `[partial — journal and DOI confirmed; volume, issue and page range not]`
*The Day Data Transparency Died: How Twitter/X Cut Off Access for Social
Research.* Contexts. DOI: 10.1177/15365042241252125

**Where these go:** the introduction (why this corpus), and the evaluation
chapter's limitations. They convert what looks like a weakness — a single-day
2020 corpus that cannot be extended — into a documented constraint of the
research environment. They also strengthen the reproducibility case for the
repository: this code runs on a dataset that can no longer be collected, so
pinned dependencies, a fixed seed and generated result tables are not
box-ticking.

Do not overclaim. The corpus predates the shutdown and its defects are its own
— one day, two disjoint collection blocks, a language-imbalanced negative pool.
The API situation explains why the study was not re-run on fresh data; it does
not excuse those defects.

---

## H. Statistical comparison methodology

Review feedback asked for formulas to be given consistently: Saito &
Rehmsmeier's is present, McNemar's and Bonferroni's are not.

### H1. CORRECTION to this file's first draft

The first draft cited **Demšar (2006)** as support for the Bonferroni
correction used in the H2 test. That misrepresents the paper. `[verified]`

Demšar finds **Holm's step-down procedure more powerful than Bonferroni-Dunn,
and making no additional assumptions**, and recommends it over plain Bonferroni.
His framework is also built for *k classifiers across N datasets* — Friedman
plus post-hoc tests, with Wilcoxon signed-ranks for two classifiers. This
project has **one dataset** and compares paired per-unit decisions, so his
framework does not transfer wholesale.

**The conclusion survives, and is strengthened by saying so.** Holm's first
step compares the smallest p-value to α/m — identical to Bonferroni. Here the
smallest of the four H2 p-values is 0.0347 against α/4 = 0.0125, so **Holm
rejects nothing either**. The two procedures coincide on exactly the comparison
that matters.

Worth stating plainly in the report: *the H2 result fails to survive correction
under both Bonferroni and the strictly more powerful Holm procedure, because
the two coincide on the smallest p-value.* That is a stronger and more
defensible sentence than the current one, and it costs nothing.

### H2. Demšar, J. (2006) `[verified]`
*Statistical Comparisons of Classifiers over Multiple Data Sets.* Journal of
Machine Learning Research, 7, 1–30.

Cite for the multiple-comparison discussion and the Holm-over-Bonferroni point
in H1 — **not** as blanket endorsement of Bonferroni, and not as the framework
for this project's single-dataset design.

### H3. Dietterich, T. G. (1998) `[verified]`
*Approximate Statistical Tests for Comparing Supervised Classification Learning
Algorithms.* Neural Computation, 10(7), 1895–1923. DOI:
10.1162/089976698300017197

**The primary citation this project actually needs, and it was missing.**
Reviews five approximate tests and shows two widely used ones have high Type I
error and should never be used. Finds **McNemar's test has low Type I error,
and that for algorithms executed only once it is the only test with acceptable
Type I error**.

That is the exact justification for this project's design: one training run per
arm, paired out-of-fold decisions, McNemar for every comparison. Cite H3 rather
than Demšar for the choice of McNemar itself.

### H4. Raschka, S. (2018) `[verified — cite v3, 2020]`
*Model Evaluation, Model Selection, and Algorithm Selection in Machine
Learning.* arXiv:1811.12808.

Gives McNemar's statistic and the exact-test variant explicitly, and notes
Cochran's Q as the generalisation to three or more classifiers. **Cite v3**:
its changelog records a fix to the exact binomial p-value in §4.4, using
max(B, C) rather than B in the sum. Citing v1 for a formula that v3 corrected
would be an unforced error.

**What the evaluation chapter needs, concretely.** Two formulas, both on paired
out-of-fold decisions:

- McNemar's exact test on the discordant pairs (b, c), reported here as
  only-A-correct and only-B-correct counts in every table.
- Bonferroni: α′ = α / m, with m = 4 leads in the H2 family — noting per H1
  that Holm gives the same answer at the decisive step.

**State explicitly that this study uses the exact binomial McNemar test, not
the chi-square approximation.** With discordant counts as low as 12, the
approximation is not reliable, so the exact test is the correct choice rather
than a stylistic one. The draft currently leaves that implicit, and H3 and H4
between them make it defensible.

---

## What this does not fix

Two review points are not addressable by adding sources:

1. **"The number of features in ablation and full fusion should be rechecked."**
   The counts are correct — `full_fusion` has 31 features, `volume_extended`
   has 33 — but the report never explains why the baseline has *more* features
   than the fused model and is not a subset of it. One paragraph of exposition,
   not a citation.

2. **"All recomputations should be listed, and if it is the same run, it cannot
   be listed separately."** This needs the draft itself to diagnose which pair
   of reported runs the reviewer read as duplicated.

---

## Sources

- [Wu et al. 2025, PeerJ CS 11:e3245](https://peerj.com/articles/cs-3245/) · [indexer record](https://ouci.dntb.gov.ua/en/works/420v1EPV/)
- [Xu et al. 2025 — Forecasting the Buzz](https://arxiv.org/abs/2510.08481)
- [Wang et al. 2024 — Survey of Deep Learning-Based Information Cascade Prediction](https://www.mdpi.com/2073-8994/16/11/1436) · [publisher-independent record](https://pure.bit.edu.cn/en/publications/a-survey-of-deep-learning-based-information-cascade-prediction/)
- [Zhang et al. — HierCas, IJCNN 2024](https://arxiv.org/abs/2310.13219)
- [Wu et al. 2025 — Multi-view temporal GNN, J. Supercomputing](https://link.springer.com/article/10.1007/s11227-025-07484-4)
- [Goel et al. 2016 — The Structural Virality of Online Diffusion](https://pubsonline.informs.org/doi/10.1287/mnsc.2015.2158)
- [Steinmann et al. 2024 — Navigating Shortcuts, Spurious Correlations, and Confounders](https://arxiv.org/abs/2412.05152)
- [Zhou et al. 2024 — Navigating the Shortcut Maze, Findings of EMNLP](https://arxiv.org/abs/2409.17455)
- [Zhou et al. 2024 — Spurious Correlations at the Concept Level, ACL](https://arxiv.org/abs/2311.08648)
- [McDermott et al. 2024 — A Closer Look at AUROC and AUPRC under Class Imbalance, NeurIPS](https://arxiv.org/abs/2401.06091)
- [Ferrari Dacrema et al. 2021 — ACM TOIS 39(2)](https://arxiv.org/abs/1911.07698)
- [Ahlmann-Eltze et al. 2025 — Nature Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC12328236/)
- [Barbieri et al. — XLM-T, LREC 2022](https://arxiv.org/abs/2104.12250)
- [Filip et al. 2024 — V4 languages (see F1: does NOT support the XLM-T claim)](https://arxiv.org/abs/2408.02044)
- [Murtfeldt et al. 2024 — RIP Twitter API](https://arxiv.org/abs/2404.07340)
- [Blakey 2024 — The Day Data Transparency Died, Contexts](https://journals.sagepub.com/doi/10.1177/15365042241252125)
- [Demšar 2006 — JMLR 7:1–30](https://www.jmlr.org/papers/volume7/demsar06a/demsar06a.pdf)
- [Dietterich 1998 — Neural Computation 10(7)](https://direct.mit.edu/neco/article-abstract/10/7/1895/6224/Approximate-Statistical-Tests-for-Comparing)
- [Raschka 2018 (cite v3, 2020)](https://arxiv.org/abs/1811.12808)
