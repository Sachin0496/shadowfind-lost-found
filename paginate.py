"""Paginate the report by measuring, not by guessing.

Approach
--------
1. Emit every content block (self-contained, balanced HTML) into a single
   invisible column whose width equals the printed text column.
2. Load it in headless Chrome and read each block's rendered height.
3. Greedily pack the blocks into pages of the known text-frame height, keeping
   headings with the block that follows them and never splitting a table or a
   figure from its caption.
4. Emit the final document: cover, certificate, TOC, list of figures,
   abbreviations, then the packed body pages with running folios.

Because the heights come from the same engine that prints the PDF, the page
breaks are exact rather than estimated.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import content
from build_report import (
    ABBREVIATIONS, CERT, COVER, CSS, FIGURES, TEXT_WIDTH, TOC,
    abbreviations_page, figures_page, tables_page, toc_page,
)

HERE = Path(__file__).resolve().parent
from browser import find_chrome

CHROME = find_chrome()
OUT_HTML = HERE / "ShadowFind_Report.html"

# printed text frame: top 22.89 mm, bottom edge at 297-23.80 = 273.20 mm
PX_PER_MM = 96 / 25.4
FRAME_TOP_MM = 22.89
FRAME_BOTTOM_MM = 273.20
FRAME_H_PX = (FRAME_BOTTOM_MM - FRAME_TOP_MM) * PX_PER_MM
# keep the last line clear of the centred folio band (folio glyph top 284.35 mm)
SAFE_BOTTOM_MM = 277.0
PAGE_BUDGET_PX = (SAFE_BOTTOM_MM - FRAME_TOP_MM) * PX_PER_MM - 6

# vertical space consumed by p + p { margin-top: 3pt }
PARA_GAP_PX = 3.0 * 96 / 72


# ---------------------------------------------------------------------------
# block rendering
# ---------------------------------------------------------------------------
def render_block(block: tuple) -> str:
    kind = block[0]

    if kind == "chapter":
        return f'<div class="blk" data-kind="chapter"><h1 class="chapter">{block[1]}<br>{block[2]}</h1></div>'

    if kind == "plain":
        return f'<div class="blk" data-kind="plain"><h1 class="plain">{block[1]}</h1></div>'

    if kind == "h2":
        return f'<div class="blk" data-kind="h2"><h2 class="sec">{block[1]}</h2></div>'

    if kind == "h3":
        return f'<div class="blk" data-kind="h3"><h3 class="sub">{block[1]}</h3></div>'

    if kind == "p":
        return f'<div class="blk" data-kind="p"><p>{block[1]}</p></div>'

    if kind == "bullets":
        lis = "".join(f"<li>{i}</li>" for i in block[1])
        return f'<div class="blk" data-kind="list"><ul class="bullets">{lis}</ul></div>'

    if kind == "numbered":
        lis = "".join(f"<li>{i}</li>" for i in block[1])
        return f'<div class="blk" data-kind="list"><ol class="numbered">{lis}</ol></div>'

    if kind == "refs":
        lis = "".join(f"<li>{i}</li>" for i in block[1])
        return f'<div class="blk" data-kind="list"><ol class="refs">{lis}</ol></div>'

    if kind == "table":
        caption, widths, headers, rows, centre = block[1:6]
        # a split fragment carries (show_caption, show_header)
        show_caption, show_header = (block[6], block[7]) if len(block) > 6 else (True, True)
        cols = "".join(f'<col style="width:{w}">' for w in widths)
        head = "".join(f"<th>{h}</th>" for h in headers)
        body = []
        for r in rows:
            cells = "".join(f'<td{" class=\"c\"" if i in centre else ""}>{c}</td>'
                            for i, c in enumerate(r))
            body.append(f"<tr>{cells}</tr>")
        cap_html = f'<div class="tcap">{caption}</div>' if (show_caption and caption) else ""
        head_html = f"<tr>{head}</tr>" if show_header else ""
        html = (
            f'<div class="blk" data-kind="table">'
            f"{cap_html}"
            f'<table class="t small tight"><colgroup>{cols}</colgroup>'
            f"{head_html}{''.join(body)}</table></div>"
        )
        return html

    if kind == "figure":
        _, src, width, caption = block
        cap = f'<div class="figcap">{caption}</div>' if caption else ""
        return (
            f'<div class="blk" data-kind="figure"><div class="figblk">'
            f'<img src="{src}" style="width:{width}mm">{cap}</div></div>'
        )

    if kind == "workflow":
        _, src, caption, steps = block
        lis = "".join(f"<li>{s}</li>" for s in steps)
        return (
            f'<div class="blk" data-kind="workflow"><div class="wf">'
            f'<div class="wf-steps"><div class="wf-h">Steps of the workflow</div>'
            f'<ol class="wf-list">{lis}</ol></div>'
            f'<div class="wf-img"><img src="{src}" style="width:72mm"></div>'
            f'</div><div class="figcap wf-cap">{caption}</div></div>'
        )

    raise ValueError(f"unknown block kind {kind!r}")


# The measuring column must reproduce the printed text context exactly:
# same width, font size, line height and justification as the .flow box.
MEASURE_CSS = f"""
body {{ margin: 0; background: #fff; }}
#col {{
    position: absolute; left: 0; top: 0;
    width: {TEXT_WIDTH}mm;
    font-size: 12pt;
    line-height: 18.6pt;
    text-align: justify;
}}
"""


def measure(blocks: list[tuple]) -> list[dict]:
    """Return the rendered height in px of every block."""
    markup = "".join(render_block(b).replace('class="blk"', f'class="blk" id="b{i}"', 1)
                     for i, b in enumerate(blocks))
    doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}{MEASURE_CSS}</style>
</head><body><div id="col">{markup}</div>
<script>
window.addEventListener('load', () => {{
  const out = [];
  document.querySelectorAll('#col .blk').forEach((el, i) => {{
    const cs = getComputedStyle(el);
    const first = el.firstElementChild;
    const fcs = first ? getComputedStyle(first) : null;
    out.push({{
      h: el.getBoundingClientRect().height,
      mt: fcs ? (parseFloat(fcs.marginTop) || 0) : 0,
      mb: fcs ? (parseFloat(fcs.marginBottom) || 0) : 0,
      kind: el.dataset.kind,
    }});
  }});
  const pre = document.createElement('pre');
  pre.id = 'probe-out';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
}});
</script></body></html>"""

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        (tmpdir / "measure.html").write_text(doc, encoding="utf-8")
        # images resolve relative to the real figure directory
        for name in ("figures",):
            src = HERE / name
            if src.exists():
                (tmpdir / name).symlink_to(src, target_is_directory=True)
        cmd = [
            CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
            f"--user-data-dir={tmpdir / 'ud'}",
            "--virtual-time-budget=15000",
            "--window-size=1200,2000",
            "--dump-dom", (tmpdir / "measure.html").as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)

    m = re.search(r'<pre id="probe-out">(.*?)</pre>', proc.stdout, re.S)
    if not m:
        raise SystemExit("measurement probe did not run:\n" + proc.stdout[:2000])
    raw = m.group(1)
    raw = (raw.replace("&quot;", '"').replace("&amp;", "&")
              .replace("&lt;", "<").replace("&gt;", ">"))
    return json.loads(raw)


