"""Pie-chart human-decision comparison for reference--CoRE disagreements."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[1]
ANNOTATION_ROOT = ROOT / "artifacts" / "annotation"
RESPONSE_ROOT = ANNOTATION_ROOT / "responses"

# Academic AI/ML palette used by the other paper figures.
COLORS = {
    "Reference only": "#4C9A8B",
    "CoRE only": "#6679C4",
    "Both": "#CB6C9D",
    "No majority": "#8CA0AD",
}

EDGE_COLORS = {
    "Reference only": "#376D64",
    "CoRE only": "#4C5FA4",
    "Both": "#AE4779",
    "No majority": "#596F7D",
}


def load_counts() -> tuple[Counter[str], int]:
    manifest = json.loads(
        (ANNOTATION_ROOT / "selected_cases.json").read_text(encoding="utf-8")
    )
    cases = {case["case_token"]: case for case in manifest["cases"]}
    annotations = []
    for path in sorted(RESPONSE_ROOT.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("manifest_id") != manifest["manifest_id"]:
            raise ValueError(f"Manifest mismatch: {path}")
        annotations.append({
            row["case_token"]: set(row.get("selected_operations", []))
            for row in payload.get("responses", [])
        })
    if not annotations:
        raise ValueError(f"No annotation files found under {RESPONSE_ROOT}")

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
categories = ["Reference only", "Both", "CoRE only", "No majority"]

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.size"] = 6.5
plt.rcParams["legend.fontsize"] = 6.0

fig, ax = plt.subplots(figsize=(3.35, 1.35))

values = [counts[category] for category in categories]
labels = categories
wedges, label_texts, value_texts = ax.pie(
    values,
    labels=labels,
    colors=[COLORS[category] for category in categories],
    startangle=90,
    counterclock=False,
    radius=0.88,
    labeldistance=1.00,
    autopct=lambda pct: f"{int(round(pct * case_count / 100.0))}",
    pctdistance=0.68,
    textprops={"fontsize": 6.5},
    wedgeprops={"linewidth": 0.8, "edgecolor": "white"},
)
for value_text in value_texts:
    value_text.set_color("white")
    value_text.set_fontweight("semibold")
    value_text.set_fontsize(6.8)

ax.set_aspect("equal")
ax.set_ylim(-0.94, 0.94)
fig.subplots_adjust(left=0.002, right=0.998, top=0.998, bottom=0.002)

out_dir = Path(__file__).resolve().parent / "figures"
out_dir.mkdir(parents=True, exist_ok=True)
for suffix, kwargs in (("pdf", {}), ("png", {"dpi": 300})):
    plt.savefig(
        out_dir / f"human_decision_comparison_pie_preview.{suffix}",
        format=suffix,
        bbox_inches="tight",
        pad_inches=0.002,
        **kwargs,
    )
plt.close(fig)

print(f"counts: {dict(counts)}")
print("saved to: human_decision_comparison_pie_preview.pdf")
