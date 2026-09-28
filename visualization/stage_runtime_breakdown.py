"""Per-stage runtime breakdown (Profile/Select/Evolve/Validate)
for CoRE, stacked bars across all four datasets.

Data is loaded live from
save_new/<Dataset>/standard/{small,medium,large}/<case>/task_state.json
as the mean total time for each stage over all cases.
Run this file directly to regenerate the PDF.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# ============================================================
# Data: mean per-stage latency (seconds), pulled from real evaluation outputs
# ============================================================

REPO_ROOT = Path(__file__).resolve().parents[1]
SAVE_ROOT = REPO_ROOT / "save_new"
DATASETS = ["Chinook", "MONDIAL", "TPCDS", "Spider"]
DATASET_LABELS = {"Chinook": "Chinook", "MONDIAL": "MONDIAL", "TPCDS": "TPC-DS", "Spider": "Spider"}
METHOD = "standard"
STAGES = [
    ("profiling", "Profile"),
    ("matching", "Select"),
    ("evolving", "Evolve"),
    ("validating", "Validate"),
]


def load_stage_timing_table(datasets: list[str], method: str) -> dict[str, list[float]]:
    data = {}
    for dataset in datasets:
        totals = {key: [] for key, _ in STAGES}
        paths = sorted((SAVE_ROOT / dataset / method).glob("*/*/task_state.json"))
        if not paths:
            raise FileNotFoundError(f"No task states found for {dataset}/{method}")
        for path in paths:
            timing = json.loads(path.read_text(encoding="utf-8")).get("timing", {})
            steps = timing.get("steps", {})
            for key, _ in STAGES:
                totals[key].append(float(steps.get(key, {}).get("total_seconds", 0.0)))
        data[dataset] = [sum(totals[key]) / len(totals[key]) for key, _ in STAGES]
    return data

stages = [label for _, label in STAGES]
datasets = [DATASET_LABELS[ds] for ds in DATASETS]

timing = load_stage_timing_table(DATASETS, METHOD)
# stage_values[stage_index][dataset_index]
stage_values = np.array([timing[ds] for ds in DATASETS]).T
profile, select, evolve, validate = stage_values

total = profile + select + evolve + validate

original_bar_width = 0.66
bar_width = 1.56
bar_gap = 0.57
x = np.arange(len(datasets)) * (bar_width + bar_gap)

# Stage colors from the template's AI / ML profile.
# Later-order hues distinguish the stages from the usual blue/orange defaults.
STAGE_COLORS = {
    "Profile":  "#5C71BC",  # Indigo
    "Select":   "#289AA4",  # Cyan
    "Evolve":   "#C5598D",  # Pink
    "Validate": "#3F8D81",  # Teal
}

STAGE_EDGE_COLORS = {
    "Profile":  "#4C5FA4",
    "Select":   "#26767D",
    "Evolve":   "#AE4779",
    "Validate": "#376D64",
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

# Single-column width with slightly more vertical room.
fig, ax = plt.subplots(figsize=(3.35, 1.62))

# ============================================================
# Stacked bars
# ============================================================

MIN_LABEL_WIDTH = 8.0
SELECT_LABEL_WIDTH = 4.0

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
        min_width = SELECT_LABEL_WIDTH if stage == "Select" else MIN_LABEL_WIDTH
        if value < min_width:
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
        value + 0.7,
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

ax.set_xlim(0, 50)

ax.set_xticks([0, 10, 20, 30, 40, 50])

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
