#!/usr/bin/env bash
# Rebuild the ShadowFind report end to end.
#   ./make.sh            -> ShadowFind_Report.pdf
set -euo pipefail
cd "$(dirname "$0")"
# prefer the project virtualenv (matplotlib/numpy/Pillow live there)
for candidate in "../../.venv/bin/python" "../.venv/bin/python" python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import matplotlib" >/dev/null 2>&1; then
    PY="$candidate"; break
  fi
done
: "${PY:?no python with matplotlib found}"
echo "using $PY"
"$PY" make_figures.py
"$PY" make_chart.py
"$PY" paginate.py          # measures blocks in Chrome, packs pages, writes HTML
"$PY" render_pdf.py        # prints the HTML to PDF
echo "done: $(pwd)/ShadowFind_Report.pdf"
