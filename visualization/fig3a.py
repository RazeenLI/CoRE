"""Figure 1: per-operation (Insert/Extend/Create) decision F1,
one subfigure per dataset (TPC-DS, Spider, MONDIAL), one bar group per method.

Data is loaded live from evaluation/aggregate_result.py's summary logic
over the raw per-case CSVs in outputs/<Dataset>/<method>/{small,medium,large}.csv
-- see data_loader.py. Run this file directly to regenerate the PDF.
"""

import numpy as np
import matplotlib.pyplot as plt

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
    ("standard", "Standard"),
    ("oneshot", "OneShot"),
    ("magneto_llm", "Magneto-LLM"),
    ("magneto", "Magneto"),
]

METHOD_COLORS = {
    "Standard":    "#3A73AB",
    "OneShot":     "#D87C2C",
    "Magneto-LLM": "#3E935C",
    "Magneto":     "#7F68AC",
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

panel_labels = ["(a)", "(b)", "(c)"]
hatches = ["//", "\\\\", "xx", ".."]


# -----------------------------
# figure
# -----------------------------
fig_w = 3.35
fig_h = 1.45

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
for col, (ax, ds, plabel) in enumerate(zip(axes, DATASETS, panel_labels)):
    for i, method in enumerate(methods):
        vals = data[ds][method]

        offset = -group_width / 2 + i * bar_w + bar_w / 2

        ax.bar(
            x + offset,
            vals,
            width=bar_w,
            label=method if col == 0 else None,
            color=METHOD_COLORS[method],
            hatch=hatches[i % len(hatches)],
            edgecolor="black",
            linewidth=0.35,
        )

    ax.set_ylim(0, 1.0)
    ax.set_yticks(np.linspace(0, 1.0, 6))
    ax.grid(axis="y", linewidth=0.35, alpha=0.5)
    ax.set_axisbelow(True)

    ax.set_title(f"{plabel} {DATASET_LABELS[ds]}", pad=2)

    # Tight horizontal range inside each panel
    ax.set_xlim(
        -group_width / 2,
        len(operations) - 1 + group_width / 2,
    )

    ax.set_xticks(x)
    ax.set_xticklabels(operation_ticks)

    if col > 0:
        ax.tick_params(axis="y", labelleft=False)


# -----------------------------
# legend
# -----------------------------
handles, labels = axes[0].get_legend_handles_labels()

fig.legend(
    handles,
    labels,
    ncol=4,                    # one row
    loc="upper center",
    bbox_to_anchor=(0.5, 0.995),
    frameon=False,
    columnspacing=0.7,
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
    bottom=0.15,
    wspace=0.18,  # larger gap between subfigures
)


# -----------------------------
# save
# -----------------------------
out_path = "visualization/figures/fig1_operation_f1.pdf"

plt.savefig(
    out_path,
    format="pdf",
    pad_inches=0,
)

plt.close(fig)

print(f"saved to: {out_path}")