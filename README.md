# ShadowFind — Shadow Silhouette Matching for Lost and Found Items

A mini-project report for a campus lost-and-found portal, typeset to the KPR
Institute mini-project format.

**The idea:** when someone photographs an item, the app extracts the object's
**cast shadow**, turns the silhouette into a 64-bin shape descriptor, and ranks
found items against lost ones by shape — so a blue bag is compared with another
blue bag by its outline, not by two people's descriptions of it.

> **Status:** this repository contains the *report* (and everything needed to
> regenerate it). The statistics, screenshots and evaluation numbers in the
> report are illustrative, written for a plausible academic mini-project; they
> are not measurements from a deployed system.

---

## Read it

| | |
|---|---|
| **[ShadowFind_Report.pdf](ShadowFind_Report.pdf)** | The finished document — 23 pages, A4 |

Front matter and body follow the KPR template: cover, bonafide certificate,
table of contents, list of tables, list of figures, list of abbreviations,
chapters 1–5, references.

**Contents:** Abstract · Introduction · Implementation · Outcome · Conclusion,
with 11 tables and 6 figures.

---

## How it is built

The PDF is not laid out by hand. A small pipeline measures the real rendered
height of every block and packs the pages, which is why nothing overflows and
the contents lists can be generated from the actual layout.

```
content.py      the prose, tables and figure references (edit the report here)
build_report.py page geometry, CSS, cover, certificate, front matter
paginate.py     measures each block in a headless browser and packs pages
render_pdf.py   prints the paginated HTML to PDF
browser.py      finds a Chromium-based browser (macOS / Linux / Windows)
make_figures.py the architecture, ER and flowchart diagrams
make_chart.py   the two-panel study chart in Chapter 4
mockups/        the HTML/CSS screenshots used as "UI screenshots"
```

### Rebuild

Requires Python 3 with `matplotlib` and `Pillow`, and any Chromium-based
browser (Chrome, Chromium, Edge or Brave). If it is not installed in a standard
place, point at it:

```bash
pip install -r requirements.txt
./make.sh
# or: CHROME=/path/to/chrome ./make.sh
```

`make.sh` regenerates the figures, repaginates, and rewrites
`ShadowFind_Report.pdf`.

### Layout checks

```bash
python3 check_layout.py     # reports any page whose content overflows its frame
```

---

## Mapping to the report

| Chapter | What it covers |
|---|---|
| 1 Abstract | Problem, method, headline results |
| 2 Introduction | Why lost-and-found fails today; objectives, scope, plan |
| 3 Implementation | Architecture, stack, five modules + security, testing |
| 4 Outcome | Chart, screenshots, comparison, accuracy tables, limitations |
| 5 Conclusion | Summary, future scope |

Figures 3.1–3.3 are diagrams generated from `make_figures.py`; 4.1–4.3 are
mockups rendered from `mockups/*.html`; the unnumbered chart at the head of
Chapter 4 comes from `make_chart.py`.

---

## Editing

Most changes only need `content.py` — it holds the report as an ordered list of
blocks (`("p", ...)`, `("table", ...)`, `("figure", ...)`), so pages re-flow on
their own. Cover details, the certificate and front matter live in
`build_report.py`.
