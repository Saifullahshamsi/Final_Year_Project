"""Build the run-and-test command sheet as a PDF.

ASCII only in the body: fpdf2's core fonts are latin-1, so arrows and dashes
would raise or render wrong. Plain hyphens and -> throughout.
"""
from fpdf import FPDF

TITLE = "trend-emergence - run and test"
SUB = "Command sheet for VS Code on Windows. Generated 2026-09-24."

# (kind, text)
#   h1   section heading
#   p    paragraph
#   cmd  command block (monospace, shaded)
#   note small italic note
#   rule thin separator
#   gap  vertical space
DOC = [
    ("p", "Open the project folder in VS Code: File > Open Folder > "
          "trend-emergence. Then open a terminal with Ctrl+` (backtick)."),
    ("note", "VS Code on Windows defaults to PowerShell. Windows PowerShell 5.1 "
             "has NO && operator - running two commands joined by && is a parser "
             "error. Run each line separately, or join with a semicolon."),

    ("h1", "0. One-time setup"),
    ("p", "Skip if .venv already exists in the project folder."),
    ("cmd", "python -m venv .venv"),
    ("cmd", ".venv\\Scripts\\python -m pip install -r requirements-dev.txt"),
    ("p", "requirements-dev.txt pulls in requirements.txt, so this installs "
          "the pipeline AND the linter. The sentiment channel needs torch and "
          "transformers, which are deliberately separate and only needed if "
          "you re-run the sentiment stage:"),
    ("cmd", ".venv\\Scripts\\python -m pip install -r requirements-sentiment.txt"),
    ("p", "Point VS Code at the environment: Ctrl+Shift+P, then "
          "\"Python: Select Interpreter\", then pick the one inside .venv. "
          "Without this, the Testing panel and the import resolver will look "
          "at the wrong Python."),

    ("h1", "1. Check it works - no dataset needed"),
    ("p", "Start here. These need no corpus at all: every test builds its own "
          "synthetic data in code. If these pass, the code is sound."),
    ("cmd", ".venv\\Scripts\\python -m pytest -q"),
    ("note", "Expect: 214 passed, 1 skipped, in about 10 seconds."),
    ("cmd", ".venv\\Scripts\\python -m ruff check ."),
    ("note", "Expect: All checks passed!"),
    ("p", "More detail when something fails:"),
    ("cmd", ".venv\\Scripts\\python -m pytest -v"),
    ("cmd", ".venv\\Scripts\\python -m pytest -q --maxfail=1 -x"),
    ("p", "Run one file, or one test, while you are working on it:"),
    ("cmd", ".venv\\Scripts\\python -m pytest tests/test_temporal.py -v"),
    ("cmd", ".venv\\Scripts\\python -m pytest -k \"arima\" -v"),
    ("p", "The load-bearing test - asserts no feature window contains data at "
          "or after its cut-off. If leakage is ever introduced, this fails:"),
    ("cmd", ".venv\\Scripts\\python -m pytest tests/test_units.py -v"),

    ("h1", "2. Check the repository state"),
    ("cmd", "git log --oneline"),
    ("note", "Expect a linear history on main, and no remote "
             "configured - nothing has been pushed yet."),
    ("cmd", "git status --short"),
    ("note", "Expect no output at all. That means a clean working tree."),
    ("p", "Confirm the corpus is not tracked - this must stay true before any "
          "push, since the repo goes public:"),
    ("cmd", "git ls-files dataset/"),
    ("note", "Expect no output. If this prints anything, STOP and do not push."),

    ("h1", "3. Rebuild everything from the dataset"),
    ("p", "Needs the two CSVs in dataset/. Run in this order - each step reads "
          "what the previous one cached. Runtimes below were measured on this "
          "machine (i9-13900H)."),
    ("cmd", ".venv\\Scripts\\python -m src.data.units"),
    ("note", "Streams both CSVs, detects peaks, drops censored topics. "
             "Writes outputs/cache/units.csv. Expect 129 units, 42 trending."),
    ("cmd", ".venv\\Scripts\\python -m src.features.network"),
    ("note", "Builds the mention/reply graph per window. About 1 minute."),
    ("cmd", ".venv\\Scripts\\python -m src.features.sentiment"),
    ("note", "XLM-T scoring. About 11 minutes on a cold cache, about 30 "
             "seconds afterwards - it caches raw model probabilities by text "
             "hash. Needs requirements-sentiment.txt installed."),
    ("cmd", ".venv\\Scripts\\python -m src.eval.arima_order"),
    ("note", "Selects the ARIMA order against the data: ADF and KPSS, then a "
             "16-order AIC/BIC grid. About 41 seconds. Writes "
             "outputs/tables/arima_order_selection.json."),
    ("cmd", ".venv\\Scripts\\python -m src.features.temporal"),
    ("note", "About 16 seconds. Prints the size-proxy audit and must end with "
             "\"audit agrees with config\"."),
    ("cmd", ".venv\\Scripts\\python -m src.eval.size_audit"),
    ("cmd", ".venv\\Scripts\\python -m src.eval.ablation"),
    ("note", "The 12-arm ablation and every McNemar test. About 14 seconds. "
             "This is the table H1 rests on."),
    ("cmd", ".venv\\Scripts\\python -m src.eval.lead_time"),
    ("note", "Slowest evaluation step - about 4 minutes. Produces the nested "
             "sweep that H2 rests on."),
    ("cmd", ".venv\\Scripts\\python -m src.eval.language_control"),
    ("note", "About 17 seconds. The negative control that fails."),
    ("cmd", ".venv\\Scripts\\python -m src.eval.robustness"),
    ("note", "About 2 minutes."),
    ("cmd", ".venv\\Scripts\\python -m src.eval.figures"),
    ("cmd", ".venv\\Scripts\\python -m src.eval.results_summary"),
    ("note", "Must run LAST. Regenerates outputs/tables/RESULTS_SUMMARY.md "
             "from the JSONs every earlier step wrote. Never edit that file "
             "by hand - it is generated."),

    ("h1", "4. Useful one-offs"),
    ("p", "Parameter sweep over topic size, lead and window, with and without "
          "the language filter:"),
    ("cmd", ".venv\\Scripts\\python -m src.data.units --sweep"),
    ("p", "Reproduce the frozen prototype, and the same prototype with the "
          "negative-pool leak corrected:"),
    ("cmd", ".venv\\Scripts\\python prototype/rerun/extract.py --mode frozen "
            "--out outputs/cache/proto_frozen_features.csv"),
    ("cmd", ".venv\\Scripts\\python prototype/rerun/evaluate.py "
            "--features outputs/cache/proto_frozen_features.csv "
            "--out outputs/tables/proto_frozen_results.json --tag frozen"),
    ("note", "Swap --mode fixed and the matching filenames for the corrected "
             "run."),

    ("h1", "5. If something goes wrong"),
    ("p", "\"No module named src\" - you are not in the project root. Check "
          "with:"),
    ("cmd", "Get-Location"),
    ("p", "\"No module named pandas\" - VS Code is using the wrong Python. "
          "Confirm which one the terminal is using:"),
    ("cmd", ".venv\\Scripts\\python -c \"import sys; print(sys.executable)\""),
    ("p", "A stage complains about a missing cache file - you skipped a step. "
          "The order in section 3 is a dependency chain, not a preference."),
    ("p", "temporal.py prints \"AUDIT/CONFIG MISMATCH\" - a feature's measured "
          "correlation with volume disagrees with its assignment in "
          "config.yaml. That is the audit doing its job. Do not silence it."),
    ("p", "Results differ slightly from the committed tables - check the seed "
          "is still 42 in config.yaml. Resampling noise is plus or minus "
          "0.02 to 0.03 PR-AUC, so small differences in the third decimal are "
          "expected between machines; anything larger is not."),

    ("h1", "6. Publication"),
    ("p", "The repository is public at "
          "github.com/Saifullahshamsi/Final_Year_Project. The CI badge, the "
          "licence holder and the repository URL are all filled in - nothing "
          "is left as a placeholder. Confirm that is still true with:"),
    ("cmd", "git grep -n \"OWNER/REPO\\|TODO-SET\""),
    ("note", "Expect no output. A hit means a placeholder has come back, "
             "which on a public graded repository is visible to anyone who "
             "opens the front page."),
]


