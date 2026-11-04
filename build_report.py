"""Assemble the ShadowFind report HTML from the front matter and the chapters.

Every printed page is one `.page` block of fixed A4 size, so the result is
deterministic: what the browser lays out is exactly one PDF page. The
companion script `render_pdf.py` prints it, and `check_layout.py` verifies
that no page block silently overflows.
"""

from __future__ import annotations

import re
from pathlib import Path

import content

HERE = Path(__file__).resolve().parent
OUT_HTML = HERE / "ShadowFind_Report.html"

mm = lambda v: f"{v:.3f}mm"

# page geometry (A4, mm) - measured from the reference PDF
PAGE_W, PAGE_H = 210.0, 297.0
FRAME_INSET = 8.47          # 24 pt frame inset
TEXT_LEFT = 30.0            # 85.0 pt
TEXT_WIDTH = 156.26         # 443 pt
BODY_TOP = 22.89            # 64.88 pt box top; first glyph lands on 65.6 pt
BODY_TOP_CONT = 22.34       # same glyph line, but the box starts with 12 pt text
BODY_BOTTOM_MARGIN = 23.80  # distance from the page bottom to the text frame
FOOTER_Y = 284.35           # folio glyph top at 805.9 pt

CSS = f"""
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; background: #fff; }}
body {{
    font-family: "Times New Roman", Times, serif;
    color: #000;
    -webkit-font-smoothing: antialiased;
    text-rendering: geometricPrecision;
}}

.page {{
    position: relative;
    width: {mm(PAGE_W)};
    height: {mm(PAGE_H)};
    overflow: hidden;
    page-break-after: always;
    break-after: page;
    background: #fff;
}}
.page:last-child {{ page-break-after: auto; break-after: auto; }}
.frame {{
    position: absolute;
    top: {mm(FRAME_INSET)}; left: {mm(FRAME_INSET)};
    right: {mm(FRAME_INSET)}; bottom: {mm(FRAME_INSET)};
    border: 0.55pt solid #000;
}}
.flow {{
    position: absolute;
    left: {mm(TEXT_LEFT)};
    width: {mm(TEXT_WIDTH)};
    top: {mm(BODY_TOP)};
    bottom: {mm(BODY_BOTTOM_MARGIN)};
    font-size: 12pt;
    line-height: 18.6pt;
    text-align: justify;
}}
.flow.cont {{ top: {mm(BODY_TOP_CONT)}; }}
.flow.cert {{ top: {mm(29.98)}; }}
.folio {{
    position: absolute;
    left: 0; right: 0;
    top: {mm(FOOTER_Y)};
    text-align: center;
    font-size: 10pt;
    line-height: 12pt;
}}

p {{ margin: 0; }}
.blk {{ display: flow-root; }}
p + p {{ margin-top: 3.0pt; }}
.blk > p + p {{ margin-top: 0; }}
.ti {{ text-indent: 12.7mm; }}
h1.chapter {{
    margin-top: 0;
    font-size: 14pt; line-height: 17.5pt; font-weight: bold;
    text-align: center; margin: 0 0 21pt 0;
}}
h1.plain {{
    font-size: 14pt; line-height: 17.5pt; font-weight: bold;
    text-align: center; margin: 0 0 13pt 0;
}}
h2.sec {{ font-size: 12pt; line-height: 18.6pt; font-weight: bold; margin: 9pt 0 0 0; }}
h2.sec.first {{ margin-top: 0; }}
h2.sub, h3.sub {{ font-size: 12pt; line-height: 18.6pt; font-weight: bold; margin: 8pt 0 0 0; text-align: left; }}
ul.bullets, ol.numbered {{ margin: 0; padding-left: 9.5mm; }}
ul.bullets li, ol.numbered li {{ margin: 0; text-align: justify; }}
ol.numbered.plain li {{ text-align: left; }}

/* cover - each line sits on the template's measured baseline */
.cover-emblem {{ position: absolute; left: 0; right: 0; top: 32.9mm; text-align: center; }}
.cover-emblem img {{ width: 26.4mm; }}
.cover-line {{ position: absolute; left: 0; right: 0; text-align: center; }}
.cl-inst {{ top: 61.55mm; font-size: 12pt; font-weight: bold; line-height: 15.5pt; }}
.cl-inst-sub {{ top: 67.15mm; font-size: 10pt; font-weight: bold; line-height: 12pt; }}
.cl-main {{ top: 80.60mm; font-size: 20pt; font-weight: bold; line-height: 24pt; }}
.cl-sub1 {{ top: 90.30mm; font-size: 14pt; font-weight: bold; line-height: 17pt; }}
.cl-sub2 {{ top: 96.00mm; font-size: 14pt; font-weight: bold; line-height: 17pt; }}
.cl-mini {{ top: 113.30mm; font-size: 12pt; font-weight: bold; line-height: 16pt; }}
.cl-submit {{ top: 128.20mm; font-size: 12pt; font-weight: bold; font-style: italic; line-height: 16pt; }}
.cl-name1 {{ top: 139.90mm; font-size: 12pt; font-weight: bold; line-height: 16pt; }}
.cl-subj {{ top: 152.40mm; font-size: 12pt; font-weight: bold; line-height: 16pt; }}
.cl-in {{ top: 162.50mm; font-size: 12pt; font-weight: bold; font-style: italic; line-height: 16pt; }}
.cl-dept {{ top: 172.30mm; font-size: 12pt; font-weight: bold; line-height: 16pt; }}
.cl-kpriet {{ top: 180.50mm; font-size: 12pt; font-weight: bold; line-height: 16pt; }}
.cl-place {{ top: 199.10mm; font-size: 12pt; font-weight: bold; line-height: 16pt; }}
.cl-date {{ top: 204.60mm; font-size: 12pt; font-weight: bold; line-height: 16pt; }}
.rule {{ display: inline-block; width: 52mm; border-bottom: 0.9pt solid #000; height: 1pt; }}

/* certificate */
.cert-title {{ text-align: center; font-size: 14pt; font-weight: bold; margin: 0 0 21pt 0; }}
.cert-body p {{ text-indent: 12.7mm; margin: 0 0 3pt 0; }}
.sigwrap {{ margin-top: 30pt; width: 100%; overflow: hidden; }}
.sig {{
    float: left; width: 50%; border: 1pt solid #000;
    padding: 3pt 5pt 5pt 5pt; font-size: 11.6pt; line-height: 15.6pt;
    min-height: 44mm;
}}
.sig b {{ display: block; margin-bottom: 3pt; }}
.viva {{
    position: absolute; left: {mm(TEXT_LEFT)}; width: {mm(TEXT_WIDTH)};
    top: 208mm; font-size: 12pt; font-weight: bold;
}}
.viva-line {{ display: block; text-align: justify; text-align-last: justify; }}
.examiners {{
    position: absolute; left: {mm(TEXT_LEFT)}; width: {mm(TEXT_WIDTH)};
    top: 254mm; font-size: 12pt; font-weight: bold; overflow: hidden;
}}
.examiners span {{ float: left; width: 50%; }}

/* tables */
table.t {{
    border-collapse: collapse; width: 100%; margin: 0 auto 4pt auto;
    font-size: 11pt; line-height: 13.4pt;
}}
table.t th, table.t td {{
    border: 0.75pt solid #000; padding: 1.1pt 3pt 1.4pt 3pt;
    vertical-align: top; text-align: left;
}}
table.t th {{ background: #D9D9D9; font-weight: bold; text-align: center; vertical-align: middle; }}
table.t td.c {{ text-align: center; }}
table.t.small {{ font-size: 10.5pt; line-height: 12.9pt; }}
table.t.tight td, table.t.tight th {{ padding: 0.8pt 3pt 1.1pt 3pt; }}
.tcap {{
    text-align: center; font-size: 11pt; line-height: 13.4pt;
    font-weight: bold; margin: 9pt 0 3pt 0;
}}
.after-table {{ margin-top: 6pt; }}

/* figures */
.figblk {{ text-align: center; margin: 9pt 0 7pt 0; }}
.figblk img {{ display: block; margin: 0 auto; }}
.figcap {{
    text-align: center; font-size: 11pt; line-height: 13.4pt;
    font-weight: bold; margin-top: 3pt;
}}

/* contents */
table.toc {{ width: 100%; border-collapse: collapse; font-size: 11pt; line-height: 15.2pt; }}
table.toc td {{ border: 0.75pt solid #000; padding: 1pt 4pt 1.4pt 4pt; vertical-align: top; }}
table.toc th {{
    border: 0.75pt solid #000; background: #D9D9D9; font-size: 11pt;
    font-weight: bold; text-align: center; padding: 1.4pt 4pt 1.8pt 4pt;
    vertical-align: middle; line-height: 13.5pt;
}}
table.toc td.no {{ text-align: center; }}
table.toc td.pg {{ text-align: center; }}
table.toc td.ttl.lvl0 {{ font-weight: bold; }}
table.toc td.ttl.lvl1 {{ padding-left: 15pt; }}
table.toc td.ttl.lvl2 {{ padding-left: 29pt; }}

table.abbr {{ width: 100%; border-collapse: collapse; font-size: 12pt; line-height: 18.6pt; }}
table.abbr td {{ padding: 0; vertical-align: top; }}
table.abbr td.k {{ width: 31mm; }}
table.abbr td.v {{ text-align: left; }}

ol.refs {{ margin: 0; padding-left: 0; list-style: none; counter-reset: ref; }}
ol.refs li {{
    counter-increment: ref; margin: 0 0 6pt 0; padding-left: 8.5mm;
    text-indent: -8.5mm; text-align: left; line-height: 18.6pt;
    word-spacing: normal;
}}
ol.refs li::before {{ content: counter(ref) ". "; }}

/* workflow two-column block */
.wf {{ display: flex; gap: 6mm; margin-top: 8pt; align-items: flex-start; }}
.wf-steps {{ width: 76mm; flex: none; }}
.wf-img {{ flex: 1; text-align: center; }}
.wf-img img {{ display: block; margin: 0 auto; }}
.wf-cap {{ text-align: center; margin-top: 5pt; }}
.wf-h {{ font-size: 12pt; font-weight: bold; line-height: 18pt; margin-bottom: 2pt; }}
ol.wf-list {{ padding-left: 6.5mm; font-size: 10.5pt; line-height: 13.2pt; }}
ol.wf-list li {{ margin-bottom: 2.4pt; text-align: left; }}
"""


