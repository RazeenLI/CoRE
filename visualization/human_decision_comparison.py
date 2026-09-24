"""Compact human-decision comparison for reference--CoRE disagreements."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ROOT = ROOT / "experiments" / "alternative_validity"
ANNOTATION_ROOT = EXPERIMENT_ROOT / "annotations"

# Academic AI/ML palette used by the other paper figures.
COLORS = {
    "Reference only": "#3F8D81",
    "CoRE only": "#5C71BC",
    "Both": "#C5598D",
    "No majority": "#678598",
}

EDGE_COLORS = {
    "Reference only": "#376D64",
    "CoRE only": "#4C5FA4",
    "Both": "#AE4779",
    "No majority": "#596F7D",
}


def load_counts() -> tuple[Counter[str], int]:
    manifest = json.loads(
        (EXPERIMENT_ROOT / "selected_cases.json").read_text(encoding="utf-8")
    )
    cases = {case["case_token"]: case for case in manifest["cases"]}
    annotations = []
    for path in sorted(ANNOTATION_ROOT.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("manifest_id") != manifest["manifest_id"]:
            raise ValueError(f"Manifest mismatch: {path}")
        annotations.append({
            row["case_token"]: set(row.get("selected_operations", []))
            for row in payload.get("responses", [])
        })
    if not annotations:
        raise ValueError(f"No annotation files found under {ANNOTATION_ROOT}")

    threshold = math.floor(len(annotations) / 2) + 1
    counts: Counter[str] = Counter()
    for token, case in cases.items():
        reference = case["reference_decision"]
        prediction = case["predicted_decision"]
        reference_supported = sum(
            reference in values.get(token, set()) for values in annotations
        ) >= threshold
        core_supported = sum(
            prediction in values.get(token, set()) for values in annotations
        ) >= threshold
        if reference_supported and core_supported:
            counts["Both"] += 1
        elif reference_supported:
            counts["Reference only"] += 1
        elif core_supported:
            counts["CoRE only"] += 1
        else:
            counts["No majority"] += 1
    return counts, len(cases)


counts, case_count = load_counts()
categories = ["Reference only", "CoRE only", "Both", "No majority"]

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.size"] = 6.5
plt.rcParams["legend.fontsize"] = 6.0

fig, ax = plt.subplots(figsize=(3.35, 0.42))

left = 0.0
for category in categories:
    value = counts[category]
    width = 100.0 * value / case_count
    ax.barh(
        0,
        width,
        left=left,
        height=0.34,
        color=COLORS[category],
        edgecolor=EDGE_COLORS[category],
        linewidth=0.45,
    )
    ax.text(
        left + width / 2,
        0,
        f"{value}",
        ha="center",
        va="center",
        fontsize=6.2,
        color="white",
        fontweight="semibold",
    )
    left += width

ax.set_xlim(0, 100)
ax.set_ylim(-0.32, 0.32)
ax.axis("off")

handles = [
    Patch(
        facecolor=COLORS[category],
        edgecolor=EDGE_COLORS[category],
        linewidth=0.45,
        label=category,
    )
    for category in categories
]
fig.legend(
    handles=handles,
    ncol=4,
    loc="upper center",
    bbox_to_anchor=(0.5, 0.74),
    frameon=False,
    columnspacing=0.55,
    handlelength=0.85,
    handletextpad=0.3,
    borderaxespad=0,
)

fig.subplots_adjust(left=0.005, right=0.995, top=0.58, bottom=0.01)

out_dir = Path(__file__).resolve().parent / "figures"
out_dir.mkdir(parents=True, exist_ok=True)
for suffix, kwargs in (("pdf", {}), ("png", {"dpi": 300})):
    plt.savefig(
        out_dir / f"human_decision_comparison.{suffix}",
        format=suffix,
        bbox_inches="tight",
        pad_inches=0,
        **kwargs,
    )
plt.close(fig)

print(f"counts: {dict(counts)}")
print(f"saved to: {out_dir / 'human_decision_comparison.pdf'}")
