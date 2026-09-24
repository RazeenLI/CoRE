"""Robustness across benchmark size (Small/Medium/Large) for Chinook and
Spider. Rows are datasets; columns show DMF1 (decision macro-F1) and
PropF1 (proposal fact micro-F1) separately, colored by method.

Data is loaded live from outputs/<Dataset>/<method>/{small,medium,large}.csv
via data_loader.load_scale_robustness_table -- decision_macro_f1 and
proposal_fact_micro_f1 from evaluation/aggregate_result.py's own summary
logic, kept per-size (not concatenated). Run this file directly to
regenerate the PDF.
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from pathlib import Path

from data_loader import load_scale_robustness_table

# ============================================================
# Data
# ============================================================

sizes = ["Small", "Medium", "Large"]
x = np.arange(len(sizes))

DATASETS = ["Chinook", "Spider"]

METHODS = [
    ("standard", "CoRE"),
    ("oneshot", "OneShot"),
    ("magneto_llm", "Magneto-LLM"),
    ("coma_llm", "COMA-LLM"),
    ("starmie_llm", "Starmie-LLM"),
]
methods = [label for _, label in METHODS]

data = load_scale_robustness_table(DATASETS, METHODS)

# Keep method colors consistent with the operation-F1 figure.
METHOD_COLORS = {
    "CoRE":        "#3B73AB",
    "OneShot":     "#D87C2C",
    "Magneto-LLM": "#3F925C",
    "COMA-LLM":    "#7F68AC",
    "Starmie-LLM": "#C14E57",
}

markers = {
    "CoRE": "o",
    "OneShot": "s",
    "Magneto-LLM": "^",
    "COMA-LLM": "D",
    "Starmie-LLM": "v",
}

Y_SCALES = {
    "DMF1": ((0.5, 1.0), [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]),
    "PropF1": ((0.5, 0.7), [0.5, 0.6, 0.7]),
}

# ============================================================
# VLDB-style plotting settings
# ============================================================

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["font.family"] = "serif"

plt.rcParams["font.size"] = 7
plt.rcParams["axes.titlesize"] = 7
plt.rcParams["axes.labelsize"] = 7
plt.rcParams["xtick.labelsize"] = 6.2
plt.rcParams["ytick.labelsize"] = 6.2
plt.rcParams["legend.fontsize"] = 6.2

# Single-column width, flatter than a square 2x2 grid
fig, axes = plt.subplots(
    2,
    2,
    figsize=(3.35, 2.0),
    sharex=True,
    sharey="col"
)

panels = [
    ("Chinook", "DMF1", "Chinook: DMF1"),
    ("Chinook", "PropF1", "Chinook: PropF1"),
    ("Spider", "DMF1", "Spider: DMF1"),
    ("Spider", "PropF1", "Spider: PropF1"),
]

# ============================================================
# Plot
# ============================================================

for ax, (dataset, metric, title) in zip(axes.flat, panels):

    for method in methods:
        ax.plot(
            x,
            data[(dataset, metric)][method],
            marker=markers[method],
            color=METHOD_COLORS[method],
            linewidth=1.0,
            markersize=2.6,
            markeredgewidth=0.8,
        )

    ax.set_title(title, pad=2)

    ax.set_xticks(x)
    ax.set_xticklabels(sizes)

    y_limits, y_ticks = Y_SCALES[metric]
    ax.set_ylim(*y_limits)
    ax.set_yticks(y_ticks)
    ax.tick_params(axis="y", labelleft=True)

    ax.grid(
        axis="y",
        linewidth=0.3,
        alpha=0.4
    )
    ax.set_axisbelow(True)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for spine in ax.spines.values():
        spine.set_linewidth(0.4)

    ax.tick_params(
        axis="both",
        length=2.2,
        width=0.4,
        pad=0
    )
    ax.tick_params(axis="x", pad=1.5)

axes[0, 0].set_ylabel("Score", labelpad=2)
axes[1, 0].set_ylabel("Score", labelpad=2)

# ============================================================
# Shared method legend
# ============================================================

method_handles = [
    Line2D([0], [0], color=METHOD_COLORS[m], marker=markers[m], markersize=3.0, linewidth=1.0)
    for m in methods
]
fig.legend(
    method_handles,
    methods,
    ncol=5,
    loc="upper center",
    bbox_to_anchor=(0.5, 1.01),
    frameon=False,
    fontsize=5.8,
    columnspacing=0.5,
    handlelength=1.0,
    handletextpad=0.3,
    borderaxespad=0
)

# ============================================================
# Tight spacing
# ============================================================

fig.subplots_adjust(
    left=0.119,
    right=0.995,
    bottom=0.1405,
    top=0.87,
    wspace=0.15,
    hspace=0.30
)

# ============================================================
# Save
# ============================================================

out_dir = Path(__file__).resolve().parent / "figures"
out_dir.mkdir(parents=True, exist_ok=True)

plt.savefig(
    out_dir / "scale_robustness.pdf",
    format="pdf",
    bbox_inches="tight",
    pad_inches=0
)

plt.savefig(
    out_dir / "scale_robustness.png",
    dpi=300,
    bbox_inches="tight",
    pad_inches=0
)

plt.close(fig)

print(f"saved to: {out_dir / 'scale_robustness.pdf'}")