# ---------------------------------------------------------------------------
# front matter
# ---------------------------------------------------------------------------
COVER = """
<div class="page">
  <div class="frame"></div>
  <div class="cover-emblem"><img src="figures/kpr_emblem.png" alt=""></div>
  <div class="cover-line cl-inst">KPR INSTITUTE OF ENGINEERING AND TECHNOLOGY</div>
  <div class="cover-line cl-inst-sub">(Autonomous Institution)</div>
  <div class="cover-line cl-main">SHADOWFIND</div>
  <div class="cover-line cl-sub1">SHADOW SILHOUETTE MATCHING FOR</div>
  <div class="cover-line cl-sub2">LOST AND FOUND ITEMS</div>
  <div class="cover-line cl-mini">A MINI PROJECT REPORT</div>
  <div class="cover-line cl-submit">Submitted by</div>
  <div class="cover-line cl-name1">SACHIN A S(24CS171)</div>
  <div class="cover-line cl-subj">U21CS504 - Web Technology</div>
  <div class="cover-line cl-in">in</div>
  <div class="cover-line cl-dept">DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING</div>
  <div class="cover-line cl-kpriet">KPRIET</div>
  <div class="cover-line cl-place">ARASUR, COIMBATORE - 641 407</div>
  <div class="cover-line cl-date">NOVEMBER 2026</div>
</div>
"""

