"""Print the built report HTML to PDF with headless Chrome.

Chrome's print pipeline is used because it renders real font metrics, so the
page geometry set in CSS is reproduced exactly: one HTML `.page` block becomes
exactly one A4 PDF page.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from browser import find_chrome

HERE = Path(__file__).resolve().parent
HTML = HERE / "ShadowFind_Report.html"
PDF = HERE / "ShadowFind_Report.pdf"


def render(out: Path = PDF) -> Path:
    chrome = find_chrome()
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=20000",
        "--force-color-profile=srgb",
        f"--print-to-pdf={out}",
        HTML.as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not out.exists():
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit("Chrome did not produce a PDF.")
    return out


if __name__ == "__main__":
    path = render()
    print(f"wrote {path} ({path.stat().st_size / 1e6:.2f} MB)")
