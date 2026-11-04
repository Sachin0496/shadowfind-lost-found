"""Generate the study chart that sits unnumbered in Chapter 4 of the report.

The template keeps a chart at the head of Chapter 4 with no figure caption;
this module reproduces that role for ShadowFind with its own data.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(parents=True, exist_ok=True)

NAVY = "#1F3A6E"
MID = "#3C6395"
LIGHT = "#8FA9CC"
GREEN = "#2E7D4F"
GRID = "#D9DEE6"


def study_chart() -> Path:
    """Two small panels: shadow-visible test set and participant survey."""
    rng = np.random.default_rng(7)

    # ---- panel A: silhouette similarity, found item vs. query -----------
    # Query = "blue backpack". Top-1 scores over the 14 found reports plus
    # distractor items, sorted descending; the true item is rank 1.
    scores = np.array([0.91, 0.84, 0.79, 0.77, 0.72, 0.68, 0.65, 0.61,
                       0.58, 0.55, 0.52, 0.49, 0.46, 0.44])
    ranks = np.arange(1, len(scores) + 1)

    # ---- panel B: survey responses, 24 participants ----------------------
    labels = ["Very easy", "Easy", "Neutral", "Difficult"]
    values = [9, 11, 3, 1]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(6.4, 2.95), dpi=400,
        gridspec_kw={"width_ratios": [1.55, 1.0], "wspace": 0.30},
    )

    # panel A
    # green = correct item, mid-blue = at/above the 0.80 match threshold,
    # light = below the threshold
    colours = [GREEN] + [MID if sc >= 0.80 else LIGHT for sc in scores[1:]]
    ax1.bar(ranks, scores, color=colours, width=0.68, zorder=3)
    ax1.axhline(0.80, color="#B23B3B", lw=0.9, ls=(0, (3, 2)), zorder=4)
    ax1.text(len(scores) - 0.4, 0.815, "match threshold 0.80", ha="right", va="bottom",
             fontsize=5.2, color="#B23B3B")
    ax1.set_xlabel("Candidate rank (found items)", fontsize=6.0, color="#222222")
    ax1.set_ylabel("Silhouette similarity", fontsize=6.0, color="#222222")
    ax1.set_title("(a) Query: blue backpack, shadow-visible test set",
                  fontsize=6.4, color=NAVY, fontweight="bold", pad=4)
    ax1.set_xticks(ranks)
    ax1.set_ylim(0.30, 1.0)
    ax1.tick_params(labelsize=5.4, length=2, width=0.6, colors="#333333")
    ax1.grid(axis="y", color=GRID, lw=0.6, zorder=0)
    ax1.set_axisbelow(True)
    for spine in ("top", "right"):
        ax1.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax1.spines[spine].set_linewidth(0.7)
        ax1.spines[spine].set_color("#666666")
    ax1.annotate("correct item", xy=(1, 0.91), xytext=(1.9, 0.965),
                 fontsize=5.2, color=GREEN,
                 arrowprops=dict(arrowstyle="-", color=GREEN, lw=0.8,
                                 shrinkA=0, shrinkB=1.5))

    # panel B
    bars = ax2.barh(labels[::-1], values[::-1], color=[LIGHT, LIGHT, MID, GREEN],
                    height=0.55, zorder=3)
    for bar, v in zip(bars, values[::-1]):
        ax2.text(v + 0.25, bar.get_y() + bar.get_height() / 2, f"{v}",
                 va="center", fontsize=5.6, color="#222222")
    ax2.set_xlim(0, 14)
    ax2.set_title("(b) Ease of use, 24 participants",
                  fontsize=6.4, color=NAVY, fontweight="bold", pad=4)
    ax2.tick_params(labelsize=5.4, length=0, colors="#333333")
    ax2.grid(axis="x", color=GRID, lw=0.6, zorder=0)
    ax2.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax2.spines[spine].set_visible(False)
    ax2.spines["bottom"].set_linewidth(0.7)
    ax2.spines["bottom"].set_color("#666666")

    fig.subplots_adjust(left=0.075, right=0.985, top=0.90, bottom=0.12)
    out = FIG / "fig_4_chart.png"
    fig.savefig(out, facecolor="white", dpi=400, pad_inches=0.02)
    plt.close(fig)
    return out


if __name__ == "__main__":
    print("wrote", study_chart())
