# trend-emergence - run and test

*Command sheet for VS Code on Windows. Generated 2026-09-24.*

Open the project folder in VS Code: File > Open Folder > trend-emergence. Then open a terminal with Ctrl+` (backtick).

> VS Code on Windows defaults to PowerShell. Windows PowerShell 5.1 has NO && operator - running two commands joined by && is a parser error. Run each line separately, or join with a semicolon.


## 0. One-time setup

Skip if .venv already exists in the project folder.

```powershell
python -m venv .venv
```

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

requirements-dev.txt pulls in requirements.txt, so this installs the pipeline AND the linter. The sentiment channel needs torch and transformers, which are deliberately separate and only needed if you re-run the sentiment stage:

```powershell
.venv\Scripts\python -m pip install -r requirements-sentiment.txt
```

Point VS Code at the environment: Ctrl+Shift+P, then "Python: Select Interpreter", then pick the one inside .venv. Without this, the Testing panel and the import resolver will look at the wrong Python.


## 1. Check it works - no dataset needed

Start here. These need no corpus at all: every test builds its own synthetic data in code. If these pass, the code is sound.

```powershell
.venv\Scripts\python -m pytest -q
```

> Expect: 214 passed, 1 skipped, in about 10 seconds.

```powershell
.venv\Scripts\python -m ruff check .
```

> Expect: All checks passed!

More detail when something fails:

```powershell
.venv\Scripts\python -m pytest -v
```

```powershell
.venv\Scripts\python -m pytest -q --maxfail=1 -x
```

Run one file, or one test, while you are working on it:

```powershell
.venv\Scripts\python -m pytest tests/test_temporal.py -v
```

```powershell
.venv\Scripts\python -m pytest -k "arima" -v
```

The load-bearing test - asserts no feature window contains data at or after its cut-off. If leakage is ever introduced, this fails:

```powershell
.venv\Scripts\python -m pytest tests/test_units.py -v
```


## 2. Check the repository state

```powershell
git log --oneline
```

> Expect a linear history on main, and no remote configured - nothing has been pushed yet.

```powershell
git status --short
```

> Expect no output at all. That means a clean working tree.

Confirm the corpus is not tracked - this must stay true before any push, since the repo goes public:

```powershell
git ls-files dataset/
```

> Expect no output. If this prints anything, STOP and do not push.


## 3. Rebuild everything from the dataset

Needs the two CSVs in dataset/. Run in this order - each step reads what the previous one cached. Runtimes below were measured on this machine (i9-13900H).

```powershell
.venv\Scripts\python -m src.data.units
```

> Streams both CSVs, detects peaks, drops censored topics. Writes outputs/cache/units.csv. Expect 129 units, 42 trending.

```powershell
.venv\Scripts\python -m src.features.network
```

> Builds the mention/reply graph per window. About 1 minute.

```powershell
.venv\Scripts\python -m src.features.sentiment
```

> XLM-T scoring. About 11 minutes on a cold cache, about 30 seconds afterwards - it caches raw model probabilities by text hash. Needs requirements-sentiment.txt installed.

```powershell
.venv\Scripts\python -m src.eval.arima_order
```

> Selects the ARIMA order against the data: ADF and KPSS, then a 16-order AIC/BIC grid. About 41 seconds. Writes outputs/tables/arima_order_selection.json.

```powershell
.venv\Scripts\python -m src.features.temporal
```

> About 16 seconds. Prints the size-proxy audit and must end with "audit agrees with config".

```powershell
.venv\Scripts\python -m src.eval.size_audit
```

```powershell
.venv\Scripts\python -m src.eval.ablation
```

> The 12-arm ablation and every McNemar test. About 14 seconds. This is the table H1 rests on.

```powershell
.venv\Scripts\python -m src.eval.lead_time
```

> Slowest evaluation step - about 4 minutes. Produces the nested sweep that H2 rests on.

```powershell
.venv\Scripts\python -m src.eval.language_control
```

> About 17 seconds. The negative control that fails.

```powershell
.venv\Scripts\python -m src.eval.robustness
```

> About 2 minutes.

```powershell
.venv\Scripts\python -m src.eval.figures
```

```powershell
.venv\Scripts\python -m src.eval.results_summary
```

> Must run LAST. Regenerates outputs/tables/RESULTS_SUMMARY.md from the JSONs every earlier step wrote. Never edit that file by hand - it is generated.


## 4. Useful one-offs

Parameter sweep over topic size, lead and window, with and without the language filter:

```powershell
.venv\Scripts\python -m src.data.units --sweep
```

Reproduce the frozen prototype, and the same prototype with the negative-pool leak corrected:

```powershell
.venv\Scripts\python prototype/rerun/extract.py --mode frozen --out outputs/cache/proto_frozen_features.csv
```

```powershell
.venv\Scripts\python prototype/rerun/evaluate.py --features outputs/cache/proto_frozen_features.csv --out outputs/tables/proto_frozen_results.json --tag frozen
```

> Swap --mode fixed and the matching filenames for the corrected run.


## 5. If something goes wrong

"No module named src" - you are not in the project root. Check with:

```powershell
Get-Location
```

"No module named pandas" - VS Code is using the wrong Python. Confirm which one the terminal is using:

```powershell
.venv\Scripts\python -c "import sys; print(sys.executable)"
```

A stage complains about a missing cache file - you skipped a step. The order in section 3 is a dependency chain, not a preference.

temporal.py prints "AUDIT/CONFIG MISMATCH" - a feature's measured correlation with volume disagrees with its assignment in config.yaml. That is the audit doing its job. Do not silence it.

Results differ slightly from the committed tables - check the seed is still 42 in config.yaml. Resampling noise is plus or minus 0.02 to 0.03 PR-AUC, so small differences in the third decimal are expected between machines; anything larger is not.


## 6. Publication

The repository is public at github.com/Saifullahshamsi/Final_Year_Project. The CI badge, the licence holder and the repository URL are all filled in - nothing is left as a placeholder. Confirm that is still true with:

```powershell
git grep -n "OWNER/REPO\|TODO-SET"
```

> Expect no output. A hit means a placeholder has come back, which on a public graded repository is visible to anyone who opens the front page.
