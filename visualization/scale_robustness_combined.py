"""Natural-context and controlled relation-count scale analysis."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.transforms import Bbox

from data_loader import (
    OUTPUTS_DIR,
    convert_result_rows,
    load_result_rows,
    load_scale_robustness_table,
    summary_for_size,
)


DATASETS = ["Chinook", "Spider"]
NATURAL_SIZES = ["Small", "Medium", "Large"]
CONTROLLED_LEVELS = ["original", "25", "50", "100"]
CONTROLLED_TICKS = ["Orig.", "25", "50", "100"]

METHODS = [
    ("standard", "CoRE"),
    ("oneshot", "OneShot"),
    ("magneto_llm", "Magneto-LLM"),
    ("coma_llm", "COMA-LLM"),
    ("starmie_llm", "Starmie-LLM"),
]
METHOD_LABELS = [label for _, label in METHODS]

# Academic AI/ML palette used across the paper figures.
METHOD_COLORS = {
    "CoRE": "#5C71BC",
    "OneShot": "#AB4977",
    "Magneto-LLM": "#3F8D81",
    "COMA-LLM": "#C79C23",
    "Starmie-LLM": "#7F68AC",
}
METHOD_MARKERS = {
    "CoRE": "o",
    "OneShot": "s",
    "Magneto-LLM": "^",
    "COMA-LLM": "D",
    "Starmie-LLM": "v",
}

DMF1_COLOR = "#5C71BC"
PROPF1_COLOR = "#3F8D81"
LATENCY_COLOR = "#C5598D"


def controlled_data(dataset: str) -> dict[str, list[float]]:
    result = {"DMF1": [], "PropF1": [], "Latency": []}
    for level in CONTROLLED_LEVELS:
        split = f"scale_{level}"
        summary = summary_for_size(dataset, "standard", split)
        result["DMF1"].append(summary["decision_macro_f1"])
        result["PropF1"].append(summary["proposal_fact_micro_f1"])

        path = OUTPUTS_DIR / dataset / "standard" / f"{split}.csv"
        rows = convert_result_rows(load_result_rows(path))
        latencies = [
            float(row["timing_end_to_end_seconds"])
            for row in rows
            if row.get("evaluation_status") == "evaluated"
            and row.get("timing_end_to_end_seconds") is not None
        ]
        result["Latency"].append(sum(latencies) / len(latencies))
    return result


natural = load_scale_robustness_table(DATASETS, METHODS)
controlled = {dataset: controlled_data(dataset) for dataset in DATASETS}

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.size"] = 7
plt.rcParams["axes.titlesize"] = 7
plt.rcParams["axes.labelsize"] = 7
plt.rcParams["xtick.labelsize"] = 6.1
plt.rcParams["ytick.labelsize"] = 6.1
plt.rcParams["legend.fontsize"] = 5.8

fig = plt.figure(figsize=(3.35, 3.0))
grid = fig.add_gridspec(3, 2, height_ratios=(1.0, 1.0, 1.12))

natural_axes = np.array([
    [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])],
    [fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])],
])
controlled_axes = [fig.add_subplot(grid[2, 0]), fig.add_subplot(grid[2, 1])]

natural_panels = [
    ("Chinook", "DMF1"),
    ("Spider", "DMF1"),
    ("Chinook", "PropF1"),
    ("Spider", "PropF1"),
]
natural_x = np.arange(len(NATURAL_SIZES))

for ax, (dataset, metric) in zip(natural_axes.flat, natural_panels):
    for method in METHOD_LABELS:
        ax.plot(
            natural_x,
            natural[(dataset, metric)][method],
            color=METHOD_COLORS[method],
            marker=METHOD_MARKERS[method],
            linewidth=0.95,
            markersize=2.4,
            markeredgewidth=0.7,
        )
    if metric == "DMF1":
        ax.set_title(dataset, pad=1.5)
    ax.set_xticks(natural_x)
    ax.set_xticklabels(NATURAL_SIZES)
    if metric == "DMF1":
        ax.set_ylim(0.5, 1.0)
        ax.set_yticks([0.5, 0.75, 1.0])
    else:
        ax.set_ylim(0.5, 0.72)
        ax.set_yticks([0.5, 0.6, 0.7])
    ax.grid(axis="y", linewidth=0.3, alpha=0.4)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for spine in ax.spines.values():
        spine.set_linewidth(0.4)
    ax.tick_params(axis="both", length=2.0, width=0.4, pad=1)

natural_axes[0, 0].set_ylabel("DMF1", labelpad=1.5)
natural_axes[1, 0].set_ylabel("PropF1", labelpad=1.5)

controlled_x = np.arange(len(CONTROLLED_LEVELS))
latency_axes = []
for index, (ax, dataset) in enumerate(zip(controlled_axes, DATASETS)):
    latency_ax = ax.twinx()
    latency_axes.append(latency_ax)
    ax.plot(
        controlled_x,
        controlled[dataset]["DMF1"],
        color=DMF1_COLOR,
        marker="o",
        linewidth=1.15,
        markersize=3.0,
        zorder=3,
    )
    ax.plot(
        controlled_x,
        controlled[dataset]["PropF1"],
        color=PROPF1_COLOR,
        marker="s",
        linestyle="--",
        linewidth=1.05,
        markersize=2.8,
        zorder=3,
    )
    latency_ax.bar(
        controlled_x,
        controlled[dataset]["Latency"],
        width=0.55,
        color=LATENCY_COLOR,
        edgecolor=LATENCY_COLOR,
        linewidth=0.4,
        alpha=0.35,
        zorder=1,
    )

    ax.set_title(dataset, pad=1.5)
    ax.set_xticks(controlled_x)
    ax.set_xticklabels(CONTROLLED_TICKS)
    ax.set_xlabel("Relations", labelpad=1)
    ax.set_ylim(0.5, 1.0)
    ax.set_yticks([0.5, 0.75, 1.0])
    latency_ax.set_ylim(0, 90)
    latency_ax.set_yticks([0, 45, 90])
    if index == 0:
        ax.set_ylabel("DMF1 / PropF1", labelpad=1.5)
        latency_ax.tick_params(axis="y", labelright=False)
    else:
        ax.tick_params(axis="y", labelleft=False)
        latency_ax.set_ylabel("Seconds", labelpad=1.5)

    ax.set_zorder(2)
    ax.patch.set_alpha(0)
    ax.grid(axis="y", linewidth=0.3, alpha=0.4)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    latency_ax.spines["top"].set_visible(False)
    latency_ax.spines["left"].set_visible(False)
    latency_ax.spines["bottom"].set_visible(False)
    for current in (ax, latency_ax):
        for spine in current.spines.values():
            spine.set_linewidth(0.4)
        current.tick_params(axis="both", length=2.0, width=0.4, pad=1)

method_handles = [
    Line2D(
        [0], [0],
        color=METHOD_COLORS[method],
        marker=METHOD_MARKERS[method],
        linewidth=1.0,
        markersize=2.8,
    )
    for method in METHOD_LABELS
]
fig.legend(
    method_handles,
    METHOD_LABELS,
    ncol=5,
    loc="upper center",
    bbox_to_anchor=(0.5, 1.0),
    frameon=False,
    columnspacing=0.45,
    handlelength=0.9,
    handletextpad=0.25,
    borderaxespad=0,
)

metric_handles = [
    Line2D([0], [0], color=DMF1_COLOR, marker="o", linewidth=1.15, markersize=3, label="DMF1"),
    Line2D([0], [0], color=PROPF1_COLOR, marker="s", linestyle="--", linewidth=1.05, markersize=2.8, label="PropF1"),
    Patch(facecolor=LATENCY_COLOR, edgecolor=LATENCY_COLOR, linewidth=0.4, alpha=0.35, label="Latency"),
]
fig.legend(
    handles=metric_handles,
    ncol=3,
    loc="lower center",
    bbox_to_anchor=(0.5, 0.002),
    frameon=False,
    columnspacing=0.8,
    handlelength=1.1,
    handletextpad=0.3,
    borderaxespad=0,
)

fig.subplots_adjust(
    left=0.105,
    right=0.965,
    top=0.91,
    bottom=0.13,
    wspace=0.18,
    hspace=0.48,
)

# Keep the overall height fixed while tightening rows 1--2 and opening rows 2--3.
for ax in natural_axes[1]:
    position = ax.get_position()
    ax.set_position([
        position.x0, position.y0 + 0.006, position.width, position.height
    ])
fig.align_ylabels([natural_axes[0, 0], natural_axes[1, 0], controlled_axes[0]])

out_dir = Path(__file__).resolve().parent / "figures"
out_dir.mkdir(parents=True, exist_ok=True)
fig.canvas.draw()
tight_bbox = fig.get_tightbbox(fig.canvas.get_renderer())
left_padded_bbox = Bbox.from_extents(
    tight_bbox.x0 - 0.015, tight_bbox.y0, tight_bbox.x1, tight_bbox.y1
)

for suffix, kwargs in (("pdf", {}), ("png", {"dpi": 300})):
    plt.savefig(
        out_dir / f"scale_robustness.{suffix}",
        format=suffix,
        bbox_inches=left_padded_bbox,
        pad_inches=0,
        **kwargs,
    )
plt.close(fig)

print(f"saved to: {out_dir / 'scale_robustness.pdf'}")
