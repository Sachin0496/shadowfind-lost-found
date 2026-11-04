"""Locate a Chromium-based browser for HTML -> PDF work.

Kept in one place so the paginator, the layout checker and the PDF renderer all
agree on which browser to use, and so a fresh clone works on macOS or Linux
without editing paths.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

CANDIDATES = [
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    # Linux / other
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
    "brave-browser",
    # Windows
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_chrome() -> str:
    """Return the path of a usable Chromium-based browser, or raise."""
    override = os.environ.get("CHROME") or os.environ.get("CHROMIUM_BIN")
    if override and Path(override).exists():
        return override

    for candidate in CANDIDATES:
        if os.path.isabs(candidate) or "/" in candidate or "\\" in candidate:
            if Path(candidate).exists():
                return candidate
        else:
            found = shutil.which(candidate)
            if found:
                return found

    sys.stderr.write(
        "No Chromium-based browser found.\n"
        "Install Chrome/Chromium, or set CHROME=/path/to/browser.\n"
    )
    raise SystemExit(1)


if __name__ == "__main__":
    print(find_chrome())
