"""Two charts, drawn with matplotlib. One axis each, honest baselines, direct labels."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BLUE, ORANGE, RED = "#2a78d6", "#eb6834", "#e34948"
SURFACE, INK, SECOND, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
    ax.tick_params(colors=SECOND, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def pareto_chart(frontier, baseline_cost, baseline_ontime, path):
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=150, facecolor=SURFACE)
    _style(ax)
    ax.plot(frontier["ontime_target"] * 100, frontier["cost"] / 1000, color=BLUE, linewidth=2.2)
    ax.scatter([baseline_ontime * 100], [baseline_cost / 1000], color=ORANGE, s=70, zorder=3)
    ax.annotate("Current plan", (baseline_ontime * 100, baseline_cost / 1000), xytext=(-12, 14),
                textcoords="offset points", ha="right", color=ORANGE, fontsize=10, fontweight="bold")
    ax.annotate("Cheapest possible plan\nfor each service level", (frontier["ontime_target"].iloc[len(frontier) // 3] * 100,
                frontier["cost"].iloc[len(frontier) // 3] / 1000), xytext=(-4, 26), textcoords="offset points",
                color=BLUE, fontsize=10, fontweight="bold")
    ax.set_xlabel("Overall on-time delivery (%)", color=SECOND, fontsize=10)
    ax.set_ylabel("Monthly freight cost (R$ thousand)", color=SECOND, fontsize=10)
    ax.set_title("Same service for less money, or better service for the same money", loc="left",
                 color=INK, fontsize=12, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def shares_chart(before, after, path):
    carriers = list(before["carrier"])
    x = np.arange(len(carriers))
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=150, facecolor=SURFACE)
    _style(ax)
    w = 0.38
    b1 = ax.bar(x - w / 2, before["share"] * 100, w, color=ORANGE, label="Current plan")
    b2 = ax.bar(x + w / 2, after["share"] * 100, w, color=BLUE, label="Optimized plan")
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.6, f"{r.get_height():.0f}%", ha="center",
                    color=SECOND, fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(carriers)
    ax.set_ylim(0, max(before["share"].max(), after["share"].max()) * 100 * 1.18)
    ax.set_ylabel("Share of monthly kg (%)", color=SECOND, fontsize=10)
    ax.set_title("Who gets the volume", loc="left", color=INK, fontsize=12, fontweight="bold", pad=12)
    ax.legend(frameon=False, loc="upper right", labelcolor=SECOND)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