class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(140)
        self.cell(0, 6, TITLE, align="R")
        self.ln(8)
        self.set_text_color(0)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(140)
        self.cell(0, 6, f"{self.page_no()}", align="C")
        self.set_text_color(0)


pdf = PDF(format="A4")
pdf.set_auto_page_break(auto=True, margin=18)
pdf.set_margins(20, 18, 20)
pdf.add_page()

pdf.set_font("Helvetica", "B", 19)
pdf.multi_cell(0, 9, TITLE)
pdf.ln(1)
pdf.set_font("Helvetica", "", 9.5)
pdf.set_text_color(100)
pdf.multi_cell(0, 5, SUB)
pdf.set_text_color(0)
pdf.ln(5)

for kind, text in DOC:
    if kind == "h1":
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12.5)
        pdf.set_text_color(20)
        pdf.multi_cell(0, 6.5, text)
        pdf.set_draw_color(200)
        pdf.set_line_width(0.3)
        y = pdf.get_y() + 1
        pdf.line(20, y, 190, y)
        pdf.ln(3.5)
        pdf.set_text_color(0)
    elif kind == "p":
        pdf.set_font("Helvetica", "", 9.5)
        pdf.multi_cell(0, 4.8, text)
        pdf.ln(2)
    elif kind == "cmd":
        lines = text.count("\n") + 1
        h = 5.2 * lines + 4
        if pdf.get_y() + h > 272:
            pdf.add_page()
        pdf.set_fill_color(243, 243, 240)
        pdf.set_draw_color(215)
        pdf.set_font("Courier", "", 8.8)
        x0, y0 = pdf.get_x(), pdf.get_y()
        pdf.rect(x0, y0, 170, h, style="DF")
        pdf.set_xy(x0 + 3, y0 + 2)
        pdf.multi_cell(164, 5.2, text)
        pdf.set_xy(x0, y0 + h)
        pdf.ln(2.5)
    elif kind == "note":
        pdf.set_font("Helvetica", "I", 8.6)
        pdf.set_text_color(95)
        pdf.multi_cell(0, 4.3, text)
        pdf.set_text_color(0)
        pdf.ln(2.5)

out = r"C:\Users\saifu\OneDrive\Desktop\DESKTOP\trend-emergence\docs\RUN_AND_TEST.pdf"
pdf.output(out)
print("wrote", out, f"({pdf.page_no()} pages)")

# --- Markdown twin, from the same DOC so the two cannot disagree ---
md = [f"# {TITLE}", "", f"*{SUB}*", ""]
for kind, text in DOC:
    if kind == "h1":
        md += ["", f"## {text}", ""]
    elif kind == "p":
        md += [text, ""]
    elif kind == "cmd":
        md += ["```powershell", text, "```", ""]
    elif kind == "note":
        md += [f"> {text}", ""]
mdout = r"C:\Users\saifu\OneDrive\Desktop\DESKTOP\trend-emergence\docs\RUN_AND_TEST.md"
with open(mdout, "w", encoding="utf-8") as fh:
    fh.write("\n".join(md).rstrip() + "\n")
print("wrote", mdout)