# ---------------------------------------------------------------------------
# packing
# ---------------------------------------------------------------------------
KEEP_WITH_NEXT = {"chapter", "plain", "h2", "h3"}


def row_heights(block: tuple) -> list[float]:
    """Measure each row of one table separately, in px."""
    _, caption, widths, headers, rows, centre = block
    frags = []
    for i in range(len(rows)):
        frags.append(("table", caption, widths, headers, [rows[i]], centre,
                      i == 0, True))
    hs = measure(frags)
    # first fragment includes the caption; strip it so the rows are comparable
    cap_h = 0.0
    if len(frags) > 1:
        sep = measure([("table", caption, widths, headers, [], centre, True, True),
                       ("table", caption, widths, headers, rows[:1], centre, False, True)])
        cap_h = sep[0]["h"]
    per_row = []
    for i, hh in enumerate(hs):
        h = hh["h"] - (cap_h if i == 0 else 0.0)
        per_row.append(h)
    return per_row, cap_h


def split_tables(blocks: list[tuple], heights: list[dict],
                 budget: float) -> tuple[list[tuple], list[dict]]:
    """Split tables that can never fit a page into header-carrying chunks."""
    out_blocks, out_heights = [], []
    for block, h in zip(blocks, heights):
        if block[0] != "table" or h["h"] <= budget:
            out_blocks.append(block)
            out_heights.append(h)
            continue

        _, caption, widths, headers, rows, centre = block
        per_row, cap_h = row_heights(block)
        header_block = ("table", caption, widths, headers, [], centre, True, True)
        header_h = measure([header_block])[0]["h"]

        chunks: list[tuple] = []
        cur: list[list[str]] = []
        used = header_h
        for row, rh in zip(rows, per_row):
            if cur and used + rh > budget:
                chunks.append(tuple(cur))
                cur, used = [], header_h
            cur.append(row)
            used += rh
        if cur:
            chunks.append(tuple(cur))

        for i, chunk in enumerate(chunks):
            frag = ("table", caption, widths, headers, list(chunk), centre,
                    i == 0, True)
            out_blocks.append(frag)
            out_heights.append(measure([frag])[0])
    return out_blocks, out_heights