CERT = """
<div class="page">
  <div class="frame"></div>
  <div class="flow">
    <div class="cert-title">BONAFIDE CERTIFICATE</div>
    <div class="cert-body">
      <p>Certified that this project report &#8220;<b>SHADOWFIND &#8211; SHADOW SILHOUETTE MATCHING
      FOR LOST AND FOUND ITEMS</b>&#8221; is the bonafide work of
      &#8220;<b>SACHIN A S (24CS171)</b>&#8221; who carried out the project work under my
      supervision.</p>
    </div>
    <div class="sigwrap">
      <div class="sig"><b>Dr. MIRUNA JOE AMALI</b>HEAD OF THE DEPARTMENT<br>Professor<br>
        Computer Science and Engineering<br>KPR Institute of Engineering and Technology<br>
        Arasur, Coimbatore &#8211; 641407</div>
      <div class="sig"><b>RAJESHKUMAR S</b>SUPERVISOR,<br>Assistant Professor III<br>
        Computer Science and Engineering<br>KPR Institute of Engineering and Technology<br>
        Arasur, Coimbatore &#8211; 641407</div>
    </div>
  </div>
  <div class="viva"><span class="viva-line">Submitted for the University Mini Project Viva-Voce
    held on ____________________</span></div>
  <div class="examiners"><span>INTERNAL EXAMINER</span><span>EXTERNAL EXAMINER</span></div>
  <div class="folio">- i -</div>
</div>
"""

