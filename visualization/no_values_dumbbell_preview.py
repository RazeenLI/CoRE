"""Single-column preview for the NoValues comparison."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


DATASETS = ["Chinook", "MONDIAL", "TPC-DS", "Spider"]
CORE = {
    "DMF1": [0.895, 0.904, 0.807, 0.871],
    "PropF1": [0.642, 0.671, 0.520, 0.663],
}
NO_VALUES = {
    "DMF1": [0.854, 0.913, 0.781, 0.857],
    "PropF1": [0.628, 0.668, 0.496, 0.649],
}

CORE_COLOR = "#6679C4"
NO_VALUES_COLOR = "#4C9A8B"
CONNECTOR_COLOR = "#AEB6BE"

plt.rcParams.update({
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "serif",
    "font.size": 6.5,
    "axes.titlesize": 7,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6.2,
    "legend.fontsize": 6.2,
})

fig, axes = plt.subplots(1, 2, figsize=(3.35, 1.48), sharey=True)
y = np.arange(len(DATASETS))

axis_settings = {
    "DMF1": ((0.75, 0.95), [0.76, 0.80, 0.84, 0.88, 0.92]),
    "PropF1": ((0.47, 0.72), [0.50, 0.55, 0.60, 0.65, 0.70]),
}

for ax, metric in zip(axes, ("DMF1", "PropF1")):
    core = np.asarray(CORE[metric])
    no_values = np.asarray(NO_VALUES[metric])

    for row, (left, right) in enumerate(zip(core, no_values)):
        ax.plot(
            [left, right], [row, row],
            color=CONNECTOR_COLOR,
            linewidth=1.0,
            solid_capstyle="round",
            zorder=1,
        )

    ax.scatter(core, y, s=22, color=CORE_COLOR, edgecolor="white", linewidth=0.45, zorder=3)
    ax.scatter(no_values, y, s=22, marker="D", color=NO_VALUES_COLOR, edgecolor="white", linewidth=0.45, zorder=3)

    xlim, xticks = axis_settings[metric]
    for row, (core_value, no_values_value) in enumerate(zip(core, no_values)):
        delta = no_values_value - core_value
        ax.text(
            (core_value + no_values_value) / 2,
            row - 0.13,
            f"{delta:+.3f}",
            ha="center",
            va="bottom",
            fontsize=5.2,
            color="#59636D",
        )

    ax.set_title(metric, pad=3)
    ax.set_xlim(*xlim)
    ax.set_xticks(xticks)
    ax.set_ylim(len(DATASETS) - 0.55, -0.45)
    ax.grid(axis="x", color="#D9DEE3", linewidth=0.4, alpha=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for spine in ax.spines.values():
        spine.set_linewidth(0.4)
    ax.tick_params(axis="both", length=2.2, width=0.4, pad=1.5)

axes[0].set_yticks(y, DATASETS)
axes[1].tick_params(axis="y", left=False, labelleft=False)

legend_handles = [
    Line2D([], [], marker="o", linestyle="none", markersize=4.5,
           markerfacecolor=CORE_COLOR, markeredgecolor="white", label="CoRE"),
    Line2D([], [], marker="D", linestyle="none", markersize=4.2,
           markerfacecolor=NO_VALUES_COLOR, markeredgecolor="white", label="NoValues"),
]
fig.legend(
    handles=legend_handles,
    ncol=2,
    loc="upper center",
    bbox_to_anchor=(0.5, 0.88),
    frameon=False,
    columnspacing=1.0,
    handletextpad=0.35,
    borderaxespad=0,
)

fig.subplots_adjust(left=0.17, right=0.995, bottom=0.19, top=0.70, wspace=0.10)

out_dir = Path(__file__).resolve().parent / "figures"
out_dir.mkdir(parents=True, exist_ok=True)
for suffix, kwargs in (("pdf", {}), ("png", {"dpi": 300})):
    fig.savefig(
        out_dir / f"no_values_dumbbell_preview.{suffix}",
        format=suffix,
        bbox_inches="tight",
        pad_inches=0.01,
        **kwargs,
    )

plt.close(fig)
print(f"saved to: {out_dir / 'no_values_dumbbell_preview.pdf'}")
