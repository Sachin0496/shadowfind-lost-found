#!/usr/bin/env bash
# Render the three ShadowFind mockup pages to 2x PNGs with headless Chrome.
set -euo pipefail
cd "$(dirname "$0")"

# first Chromium-based browser found wins
CHROME=""
for c in \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
  "$(command -v google-chrome || true)" \
  "$(command -v chromium || true)"; do
  [ -n "$c" ] && [ -x "$c" ] && CHROME="$c" && break
done
[ -n "$CHROME" ] || { echo "No Chromium-based browser found." >&2; exit 1; }

SRC="$PWD"
OUT="$PWD/../figures"
mkdir -p "$OUT"

for page in login dashboard matches; do
  "$CHROME" \
    --headless --disable-gpu --hide-scrollbars \
    --force-device-scale-factor=2 \
    --window-size=1280,800 \
    --virtual-time-budget=2000 \
    --screenshot="$OUT/$page.png" \
    "file://$SRC/$page.html" >/dev/null 2>&1
  echo "rendered $page.png"
done

command -v sips >/dev/null && for page in login dashboard matches; do
  sips -g pixelWidth -g pixelHeight "$OUT/$page.png" | tail -n 2
done