TOC = [
    ("", "LIST OF TABLES", "iii", 0),
    ("", "LIST OF FIGURES", "iv", 0),
    ("", "LIST OF ABBREVIATIONS", "v", 0),
    ("1", "ABSTRACT", "1", 0),
    ("2", "INTRODUCTION", "2", 0),
    ("2.1", "Background and Need for the Project", "2", 1),
    ("2.2", "Objectives", "2", 2),
    ("2.3", "Scope", "3", 2),
    ("2.4", "Development Plan", "3", 2),
    ("3", "IMPLEMENTATION", "4", 0),
    ("3.1", "Tech Stack", "4", 1),
    ("3.1.1", "HTML", "", 2),
    ("3.1.2", "CSS and Bootstrap", "", 2),
    ("3.1.3", "Python and Flask", "", 2),
    ("3.1.4", "OpenCV and the Shadow Pipeline", "", 2),
    ("3.1.5", "SQLite", "", 2),
    ("3.1.6", "Development and Testing Tools", "", 2),
    ("3.2", "Modules", "5", 1),
    ("3.2.1", "Database Module", "5", 2),
    ("3.2.2", "Registration and Login Module", "6", 2),
    ("3.2.3", "Report and Browse Items Module", "6", 2),
    ("3.2.4", "Shadow Matching Module", "7", 2),
    ("3.2.5", "Claim and Handover Module", "7", 2),
    ("3.2.6", "Security Module", "7", 2),
    ("3.3", "Testing Approach", "8", 1),
    ("3.4", "Workflow of the Application", "8", 1),
    ("4", "OUTCOME", "9", 0),
    ("4.1", "Implementation Outcome", "9", 1),
    ("4.2", "Module-wise Outcome with Screenshots", "9", 1),
    ("4.3", "Comparison with Existing Methods", "10", 1),
    ("4.4", "Discussion and Limitations", "11", 1),
    ("5", "CONCLUSION", "12", 0),
    ("5.1", "Future Scope", "12", 1),
    ("", "REFERENCES", "13", 0),
]


def toc_page(sections: dict[str, int] | None = None) -> str:
    sections = sections or {}
    rows = []
    for no, title, page, lvl in TOC:
        real = sections.get(title.strip())
        shown = real if real is not None else ("" if not page else page)
        rows.append(
            f'<tr><td class="no">{no}</td><td class="ttl lvl{lvl}">{title}</td>'
            f'<td class="pg">{shown}</td></tr>'
        )
    rows = "".join(rows)
    head = ('<tr><th style="width:19mm">CHAPTER<br>NO</th><th>TITLE</th>'
            '<th style="width:22mm">PAGE NO</th></tr>')
    return (
        '<div class="page"><div class="frame"></div><div class="flow">'
        '<h1 class="plain">TABLE OF CONTENTS</h1>'
        f'<table class="toc">{head}{rows}</table></div>'
        '<div class="folio">- ii -</div></div>'
    )


TABLES = [
    ("2.1", "PROBLEMS IN THE EXISTING METHODS OF TRACKING LOST ITEMS"),
    ("2.2", "DEVELOPMENT PLAN OF SHADOWFIND"),
    ("3.1", "TECHNOLOGY STACK"),
    ("3.2", "CORE DATA ENTITIES"),
    ("3.3", "TYPE AND STATUS VALUES OF ITEMS AND CLAIMS"),
    ("3.4", "SHADOW MATCHING PARAMETERS"),
    ("3.5", "SECURITY CONTROLS IMPLEMENTED IN THE APPLICATION"),
    ("3.6", "TESTING TOOLS AND CHECKS"),
    ("4.1", "EXISTING METHODS VERSUS SHADOWFIND"),
    ("4.2", "SILHOUETTE MATCHING ACCURACY ON 96 LABELLED PAIRS"),
    ("4.3", "TOP-1 ACCURACY BY LIGHTING CONDITION"),
]

FIGURES = [
    ("3.1", "SYSTEM ARCHITECTURE OF SHADOWFIND", "4"),
    ("3.2", "ENTITY RELATIONSHIP DIAGRAM OF THE DATABASE", "5"),
    ("3.3", "FLOWCHART OF THE SHADOWFIND WORKFLOW", "8"),
    ("4.1", "LOGIN MODULE", "9"),
    ("4.2", "STUDENT DASHBOARD AND ITEM UPLOAD", "10"),
    ("4.3", "CLAIM AND HANDOVER MODULE", "10"),
]


