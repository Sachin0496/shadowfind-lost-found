"""Generate the diagrams used in the ShadowFind project report.

Figures
-------
fig_3_1_architecture.png   wide, dark boxed system architecture (Fig 3.1)
fig_3_2_er.png             entity-relationship diagram, white ground   (Fig 3.2)
fig_3_3_flowchart.png      tall workflow flowchart, dark ground         (Fig 3.3)

The visual language mirrors the supplied KPR report template: near-black
background, #00284D rounded boxes and white sans-serif labels for the dark
figures, #1F3A6E headers on white for the ER diagram.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(parents=True, exist_ok=True)

SANS = "DejaVu Sans"
MONO = "DejaVu Sans Mono"
DARK_BG = "#000000"
BOX = "#00284D"
BOX_EDGE = "#0C4A7A"
BOX_LIGHT = "#0A3A63"
CONTAINER = "#001A33"
CONTAINER_EDGE = "#123A5C"
WHITE = "#FFFFFF"
MUTED = "#9FB6CC"
LINK = "#7FA8CC"

ER_HEAD = "#1F3A6E"
ER_TEXT = "#111111"


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------
def rbox(ax, x, y, w, h, *, fc=BOX, ec=BOX_EDGE, lw=1.0, radius=0.09, z=2):
    """Rounded rectangle whose (x, y) is the BOTTOM-LEFT corner."""
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle=f"round,pad=0,rounding_size={radius}",
            linewidth=lw, edgecolor=ec, facecolor=fc, zorder=z,
        )
    )


def text_w(ax, text, size, weight="normal", family=SANS, fig=None):
    """Width of `text` in data units for the given point size."""
    fig = fig or ax.figure
    renderer = fig.canvas.get_renderer()
    t = ax.text(0, 0, text, fontsize=size, fontweight=weight, family=family)
    bb = t.get_window_extent(renderer=renderer)
    t.remove()
    return bb.width * ax.get_xlim()[1] / ax.figure.bbox.width


def fit_text(ax, x, y, text, max_w, base=7.0, *, color=WHITE, weight="bold",
             ha="center", va="center", family=SANS, min_size=4.0, z=5):
    """Draw `text` centred at (x, y), shrinking it until it fits inside max_w."""
    size = base
    while size > min_size:
        if text_w(ax, text, size, weight=weight, family=family) <= max_w:
            break
        size -= 0.15
    ax.text(x, y, text, ha=ha, va=va, fontsize=size, color=color, fontweight=weight,
            family=family, zorder=z)
    return size


def label(ax, x, y, text, *, size=7.0, color=WHITE, weight="bold", ha="center",
          va="center", z=5, style="normal", family=SANS):
    ax.text(x, y, text, ha=ha, va=va, fontsize=size, color=color, fontweight=weight,
            family=family, zorder=z, fontstyle=style)


def arrow(ax, start, end, *, color=LINK, lw=1.1, mut=7, z=3, ls="-", rad=0.0):
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle="-|>", mutation_scale=mut, linewidth=lw,
            color=color, connectionstyle=f"arc3,rad={rad}", zorder=z,
            linestyle=ls, shrinkA=0, shrinkB=0,
        )
    )


def polyline(ax, pts, *, color=LINK, lw=1.0, z=2, ls="-"):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=color, lw=lw, zorder=z, ls=ls,
            solid_capstyle="butt", solid_joinstyle="miter")


# ---------------------------------------------------------------------------
# Fig 3.1  system architecture
# ---------------------------------------------------------------------------
def architecture() -> Path:
    W, H = 6.55, 1.55
    fig = plt.figure(figsize=(W, H), dpi=400)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_axis_off()
    ax.set_facecolor(DARK_BG)

    # 1 presentation
    rbox(ax, 0.05, 0.55, 0.98, 0.46)
    label(ax, 0.54, 0.885, "HTML  CSS", size=6.2)
    label(ax, 0.54, 0.665, "Bootstrap", size=6.2)

    # 2 browser
    rbox(ax, 1.20, 0.34, 1.10, 0.88)
    label(ax, 1.75, 1.035, "Student Interface", size=6.1)
    label(ax, 1.75, 0.885, "(browser)", size=5.3, weight="normal", color=MUTED)
    label(ax, 1.75, 0.705, "camera capture", size=5.1, weight="normal", color=MUTED)
    label(ax, 1.75, 0.575, "item form · claims", size=5.1, weight="normal", color=MUTED)
    label(ax, 1.75, 0.445, "match list", size=5.1, weight="normal", color=MUTED)

    # 3 flask container
    rbox(ax, 2.46, 0.10, 1.90, 1.42, fc=CONTAINER, ec=CONTAINER_EDGE, lw=1.0)
    label(ax, 3.41, 1.365, "FLASK APPLICATION", size=6.0)
    label(ax, 3.41, 1.235, "Apache + mod_wsgi", size=5.0, weight="normal", color=MUTED)
    for (bx, by, txt) in (
        (2.55, 0.90, "auth & sessions"),
        (3.44, 0.90, "item routes"),
        (2.55, 0.52, "match routes"),
        (3.44, 0.52, "claim workflow"),
    ):
        rbox(ax, bx, by, 0.82, 0.30, fc=BOX_LIGHT)
        fit_text(ax, bx + 0.41, by + 0.15, txt, 0.74, base=5.3, weight="normal")
    label(ax, 3.41, 0.31, "Jinja2 templates · validation · sessions", size=4.8,
          weight="normal", color=MUTED)

    # 4 shadow pipeline
    rbox(ax, 4.52, 0.34, 1.06, 0.88)
    label(ax, 5.05, 1.035, "Shadow Pipeline", size=6.1)
    label(ax, 5.05, 0.885, "(OpenCV)", size=5.3, weight="normal", color=MUTED)
    label(ax, 5.05, 0.705, "mask → silhouette", size=5.1, weight="normal", color=MUTED)
    label(ax, 5.05, 0.575, "64-bin descriptor", size=5.1, weight="normal", color=MUTED)
    label(ax, 5.05, 0.445, "cosine ranking", size=5.1, weight="normal", color=MUTED)

    # 5 database
    rbox(ax, 5.72, 0.34, 0.78, 0.88)
    label(ax, 6.11, 1.035, "SQLite", size=6.1)
    label(ax, 6.11, 0.885, "Database", size=6.1)
    label(ax, 6.11, 0.665, "students", size=5.1, weight="normal", color=MUTED)
    label(ax, 6.11, 0.545, "items", size=5.1, weight="normal", color=MUTED)
    label(ax, 6.11, 0.425, "claims · matches", size=5.1, weight="normal", color=MUTED)

    # flow arrows
    arrow(ax, (1.04, 0.78), (1.18, 0.78), mut=6)
    arrow(ax, (2.31, 0.78), (2.44, 0.78), mut=6)
    arrow(ax, (4.37, 0.78), (4.50, 0.78), mut=6)
    arrow(ax, (5.59, 0.78), (5.70, 0.78), mut=6)
    # descriptor hand-back
    arrow(ax, (4.50, 0.46), (4.39, 0.46), color="#5C86AD", ls=(0, (2.2, 1.6)), mut=5)
    label(ax, 4.445, 0.30, "descriptor", size=4.3, weight="normal", color=MUTED)

    out = FIG / "fig_3_1_architecture.png"
    fig.savefig(out, facecolor=DARK_BG, dpi=400, pad_inches=0)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Fig 3.2  entity relationship diagram
# ---------------------------------------------------------------------------
ROW_H = 0.150
HEAD_H = 0.210


def entity(ax, x_top, y_top, w, title, rows, *, font=5.4):
    """Draw one entity box; (x_top, y_top) is the TOP-LEFT corner."""
    h = HEAD_H + ROW_H * len(rows)
    ax.add_patch(mpatches.Rectangle((x_top, y_top - h), w, h, facecolor="white",
                                    edgecolor=ER_HEAD, linewidth=1.0, zorder=3))
    ax.add_patch(mpatches.Rectangle((x_top, y_top - HEAD_H), w, HEAD_H,
                                    facecolor=ER_HEAD, edgecolor=ER_HEAD,
                                    linewidth=1.0, zorder=4))
    ax.text(x_top + w / 2, y_top - HEAD_H / 2, title, ha="center", va="center",
            fontsize=6.2, color="white", fontweight="bold", family=SANS, zorder=5)
    for i, row in enumerate(rows):
        cy = y_top - HEAD_H - ROW_H * (i + 0.5)
        ax.text(x_top + 0.07, cy, row, ha="left", va="center", fontsize=font,
                color=ER_TEXT, family=MONO, zorder=5)
    return {"x": x_top, "top": y_top, "w": w, "h": h,
            "left": x_top, "right": x_top + w,
            "bottom": y_top - h, "top_edge": y_top,
            "mid": y_top - h / 2}


def er() -> Path:
    W, H = 6.55, 3.05
    fig = plt.figure(figsize=(W, H), dpi=400)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_axis_off()
    ax.set_facecolor("white")

    students = entity(ax, 0.06, 2.94, 1.86, "students",
                      ["id (PK)", "name", "email (UNIQUE)", "password",
                       "department", "created_at"])
    items = entity(ax, 2.46, 2.98, 1.80, "items",
                   ["id (PK)", "student_id (FK)", "title", "type (lost/found)",
                    "description", "shadow_iou", "descriptor", "created_at"])
    matches = entity(ax, 4.72, 2.82, 1.78, "matches",
                     ["id (PK)", "lost_item_id (FK)", "found_item_id (FK)",
                      "score", "created_at"])
    claims = entity(ax, 2.46, 1.38, 1.80, "claims",
                    ["id (PK)", "match_id (FK)", "sender_id (FK)",
                     "receiver_id (FK)", "status", "created_at"])

    # --- students 1 : N items -------------------------------------------
    gx = (students["right"] + items["left"]) / 2      # 2.12
    y1 = items["top_edge"] - HEAD_H - ROW_H * 1.5     # student_id row
    polyline(ax, [(students["right"], y1), (gx, y1), (gx, y1)])
    polyline(ax, [(students["right"], y1), (items["left"], y1)], z=2)
    arrow(ax, (items["left"] - 0.12, y1), (items["left"], y1), mut=5)
    label(ax, gx + 0.02, y1 + 0.115, "owns", size=5.0, color=ER_HEAD, weight="normal",
          style="italic")
    label(ax, gx + 0.02, y1 + 0.045, "(1 : N)", size=4.8, color=ER_HEAD, weight="normal",
          style="italic")

    # --- items 1 : N matches --------------------------------------------
    y2 = matches["top_edge"] - HEAD_H - ROW_H * 0.5
    mid_gap = (items["right"] + matches["left"]) / 2   # 4.47
    y2 = max(y2, items["top_edge"] - HEAD_H - ROW_H * 0.5)
    polyline(ax, [(items["right"], y2), (matches["left"], y2)])
    arrow(ax, (matches["left"] - 0.12, y2), (matches["left"], y2), mut=5)
    label(ax, mid_gap, y2 + 0.140, "has  (1 : N)", size=4.5, color=ER_HEAD,
          weight="normal", style="italic")

    # --- matches 1 : N claims (elbow down the right gap) -----------------
    mx = matches["left"] + 0.42
    y3 = claims["top_edge"] - HEAD_H - ROW_H * 1.5    # match_id row
    polyline(ax, [(mx, matches["bottom"]), (mx, y3), (claims["right"], y3)])
    arrow(ax, (claims["right"] + 0.13, y3), (claims["right"], y3), mut=5)
    label(ax, mx + 0.06, (matches["bottom"] + y3) / 2 + 0.02, "leads to", size=4.9,
          color=ER_HEAD, weight="normal", style="italic", ha="left")

    # --- items 1 : N claims (vertical drop) ------------------------------
    bx = items["left"] + 0.90
    polyline(ax, [(bx, items["bottom"]), (bx, claims["top_edge"])])
    arrow(ax, (bx, claims["top_edge"] + 0.14), (bx, claims["top_edge"]), mut=5)
    label(ax, bx - 0.06, (items["bottom"] + claims["top_edge"]) / 2 + 0.02,
          "claimed via (1 : N)", size=4.9, color=ER_HEAD, weight="normal",
          style="italic", ha="right")

    out = FIG / "fig_3_2_er.png"
    fig.savefig(out, facecolor="white", dpi=400, pad_inches=0)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Fig 3.3  workflow flowchart
# ---------------------------------------------------------------------------
FLOW_SPEC = [
    ("term", "Start"),
    ("process", "Open ShadowFind website"),
    ("decision", "Already registered?"),
    ("process", "Register with college email"),
    ("process", "Log in  (invalid login returns here)"),
    ("process", "Student Dashboard"),
    ("process", "Report a lost or found item"),
    ("process", "Upload a photo of the item"),
    ("decision", "Shadow visible in photo?"),
    ("process", "Extract the shadow silhouette"),
    ("process", "Store 64-bin descriptor in SQLite"),
    ("process", "Match against opposite-type items"),
    ("process", "Ranked candidate list for the owner"),
    ("process", "Owner sends a claim request"),
    ("process", "Finder confirms the handover"),
    ("process", "Status set to Returned"),
    ("term", "End"),
]


def flowchart() -> Path:
    """Vertical workflow chart: one main spine, both decisions branch right."""
    W = 3.90
    cx = 1.20
    bw, bh = 2.22, 0.315
    gap = 0.135
    dh = 0.50
    margin = 0.15
    branch_x = cx + 1.19

    heights = [{"term": bh, "process": bh, "decision": dh}[k] for k, _ in FLOW_SPEC]
    H = sum(heights) + gap * (len(heights) - 1) + 2 * margin

    fig = plt.figure(figsize=(W, H), dpi=400)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_axis_off()
    ax.set_facecolor(DARK_BG)

    # ---- assign a y to every node -------------------------------------
    y = H - margin
    layout = []
    for (kind, text), h in zip(FLOW_SPEC, heights):
        y -= h / 2
        layout.append((kind, text, h, y))
        y -= h / 2 + gap

    def draw_term(yy, text, w=0.98):
        rbox(ax, cx - w / 2, yy - bh / 2, w, bh, fc="#123A5C", radius=0.15)
        fit_text(ax, cx, yy, text, w - 0.16, base=6.2)

    def draw_process(yy, text):
        rbox(ax, cx - bw / 2, yy - bh / 2, bw, bh)
        fit_text(ax, cx, yy, text, bw - 0.22, base=6.2, weight="normal")

    def draw_decision(yy, text):
        pts = [(cx, yy + dh / 2), (cx + 1.02, yy), (cx, yy - dh / 2), (cx - 1.02, yy)]
        ax.add_patch(plt.Polygon(pts, closed=True, facecolor="#0A3A63",
                                 edgecolor=BOX_EDGE, linewidth=1.0, zorder=2))
        fit_text(ax, cx, yy, text, 1.46, base=6.0, weight="normal")

    def down(y0, y1, x=None):
        arrow(ax, (x if x is not None else cx, y0), (x if x is not None else cx, y1),
              color=LINK, lw=1.0, mut=6)

    for kind, text, h, yy in layout:
        {"term": draw_term, "process": draw_process, "decision": draw_decision}[kind](yy, text)

    for (k0, _, h0, y0), (k1, _, h1, y1) in zip(layout, layout[1:]):
        down(y0 - h0 / 2, y1 + h1 / 2)

    # ---- decision 1: Yes -> skip registration, rejoin at Log in ---------
    y_dec1 = layout[2][3]
    y_log = layout[4][3]
    polyline(ax, [(cx + 1.02, y_dec1), (branch_x, y_dec1), (branch_x, y_log),
                  (cx + bw / 2 + 0.12, y_log)])
    arrow(ax, (cx + bw / 2 + 0.14, y_log), (cx + bw / 2, y_log), mut=5)
    label(ax, branch_x + 0.07, y_dec1 + 0.055, "Yes", size=5.0, weight="normal",
          color=MUTED, ha="left")
    label(ax, branch_x + 0.07, (y_dec1 + y_log) / 2, "skip\nregistration", size=4.2,
          weight="normal", color=MUTED, ha="left")
    label(ax, cx + 0.07, (y_dec1 - dh / 2 + layout[3][3] + bh / 2) / 2, "No", size=5.0,
          weight="normal", color=MUTED, ha="left")

    # ---- decision 2: No shadow -> fallback straight to the descriptor ---
    y_dec2 = layout[8][3]
    y_desc = layout[10][3]
    polyline(ax, [(cx + 1.02, y_dec2), (branch_x, y_dec2), (branch_x, y_desc),
                  (cx + bw / 2 + 0.12, y_desc)])
    arrow(ax, (cx + bw / 2 + 0.14, y_desc), (cx + bw / 2, y_desc), mut=5)
    label(ax, branch_x + 0.07, y_dec2 + 0.055, "No", size=5.0, weight="normal",
          color=MUTED, ha="left")
    label(ax, branch_x + 0.07, (y_dec2 + y_desc) / 2, "colour + edge\nfallback", size=4.2,
          weight="normal", color=MUTED, ha="left")
    label(ax, cx + 0.07, (y_dec2 - dh / 2 + layout[9][3] + bh / 2) / 2, "Yes", size=5.0,
          weight="normal", color=MUTED, ha="left")

    out = FIG / "fig_3_3_flowchart.png"
    fig.savefig(out, facecolor=DARK_BG, dpi=400, pad_inches=0)
    plt.close(fig)
    return out


if __name__ == "__main__":
    for fn in (architecture, er, flowchart):
        print("wrote", fn())
