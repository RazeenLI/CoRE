"""Figure 2: normalized decision confusion matrices (rows: reference
operation, columns: predicted operation) for the Standard method on
TPC-DS, Spider, and MONDIAL.

Data is loaded live from outputs/<Dataset>/standard/{small,medium,large}.csv
via data_loader.decision_confusion_matrix -- verified to reproduce the
paper's confusion-matrix table exactly (Experimental Evaluation.tex).
Run this file directly to regenerate the PDF.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from data_loader import (
    OPERATIONS,
    load_evaluated_rows,
    decision_confusion_matrix,
)


# -----------------------------
# data
# -----------------------------
DATASETS = ["TPCDS", "Spider", "MONDIAL"]

DATASET_LABELS = {
    "TPCDS": "TPC-DS",
    "Spider": "Spider",
    "MONDIAL": "MONDIAL",
}

METHOD = "standard"

operation_keys = [key for key, _ in OPERATIONS]

# Abbreviated operation labels:
# I = Insert, E = Extend, C = Create
labels = [label[0] for _, label in OPERATIONS]


# -----------------------------
# colormap
# -----------------------------
PAIRED_BLUE_ORANGE = [
    "#284F76",
    "#6891BA",
    "#C0C9D3",
    "#F4F2ED",
    "#E2D8CF",
    "#D29D6F",
    "#9F5A1E",
]

CMAP = LinearSegmentedColormap.from_list(
    "db_paired_blue_orange",
    PAIRED_BLUE_ORANGE,
)


# -----------------------------
# confusion matrices
# -----------------------------
conf_mats = {
    DATASET_LABELS[ds]: decision_confusion_matrix(
        load_evaluated_rows(ds, METHOD),
        operation_keys,
    )
    for ds in DATASETS
}


# ============================================================
# Publication settings
# ============================================================

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["font.family"] = "serif"

plt.rcParams["font.size"] = 7
plt.rcParams["axes.titlesize"] = 8
plt.rcParams["axes.labelsize"] = 7
plt.rcParams["xtick.labelsize"] = 6.5
plt.rcParams["ytick.labelsize"] = 6.5


# -----------------------------
# figure
#
# Same overall single-column structure as Figure 1.
# Slightly taller because of the horizontal colorbar.
# -----------------------------
fig_w = 3.35
fig_h = 1.55

fig, axes = plt.subplots(
    nrows=1,
    ncols=3,
    figsize=(fig_w, fig_h),
)


# Shared scale
vmin = 0.0
vmax = 1.0


# ============================================================
# heatmaps
# ============================================================

for col, (ax, (dataset, cm)) in enumerate(
    zip(axes, conf_mats.items())
):

    im = ax.imshow(
        cm,
        cmap=CMAP,
        vmin=vmin,
        vmax=vmax,

        # Do not let imshow create large horizontal whitespace
        # inside each subplot.
        aspect="auto",

        interpolation="nearest",
    )

    # Keep the heatmap area itself square.
    ax.set_box_aspect(1)

    # -------------------------
    # ticks
    # -------------------------
    ax.set_xticks(np.arange(3))
    ax.set_yticks(np.arange(3))

    ax.set_xticklabels(labels)

    if col == 0:
        ax.set_yticklabels(labels)
        ax.set_ylabel("Reference")
    else:
        ax.set_yticklabels([])

    # -------------------------
    # title / xlabel
    # -------------------------
    ax.set_title(
        dataset,
        pad=2,
    )

    ax.set_xlabel(
        "Prediction",
        labelpad=2,
    )

    # -------------------------
    # annotations
    # -------------------------
    for i in range(3):
        for j in range(3):

            value = cm[i, j]

            r, g, b, _ = CMAP(value)

            luminance = (
                0.299 * r
                + 0.587 * g
                + 0.114 * b
            )

            text_color = (
                "white"
                if luminance < 0.6
                else "black"
            )

            ax.text(
                j,
                i,
                f"{value:.2f}",
                ha="center",
                va="center",
                fontsize=6.5,
                color=text_color,
            )

    # -------------------------
    # cell boundaries
    # -------------------------
    ax.set_xticks(
        np.arange(-0.5, 3, 1),
        minor=True,
    )

    ax.set_yticks(
        np.arange(-0.5, 3, 1),
        minor=True,
    )

    ax.grid(
        which="minor",
        linewidth=0.45,
    )

    ax.tick_params(
        which="minor",
        bottom=False,
        left=False,
    )

    ax.tick_params(
        axis="both",
        length=0,
    )


# ============================================================
# Main panel layout
#
# Similar horizontal structure to Figure 1:
# - left margin for y labels
# - small right safety margin
# - visible but not excessive space between panels
# ============================================================

fig.subplots_adjust(
    left=0.088,
    right=0.992,
    top=0.93,

    # More bottom space because colorbar sits below heatmaps.
    bottom=0.34,

    # Similar visual spacing to Figure 1.
    wspace=0.18,
)


# ============================================================
# Shared colorbar
#
# Use a dedicated fixed axes instead of fig.colorbar(ax=axes).
# This prevents the colorbar from shrinking / separating
# the three heatmap panels.
# ============================================================

cbar_ax = fig.add_axes([
    0.285,   # left
    0.105,   # bottom
    0.43,    # width
    0.035,   # height
])

cbar = fig.colorbar(
    im,
    cax=cbar_ax,
    orientation="horizontal",
)

cbar.ax.tick_params(
    labelsize=6,
    pad=1.5,
    length=2,
)

cbar.ax.text(
    1.04,
    0.5,
    "Fraction",
    transform=cbar.ax.transAxes,
    ha="left",
    va="center",
    fontsize=7,
)


# ============================================================
# save
# ============================================================

out_path = "visualization/figures/fig2_confusion_heatmaps.pdf"

plt.savefig(
    out_path,
    format="pdf",
    pad_inches=0,
)

plt.close(fig)

print(f"saved to: {out_path}")