def tables_page(sections: dict[str, int] | None = None) -> str:
    sections = sections or {}
    out = []
    for no, title in TABLES:
        real = sections.get(f"Table {no}")
        out.append(
            f'<tr><td class="no">{no}</td><td class="ttl lvl1" style="padding-left:5pt">'
            f'{title}</td><td class="pg">{real if real is not None else ""}</td></tr>'
        )
    rows = "".join(out)
    head = ('<tr><th style="width:22mm">TABLE NO</th><th>TABLE NAME</th>'
            '<th style="width:22mm">PAGE NO</th></tr>')
    return (
        '<div class="page"><div class="frame"></div><div class="flow">'
        '<h1 class="plain">LIST OF TABLES</h1>'
        f'<table class="toc">{head}{rows}</table></div>'
        '<div class="folio">- iii -</div></div>'
    )


def figures_page(sections: dict[str, int] | None = None) -> str:
    sections = sections or {}
    out = []
    for no, title, pg in FIGURES:
        cap = f"Fig {no} {title}"
        real = sections.get(cap)
        out.append(
            f'<tr><td class="no">{no}</td><td class="ttl lvl1" style="padding-left:5pt">{title}</td>'
            f'<td class="pg">{real if real is not None else pg}</td></tr>'
        )
    rows = "".join(out)
    head = ('<tr><th style="width:22mm">FIGURE NO</th><th>FIGURE NAME</th>'
            '<th style="width:22mm">PAGE NO</th></tr>')
    return (
        '<div class="page"><div class="frame"></div><div class="flow">'
        '<h1 class="plain">LIST OF FIGURES</h1>'
        f'<table class="toc">{head}{rows}</table></div>'
        '<div class="folio">- iv -</div></div>'
    )


ABBREVIATIONS = [
    ("CSRF", "CROSS-SITE REQUEST FORGERY"),
    ("CSS", "CASCADING STYLE SHEETS"),
    ("DBMS", "DATABASE MANAGEMENT SYSTEM"),
    ("ER", "ENTITY RELATIONSHIP"),
    ("FK", "FOREIGN KEY"),
    ("HTML", "HYPERTEXT MARKUP LANGUAGE"),
    ("HTTP", "HYPERTEXT TRANSFER PROTOCOL"),
    ("IDE", "INTEGRATED DEVELOPMENT ENVIRONMENT"),
    ("IoU", "INTERSECTION OVER UNION"),
    ("MVC", "MODEL VIEW CONTROLLER"),
    ("ORM", "OBJECT RELATIONAL MAPPING"),
    ("OWASP", "OPEN WORLDWIDE APPLICATION SECURITY PROJECT"),
    ("PK", "PRIMARY KEY"),
    ("SEO", "SEARCH ENGINE OPTIMISATION"),
    ("SQL", "STRUCTURED QUERY LANGUAGE"),
    ("UI", "USER INTERFACE"),
    ("URL", "UNIFORM RESOURCE LOCATOR"),
    ("WSGI", "WEB SERVER GATEWAY INTERFACE"),
    ("XSS", "CROSS-SITE SCRIPTING"),
    ("ZAP", "ZED ATTACK PROXY"),
]


def abbreviations_page() -> str:
    rows = "".join(f'<tr><td class="k">{k}</td><td class="v">{v}</td></tr>'
                   for k, v in ABBREVIATIONS)
    return (
        '<div class="page"><div class="frame"></div><div class="flow">'
        '<h1 class="plain">LIST OF ABBREVIATIONS</h1>'
        f'<table class="abbr">{rows}</table></div>'
        '<div class="folio">- v -</div></div>'
    )


# ---------------------------------------------------------------------------
def body_pages() -> list[str]:
    pages = []
    for i, blocks in enumerate(content.PAGES, start=1):
        inner = "\n".join(blocks)
        cont = " cont" if i > 1 else ""
        pages.append(
            f'<div class="page"><div class="frame"></div>'
            f'<div class="flow{cont}">{inner}</div>'
            f'<div class="folio">- {i} -</div></div>'
        )
    return pages


def build() -> Path:
    pages = [COVER, CERT, toc_page(), figures_page(), abbreviations_page()]
    pages += body_pages()
    doc = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        "<title>ShadowFind - Project Report</title>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n" + "\n".join(pages) + "\n</body>\n</html>\n"
    )
    OUT_HTML.write_text(doc, encoding="utf-8")
    return OUT_HTML


if __name__ == "__main__":
    print(build())
    print(f"{len(content.PAGES) + 5} pages")
