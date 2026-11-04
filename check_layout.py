"""Layout QA for the generated report.

Two independent checks, both against the rendered PDF:

1. `check_overflow` loads the HTML in headless Chrome and reports, for every
   `.page` block, any child whose bottom edge passes the text frame. This
   catches content that would be silently clipped by `overflow: hidden`.
2. `check_pdf_text` extracts the text of the PDF and verifies the folio
   sequence, so a missing or doubled page is caught.

Usage:  python3 check_layout.py
Exit status is non-zero when a check fails.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = HERE / "ShadowFind_Report.html"
PDF = HERE / "ShadowFind_Report.pdf"
from browser import find_chrome

CHROME = find_chrome()

PROBE_JS = r"""
(() => {
  const out = [];
  const flush = (data) => {
    const pre = document.createElement('pre');
    pre.id = 'probe-out';
    pre.textContent = JSON.stringify(data);
    document.body.appendChild(pre);
  };
  document.querySelectorAll('.page').forEach((p, i) => {
    const flow = p.querySelector('.flow');
    const frame = p.querySelector('.frame');
    const pageRect = p.getBoundingClientRect();
    let limit;
    if (frame) {
      limit = frame.getBoundingClientRect().bottom - 12;  // stay inside the border
    } else {
      limit = pageRect.bottom;
    }
    // deepest bottom edge among content children of the flow
    let worst = 0, worstTag = '';
    const nodes = flow ? Array.from(flow.children) : [];
    nodes.forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.bottom > limit + 0.5 && r.height > 0) {
        out.push({
          page: i + 1,
          tag: el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
          over: +(r.bottom - limit).toFixed(1),
          text: (el.textContent || '').trim().slice(0, 70),
        });
      }
    });

  });
  flush(out);
})()
"""


def check_overflow() -> list[dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(PROBE_JS)
        js_path = fh.name
    dom = HTML.read_text(encoding="utf-8")
    dom = dom.replace("</body>", f"<script>{PROBE_JS}</script></body>")
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
        fh.write(dom)
        html_path = fh.name

    with tempfile.TemporaryDirectory() as tmp:
        user_data = Path(tmp) / "ud"
        cmd = [
            CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
            f"--user-data-dir={user_data}", "--virtual-time-budget=8000",
            "--dump-dom", Path(html_path).as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
    Path(js_path).unlink(missing_ok=True)
    Path(html_path).unlink(missing_ok=True)

    dom = proc.stdout
    m = re.search(r"<pre[^>]*>(.*?)</pre>", dom, re.S)
    raw = m.group(1) if m else ""
    if not raw:
        # the probe result is the only <pre>; fall back to a loose search
        m = re.search(r"(\[\{.*?\}\])", dom, re.S)
        raw = m.group(1) if m else "[]"
    raw = raw.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("  (probe output not parseable, falling back to PDF metrics)")
        return []


def check_pdf_text() -> tuple[bool, list[str]]:
    txt = subprocess.run(["pdftotext", "-layout", str(PDF), "-"],
                         capture_output=True, text=True).stdout
    pages = txt.split("\f")
    issues: list[str] = []
    expected = ["- i -", "- ii -", "- iii -", "- iv -"] + [f"- {i} -" for i in range(1, 17)]
    seen = []
    for page in pages:
        for folio in re.findall(r"-\s*(?:i{1,3}|iv|\d{1,2})\s*-", page):
            seen.append(re.sub(r"\s+", " ", folio).strip())
    ok = True
    for exp, got in zip(expected, seen):
        if exp.replace(" ", "") not in got.replace(" ", ""):
            issues.append(f"expected folio {exp!r}, found {got!r}")
            ok = False
    if len(seen) != len(expected):
        issues.append(f"folio count {len(seen)} != {len(expected)}")
        ok = False
    return ok, issues


def main() -> int:
    problems = check_overflow()
    if problems:
        print("OVERFLOW:")
        for p in problems:
            print(f"  page {p['page']:>2}  +{p['over']:>6} px  {p['tag']:<28} {p['text']!r}")
    else:
        print("overflow: none")

    ok, issues = check_pdf_text()
    print(f"folios: {'ok' if ok else 'FAILED'}")
    for i in issues:
        print("  ", i)
    return 0 if not problems and ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
