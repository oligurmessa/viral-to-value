"""
viz.py - shared matplotlib style for the project (light surface, fixed categorical order).
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

# fixed categorical order: blue, orange, aqua, yellow, magenta, green, violet, red
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
BLUES = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
         "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
VIRAL, NONVIRAL = SERIES[1], SERIES[0]        # orange = viral, blue = non-viral (fixed everywhere)
GOOD, WARN, BAD = "#0ca30c", "#fab219", "#d03b3b"


def setup():
    mpl.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#e6e5e1", "grid.linewidth": 0.6, "axes.axisbelow": True,
        "axes.prop_cycle": mpl.cycler(color=SERIES), "font.size": 10, "axes.titlesize": 11,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
        "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight", "lines.linewidth": 2,
        "patch.linewidth": 0,
    })


def blues_cmap():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("blues_proj", BLUES)


def money(x, _=None):
    return f"${x:,.0f}"


def pct(x, _=None):
    return f"{x:.0%}"
