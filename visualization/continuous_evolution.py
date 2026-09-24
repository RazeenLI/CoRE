"""Plot sequential evolution under corrected and uncorrected states."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = ROOT / "outputs" / "continuous"
DATASETS = ["Spider", "TPCDS"]
DATASET_LABELS = {"Spider": "Spider", "TPCDS": "TPC-DS"}
MODES = ["oracle", "rollout"]
MODE_LABELS = {
    "oracle": "Corrected state",
    "rollout": "Uncorrected rollout",
}

# Academic AI/ML palette used across the paper figures.
MODE_COLORS = {
    "oracle": "#5C71BC",
    "rollout": "#AB4977",
}
MODE_MARKERS = {"oracle": "o", "rollout": "s"}
MODE_LINESTYLES = {"oracle": "-", "rollout": "--"}


def load_curves(dataset: str) -> dict[str, dict[str, list[float]]]:
    curves = {}
    for mode in MODES:
        path = RESULT_ROOT / dataset / f"{mode}_summary.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        steps = [payload["steps"][str(step)] for step in range(1, 11)]
        curves[mode] = {
            "schema_exact": [float(row["schema_exact"]) for row in steps],
            "proposal_f1": [float(row["proposal_micro_f1"]) for row in steps],
        }
    return curves


curves = {dataset: load_curves(dataset) for dataset in DATASETS}
steps = np.arange(1, 11)

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.size"] = 7
plt.rcParams["axes.titlesize"] = 7
plt.rcParams["axes.labelsize"] = 7
plt.rcParams["xtick.labelsize"] = 6.1
plt.rcParams["ytick.labelsize"] = 6.1
plt.rcParams["legend.fontsize"] = 5.8

fig, axes = plt.subplots(2, 2, figsize=(3.35, 1.85), sharex=True)

for column, dataset in enumerate(DATASETS):
    axes[0, column].set_title(DATASET_LABELS[dataset], pad=2)
    for row, metric in enumerate(("schema_exact", "proposal_f1")):
        ax = axes[row, column]
        for mode in MODES:
            ax.plot(
                steps,
                curves[dataset][mode][metric],
                color=MODE_COLORS[mode],
                marker=MODE_MARKERS[mode],
                linestyle=MODE_LINESTYLES[mode],
                linewidth=0.95,
                markersize=2.4,
                markeredgewidth=0.7,
            )
        ax.set_xlim(0.7, 10.3)
        ax.set_xticks([1, 4, 7, 10])
        ax.grid(axis="y", linewidth=0.3, alpha=0.4)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for spine in ax.spines.values():
            spine.set_linewidth(0.4)
        ax.tick_params(axis="both", length=2.0, width=0.4, pad=1)

for ax in axes[0]:
    ax.set_ylim(-0.03, 1.03)
    ax.set_yticks([0.0, 0.5, 1.0])

for ax in axes[1]:
    ax.set_ylim(0.4, 1.02)
    ax.set_yticks([0.4, 0.7, 1.0])
    ax.set_xlabel("Evolution step", labelpad=1.5)

axes[0, 0].set_ylabel("SchEx", labelpad=1.5)
axes[1, 0].set_ylabel("PropF1", labelpad=1.5)
axes[0, 1].tick_params(axis="y", labelleft=False)
axes[1, 1].tick_params(axis="y", labelleft=False)

legend_handles = [
    Line2D(
        [0],
        [0],
        color=MODE_COLORS[mode],
        marker=MODE_MARKERS[mode],
        linestyle=MODE_LINESTYLES[mode],
        linewidth=1.0,
        markersize=2.8,
        label=MODE_LABELS[mode],
    )
    for mode in MODES
]
fig.legend(
    handles=legend_handles,
    ncol=2,
    loc="upper center",
    bbox_to_anchor=(0.5, 0.99),
    frameon=False,
    columnspacing=0.8,
    handlelength=1.1,
    handletextpad=0.3,
    borderaxespad=0,
)

fig.subplots_adjust(
    left=0.105,
    right=0.985,
    top=0.84,
    bottom=0.14,
    wspace=0.18,
    hspace=0.36,
)

out_dir = Path(__file__).resolve().parent / "figures"
out_dir.mkdir(parents=True, exist_ok=True)
for suffix, kwargs in (("pdf", {}), ("png", {"dpi": 300})):
    plt.savefig(
        out_dir / f"continuous_evolution.{suffix}",
        format=suffix,
        bbox_inches="tight",
        pad_inches=0,
        **kwargs,
    )
plt.close(fig)

print(f"saved to: {out_dir / 'continuous_evolution.pdf'}")

