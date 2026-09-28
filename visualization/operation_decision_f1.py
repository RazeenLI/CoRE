"""Per-operation (Insert/Extend/Create) decision F1,
one subfigure per dataset (TPC-DS, Spider, MONDIAL), one bar group per method.

Data is loaded live from evaluation/aggregate_result.py's summary logic
over the raw per-case CSVs in outputs/<Dataset>/<method>/{small,medium,large}.csv
-- see data_loader.py. Run this file directly to regenerate the PDF.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from data_loader import OPERATIONS, load_operation_f1_table


# -----------------------------
# data
# -----------------------------
DATASETS = ["TPCDS", "Spider", "MONDIAL"]

DATASET_LABELS = {
    "TPCDS": "TPC-DS",
    "Spider": "Spider",
    "MONDIAL": "MONDIAL",
}

METHODS = [
    ("standard", "CoRE"),
    ("oneshot", "OneShot"),
    ("magneto_llm", "Magneto-LLM"),
    ("coma_llm", "COMA-LLM"),
    ("starmie_llm", "Starmie-LLM"),
]

METHOD_COLORS = {
    "CoRE":        "#5C71BC",
    "OneShot":     "#AB4977",
    "Magneto-LLM": "#3F8D81",
    "COMA-LLM":    "#C79C23",
    "Starmie-LLM": "#7F68AC",
}

METHOD_EDGE_COLORS = {
    "CoRE":        "#4C5FA4",
    "OneShot":     "#8A4264",
    "Magneto-LLM": "#376D64",
    "COMA-LLM":    "#9C7C26",
    "Starmie-LLM": "#6C5794",
}

# Full operation names for loading data
operations = [label for _, label in OPERATIONS]

# Abbreviations only for display
OPERATION_TICKS = {
    "Insert": "I",
    "Extend": "E",
    "Create": "C",
}
operation_ticks = [OPERATION_TICKS.get(op, op[0]) for op in operations]

methods = [label for _, label in METHODS]

data = load_operation_f1_table(DATASETS, METHODS)


# -----------------------------
# style
# -----------------------------
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["font.family"] = "serif"

plt.rcParams["font.size"] = 7
plt.rcParams["axes.titlesize"] = 8
plt.rcParams["axes.labelsize"] = 8
plt.rcParams["xtick.labelsize"] = 7
plt.rcParams["ytick.labelsize"] = 7
plt.rcParams["legend.fontsize"] = 6.5

# -----------------------------
# figure
# -----------------------------
fig_w = 3.35
fig_h = 1.55

fig, axes = plt.subplots(
    nrows=1,
    ncols=3,
    figsize=(fig_w, fig_h),
    sharey=True,
)

x = np.arange(len(operations))
n_methods = len(methods)

group_width = 0.88
bar_w = group_width / n_methods


# -----------------------------
# panels
# -----------------------------
for col, (ax, ds) in enumerate(zip(axes, DATASETS)):
    for i, method in enumerate(methods):
        vals = data[ds][method]

        offset = -group_width / 2 + i * bar_w + bar_w / 2

        ax.bar(
            x + offset,
            vals,
            width=bar_w,
            label=method if col == 0 else None,
            color=METHOD_COLORS[method],
            edgecolor=METHOD_EDGE_COLORS[method],
            linewidth=0.4,
        )

    ax.set_ylim(0, 1.0)
    ax.set_yticks(np.linspace(0, 1.0, 6))
    ax.grid(axis="y", linewidth=0.35, alpha=0.5)
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_linewidth(0.4)

    ax.set_title(DATASET_LABELS[ds], pad=2)

    # Tight horizontal range inside each panel
    ax.set_xlim(
        -group_width / 2,
        len(operations) - 1 + group_width / 2,
    )

    ax.set_xticks(x)
    ax.set_xticklabels(operation_ticks)
    ax.tick_params(axis="both", width=0.4)

    if col > 0:
        ax.tick_params(axis="y", labelleft=False)


# -----------------------------
# legend
# -----------------------------
handles, labels = axes[0].get_legend_handles_labels()

fig.legend(
    handles,
    labels,
    ncol=5,                    # one row
    loc="upper center",
    bbox_to_anchor=(0.5, 0.995),
    frameon=False,
    fontsize=6.0,
    columnspacing=0.55,
    handletextpad=0.35,
    handlelength=1.1,
    borderaxespad=0.0,
)


# -----------------------------
# layout
# -----------------------------
fig.subplots_adjust(
    left=0.088,   # slightly tighter left margin
    right=0.992,  # tiny right white margin so border is not cut
    top=0.77,     # room for one-line legend
    bottom=0.18,
    wspace=0.18,  # larger gap between subfigures
)


# -----------------------------
# save
# -----------------------------
out_path = Path(__file__).resolve().parent / "figures" / "operation_f1.pdf"
out_path.parent.mkdir(parents=True, exist_ok=True)

plt.savefig(
    out_path,
    format="pdf",
    pad_inches=0,
)

plt.close(fig)

print(f"saved to: {out_path}")
