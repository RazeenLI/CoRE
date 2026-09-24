"""Per-stage runtime breakdown (Profile/Select/Evolve/Validate)
for CoRE, stacked bars across all four datasets.

Data is loaded live from outputs/<Dataset>/standard/{small,medium,large}.csv
via data_loader.load_stage_timing_table -- mean of each stage's
timing_steps_*_total_seconds column over all cases. Verified to reproduce
the reference numbers exactly (e.g. TPC-DS -> [59.1, 6.2, 78.1, 8.0]).
Run this file directly to regenerate the PDF.
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

from data_loader import STAGE_TIMING_COLUMNS, load_stage_timing_table

# ============================================================
# Data: mean per-stage latency (seconds), pulled from real evaluation outputs
# ============================================================

DATASETS = ["Chinook", "MONDIAL", "TPCDS", "Spider"]
DATASET_LABELS = {"Chinook": "Chinook", "MONDIAL": "MONDIAL", "TPCDS": "TPC-DS", "Spider": "Spider"}
METHOD = "standard"

stages = [label for _, label in STAGE_TIMING_COLUMNS]
datasets = [DATASET_LABELS[ds] for ds in DATASETS]

timing = load_stage_timing_table(DATASETS, METHOD)
# stage_values[stage_index][dataset_index]
stage_values = np.array([timing[ds] for ds in DATASETS]).T
profile, select, evolve, validate = stage_values

total = profile + select + evolve + validate

x = np.arange(len(datasets))

# Stage colors, from the academic color palette's "AI/ML" profile -- same
# Blue/Orange/Green/Purple categorical hues used for the first four methods
# in the operation-F1 figure, reused here for the four pipeline stages.
STAGE_COLORS = {
    "Profile":  "#3B73AB",  # Blue
    "Select":   "#D87C2C",  # Orange
    "Evolve":   "#3F925C",  # Green
    "Validate": "#7F68AC",  # Purple
}

STAGE_EDGE_COLORS = {
    "Profile":  "#365E87",
    "Select":   "#AF692C",
    "Evolve":   "#36724B",
    "Validate": "#6C5794",
}


def _contrast_text_color(hex_color: str) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "white" if luminance < 0.6 else "black"


STAGE_TEXT_COLORS = {stage: _contrast_text_color(color) for stage, color in STAGE_COLORS.items()}

# ============================================================
# Publication settings
# ============================================================

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["font.family"] = "serif"

plt.rcParams["font.size"] = 7
plt.rcParams["axes.labelsize"] = 7
plt.rcParams["xtick.labelsize"] = 6.5
plt.rcParams["ytick.labelsize"] = 6.5
plt.rcParams["legend.fontsize"] = 6.5

# Single-column width with a compact height
fig, ax = plt.subplots(figsize=(3.35, 0.9))

# ============================================================
# Stacked bars
# ============================================================

bar_width = 0.66

MIN_LABEL_WIDTH = 8.0  # skip in-segment labels too narrow to hold text (e.g. Select)

left = np.zeros(len(datasets))
for stage_values, stage in zip((profile, select, evolve, validate), stages):
    ax.barh(
        x,
        stage_values,
        height=bar_width,
        left=left,
        label=stage,
        color=STAGE_COLORS[stage],
        edgecolor=STAGE_EDGE_COLORS[stage],
        linewidth=0.4
    )

    # In-segment value labels
    for i, value in enumerate(stage_values):
        if value < MIN_LABEL_WIDTH:
            continue
        ax.text(
            left[i] + value / 2,
            x[i],
            f"{value:.1f}",
            ha="center",
            va="center",
            fontsize=6,
            color=STAGE_TEXT_COLORS[stage],
        )

    left += stage_values

# ============================================================
# Total latency labels
# ============================================================

for i, value in enumerate(total):
    ax.text(
        value + 3.0,
        x[i],
        f"{value:.1f}",
        ha="left",
        va="center",
        fontsize=6.3
    )

# ============================================================
# Axes
# ============================================================

ax.set_yticks(x)
ax.set_yticklabels(datasets)
ax.invert_yaxis()  # first dataset at the top

ax.set_xlim(0, 170)

ax.set_xticks([0, 50, 100, 150])

ax.grid(
    axis="x",
    linewidth=0.3,
    alpha=0.4
)
ax.set_axisbelow(True)

# Cleaner publication appearance
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

for spine in ax.spines.values():
    spine.set_linewidth(0.4)

ax.tick_params(
    axis="both",
    length=2.5,
    width=0.4,
    pad=2
)

# ============================================================
# Legend
# ============================================================

ax.legend(
    ncol=4,
    loc="lower center",
    bbox_to_anchor=(0.5, 1.01),
    frameon=False,
    columnspacing=0.8,
    handlelength=1.0,
    handletextpad=0.35,
    borderaxespad=0
)

# ============================================================
# Tight layout / no external white padding
# ============================================================

fig.subplots_adjust(
    left=0.115,
    right=1.0,
    bottom=0.25,
    top=0.72
)

out_path = Path(__file__).resolve().parent / "figures" / "stage_runtime_breakdown.pdf"
out_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(
    out_path,
    format="pdf",
    bbox_inches="tight",
    pad_inches=0
)

plt.close(fig)

print(f"saved to: {out_path}")
