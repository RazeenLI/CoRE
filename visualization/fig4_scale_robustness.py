"""Figure 4: robustness across benchmark size (Small/Medium/Large), one
panel per dataset (Chinook, MONDIAL, TPC-DS, Spider). Each panel overlays
both metrics -- DMF1 (decision macro-F1, solid/filled) and PropF1
(proposal_fact_micro_f1, dashed/hollow) -- since they share the same [0.2,
1.0] score scale, colored by method.

Data is loaded live from outputs/<Dataset>/<method>/{small,medium,large}.csv
via data_loader.load_scale_robustness_table -- decision_macro_f1 and
proposal_fact_micro_f1 from evaluation/aggregate_result.py's own summary
logic, kept per-size (not concatenated). Run this file directly to
regenerate the PDF.
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from data_loader import load_scale_robustness_table

# ============================================================
# Data
# ============================================================

sizes = ["Small", "Medium", "Large"]
x = np.arange(len(sizes))

DATASETS = ["Chinook", "MONDIAL", "TPCDS", "Spider"]
DATASET_LABELS = {"Chinook": "Chinook", "MONDIAL": "MONDIAL", "TPCDS": "TPC-DS", "Spider": "Spider"}

METHODS = [
    ("standard", "Standard"),
    ("oneshot", "OneShot"),
    ("magneto_llm", "Magneto-LLM"),
    ("magneto", "Magneto"),
]
methods = [label for _, label in METHODS]

data = load_scale_robustness_table(DATASETS, METHODS)
data = {
    (DATASET_LABELS[ds], metric): values
    for (ds, metric), values in data.items()
}

# Method colors, from the academic color palette's "AI/ML" profile -- same
# identity used across the other figures (Standard=Blue, OneShot=Orange,
# Magneto-LLM=Green, Magneto=Purple).
METHOD_COLORS = {
    "Standard":    "#3A73AB",
    "OneShot":     "#D87C2C",
    "Magneto-LLM": "#3E935C",
    "Magneto":     "#7F68AC",
}

markers = {
    "Standard": "o",
    "OneShot": "s",
    "Magneto-LLM": "^",
    "Magneto": "D",
}

METRIC_STYLE = {
    "DMF1":   dict(linestyle="-",  fillstyle="full"),
    "PropF1": dict(linestyle="--", fillstyle="none"),
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
    figsize=(3.35, 2.35),
    sharex=True,
    sharey=True
)

panels = [
    ("Chinook", "(a) Chinook"),
    ("MONDIAL", "(b) MONDIAL"),
    ("TPC-DS", "(c) TPC-DS"),
    ("Spider", "(d) Spider"),
]

# ============================================================
# Plot
# ============================================================

for ax, (dataset, title) in zip(axes.flat, panels):

    for method in methods:
        for metric in ("DMF1", "PropF1"):
            style = METRIC_STYLE[metric]
            ax.plot(
                x,
                data[(dataset, metric)][method],
                marker=markers[method],
                color=METHOD_COLORS[method],
                linewidth=1.0,
                markersize=2.6,
                markeredgewidth=0.8,
                **style,
            )

    ax.set_title(title, pad=2)

    ax.set_xticks(x)
    ax.set_xticklabels(sizes)

    ax.set_ylim(0.2, 1.0)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])

    ax.grid(
        axis="y",
        linewidth=0.3,
        alpha=0.4
    )
    ax.set_axisbelow(True)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.tick_params(
        axis="both",
        length=2.2,
        pad=1.5
    )

# Only left-side y labels
axes[0, 0].set_ylabel("Score", labelpad=2)
axes[1, 0].set_ylabel("Score", labelpad=2)

# ============================================================
# Shared legends: method (color) and metric (line style) are independent,
# so they get two separate small legends rather than 8 combined entries.
# ============================================================

method_handles = [
    Line2D([0], [0], color=METHOD_COLORS[m], marker=markers[m], markersize=3.0, linewidth=1.0)
    for m in methods
]
fig.legend(
    method_handles,
    methods,
    ncol=4,
    loc="upper center",
    bbox_to_anchor=(0.5, 1.03),
    frameon=False,
    columnspacing=0.8,
    handlelength=1.4,
    handletextpad=0.3,
    borderaxespad=0
)

metric_handles = [
    Line2D([0], [0], color="black", linewidth=1.0, **METRIC_STYLE["DMF1"], marker="o", markersize=2.6, markeredgewidth=0.8),
    Line2D([0], [0], color="black", linewidth=1.0, **METRIC_STYLE["PropF1"], marker="o", markersize=2.6, markeredgewidth=0.8),
]
fig.legend(
    metric_handles,
    ["DMF1", "PropF1"],
    ncol=2,
    loc="upper center",
    bbox_to_anchor=(0.5, 0.93),
    frameon=False,
    columnspacing=0.8,
    handlelength=1.8,
    handletextpad=0.3,
    borderaxespad=0
)

# ============================================================
# Tight spacing
# ============================================================

fig.subplots_adjust(
    left=0.13,
    right=1.0,
    bottom=0.115,
    top=0.8,
    wspace=0.1,
    hspace=0.4
)

# ============================================================
# Save
# ============================================================

plt.savefig(
    "figures/fig4_scale_robustness.pdf",
    format="pdf",
    bbox_inches="tight",
    pad_inches=0
)

plt.savefig(
    "figures/fig4_scale_robustness.png",
    dpi=300,
    bbox_inches="tight",
    pad_inches=0
)

plt.close(fig)

print("saved to: figures/fig4_scale_robustness.pdf")