def _table_parts(block: tuple) -> tuple[float, list[float]]:
    """Return (header+caption height, per-row heights) in px for one table."""
    caption, widths, headers, rows, centre = block[1:6]
    probe = [("table", caption, widths, headers, [], centre, True, True)]
    for i in range(len(rows)):
        probe.append(("table", caption, widths, headers, [rows[i]], centre, True, True))
    hs = measure(probe)
    cap_head = hs[0]["h"]
    per_row = [h["h"] - cap_head for h in hs[1:]]
    return cap_head, per_row


def _fragment(block: tuple, rows: list[list[str]], *, caption: bool, header: bool) -> tuple:
    cap, widths, headers, _rows, centre = block[1:6]
    return ("table", cap, widths, headers, list(rows), centre, caption, header)


def paginate(blocks: list[tuple], heights: list[dict]) -> list[list[int]]:
    """Greedy page packing; oversized tables are split at the fill point."""
    # Working copy: entries are (block, height) so a table can be replaced by
    # two fragments without disturbing indices elsewhere.
    work: list[list] = [[b, h] for b, h in zip(blocks, heights)]
    pages: list[list[list]] = []
    current: list[list] = []
    used = 0.0
    i = 0

    def gap(a, b) -> float:
        return max(a[1]["mb"], b[1]["mt"])

    while i < len(work):
        entry = work[i]
        kind = entry[0][0]

        # a heading must travel with the block that follows it
        group = [i]
        j = i
        while j < len(work) and work[j][0][0] in KEEP_WITH_NEXT and j + 1 < len(work):
            j += 1
            group.append(j)

        need = sum(work[k][1]["h"] for k in group)
        for a, b in zip(group, group[1:]):
            need += gap(work[a], work[b])
        if current:
            need += gap(current[-1], work[group[0]])

        force_break = kind == "chapter" and current
        remaining = PAGE_BUDGET_PX - used - (gap(current[-1], entry) if current else 0)

        # ---- split a table that does not fit in what is left -------------
        if (not force_break and current and need > PAGE_BUDGET_PX - used
                and kind == "table" and len(entry[0][4]) > 2):
            block = entry[0]
            cap_head, per_row = _table_parts(block)
            room = remaining - 4
            k = 0
            acc = cap_head
            while k < len(block[4]) and acc + per_row[k] <= room:
                acc += per_row[k]
                k += 1
            # never leave a sliver: need at least 2 rows kept AND 2 rows moved
            if k >= 2 and (len(block[4]) - k) >= 2 and k < len(block[4]):
                head_rows = block[4][:k]
                tail_rows = block[4][k:]
                head = [_fragment(block, head_rows, caption=True, header=True), None]
                tail = [_fragment(block, tail_rows, caption=False, header=True), None]
                head[1] = measure([head[0]])[0]
                tail[1] = measure([tail[0]])[0]
                work[i:i + 1] = [head, tail]
                continue

        group_has_heading = kind in KEEP_WITH_NEXT
        if current and (need > PAGE_BUDGET_PX - used or force_break):
            pages.append(current)
            current = []
            used = 0.0
            need = sum(work[k][1]["h"] for k in group)
            for a, b in zip(group, group[1:]):
                need += gap(work[a], work[b])

        for k in group:
            if current:
                used += gap(current[-1], work[k])
            current.append(work[k])
            used += work[k][1]["h"]

        # a heading must never be the last thing on a page
        if current and current[-1][0][0] in KEEP_WITH_NEXT and j + 1 >= len(work):
            pass
        i = j + 1

    if current:
        pages.append(current)

    # repair: no page may end with a heading
    for idx in range(len(pages) - 1):
        moved = []
        while pages[idx] and pages[idx][-1][0][0] in KEEP_WITH_NEXT:
            moved.insert(0, pages[idx].pop())
        if moved:
            if not pages[idx]:
                pages[idx + 1][0:0] = moved
            else:
                pages[idx + 1][0:0] = moved
    pages = [p for p in pages if p]
    pages = balance(pages)
    for idx in range(len(pages) - 1):
        moved = []
        while pages[idx] and pages[idx][-1][0][0] in KEEP_WITH_NEXT:
            moved.insert(0, pages[idx].pop())
        if moved:
            pages[idx + 1][0:0] = moved
    return [p for p in pages if p]


def _fill(entries) -> float:
    total = sum(e[1]["h"] for e in entries)
    for a, b in zip(entries, entries[1:]):
        total += max(a[1]["mb"], b[1]["mt"])
    return total


def balance(pages, *, min_fill=0.80):
    """Even the fill across pages without ever orphaning a heading.

    A page whose content is much sparser than its neighbours looks like a
    mistake in a printed report, so trailing units are slid forward. A unit is
    either a single block or a heading together with the block it introduces.
    """
    def units(page):
        """Split a page into movable units, heading+next kept together."""
        out, i = [], 0
        while i < len(page):
            if page[i][0][0] in KEEP_WITH_NEXT and i + 1 < len(page):
                out.append(page[i:i + 2])
                i += 2
            else:
                out.append(page[i:i + 1])
                i += 1
        return out

    for idx in range(1, len(pages)):
        for _ in range(14):
            nxt, prev = pages[idx], pages[idx - 1]
            if not prev or not nxt:
                break
            if _fill(nxt) >= PAGE_BUDGET_PX * min_fill:
                break
            us = units(prev)
            if len(us) < 2:          # keep at least one unit behind
                break
            unit = us[-1]
            trial_prev = [e for u in us[:-1] for e in u]
            trial_next = unit + nxt
            if _fill(trial_next) > PAGE_BUDGET_PX:
                break
            if _fill(trial_prev) < PAGE_BUDGET_PX * 0.55:
                break
            pages[idx - 1] = trial_prev
            pages[idx] = trial_next
    return pages


# ---------------------------------------------------------------------------
# document assembly
# ---------------------------------------------------------------------------
def locate_sections(packed, blocks=None) -> dict[str, int]:
    """Map a heading's text to the page number it actually prints on."""
    found: dict[str, int] = {}
    for page_no, entries in enumerate(packed, start=1):
        for e in entries:
            b = e[0]
            if b[0] in ("h2", "h3"):
                # "3.2.1 Database Module" -> "Database Module"
                found[b[1].split(" ", 1)[1].strip()] = page_no
            elif b[0] == "chapter":
                found[b[2].strip()] = page_no
            elif b[0] == "plain":
                found[b[1].strip()] = page_no
            elif b[0] == "table":
                # caption already reads "Table 2.1 ..."; a split table reports
                # the page its caption first appears on
                key = b[1].split(" ", 2)[0] + " " + b[1].split(" ", 2)[1]
                shows_caption = b[6] if len(b) > 6 else True
                if shows_caption and key not in found:
                    found[key] = page_no
            elif b[0] == "figure" and b[3]:
                found[b[3].strip()] = page_no
            elif b[0] == "workflow":
                found[b[2].strip()] = page_no
    return found


def body_pages(packed, blocks=None) -> list[str]:
    out = []
    for page_no, entries in enumerate(packed, start=1):
        inner = "\n".join(render_block(e[0]) for e in entries)
        cont = " cont" if page_no > 1 else ""
        out.append(
            f'<div class="page"><div class="frame"></div>'
            f'<div class="flow{cont}">{inner}</div>'
            f'<div class="folio">- {page_no} -</div></div>'
        )
    return out


def build() -> Path:
    blocks = content.DOC
    heights = measure(blocks)
    blocks, heights = split_tables(blocks, heights, PAGE_BUDGET_PX - 24)
    packed = paginate(blocks, heights)
    sections = locate_sections(packed, blocks)
    pages = [COVER, CERT, toc_page(sections), tables_page(sections),
             figures_page(sections), abbreviations_page()]
    pages += body_pages(packed, blocks)
    doc = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        "<title>ShadowFind - Project Report</title>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n" + "\n".join(pages) + "\n</body>\n</html>\n"
    )
    OUT_HTML.write_text(doc, encoding="utf-8")
    print(f"{len(pages)} pages  (front matter {len(pages) - len(packed)} + body {len(packed)})")
    for pno, entries in enumerate(packed, start=1):
        used = sum(e[1]["h"] for e in entries)
        first = entries[0][0][0]
        print(f"  page {pno:>2}: {len(entries):>2} blocks  {used:7.1f}px  first={first}")
    return OUT_HTML


if __name__ == "__main__":
    print(build())
