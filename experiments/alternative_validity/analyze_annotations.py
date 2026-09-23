from __future__ import annotations

import argparse
import csv
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
OPERATIONS = ("insert_table", "extend_table", "create_table")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cohen_kappa(a: list[bool], b: list[bool]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    observed = sum(x == y for x, y in zip(a, b)) / len(a)
    pa = sum(a) / len(a)
    pb = sum(b) / len(b)
    expected = pa * pb + (1 - pa) * (1 - pb)
    if expected == 1:
        return 1.0 if observed == 1 else None
    return (observed - expected) / (1 - expected)


def jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def category(selected: set[str], reference: str, prediction: str) -> str:
    ref = reference in selected
    pred = prediction in selected
    if ref and pred:
        return "both_reference_and_core"
    if ref:
        return "reference_only"
    if pred:
        return "core_only"
    return "neither"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=HERE / "selected_cases.json")
    parser.add_argument("--output", type=Path, default=HERE / "analysis")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_json(args.manifest)
    labels = {case["case_token"]: case for case in manifest["cases"]}
    paths = sorted(args.responses.glob("*.json"))
    if len(paths) < 2:
        raise ValueError("At least two annotator JSON files are required.")

    annotations: dict[str, dict[str, set[str]]] = {}
    for path in paths:
        payload = load_json(path)
        if payload.get("manifest_id") != manifest["manifest_id"]:
            raise ValueError(f"Manifest mismatch: {path}")
        annotator = str(payload.get("annotator_id", path.stem))
        annotations[annotator] = {
            row["case_token"]: set(row.get("selected_operations", []))
            for row in payload.get("responses", [])
        }

    pairwise: dict[str, list[float]] = defaultdict(list)
    exact_values: list[float] = []
    jaccard_values: list[float] = []
    annotators = sorted(annotations)
    tokens = list(labels)
    for left, right in itertools.combinations(annotators, 2):
        left_data, right_data = annotations[left], annotations[right]
        common = [token for token in tokens if token in left_data and token in right_data]
        exact_values.append(
            sum(left_data[t] == right_data[t] for t in common) / len(common)
        )
        jaccard_values.append(
            sum(jaccard(left_data[t], right_data[t]) for t in common) / len(common)
        )
        for operation in OPERATIONS:
            value = cohen_kappa(
                [operation in left_data[t] for t in common],
                [operation in right_data[t] for t in common],
            )
            if value is not None:
                pairwise[operation].append(value)

    per_annotator = {}
    rows = []
    for annotator, values in annotations.items():
        counts = Counter()
        for token, selected in values.items():
            if token not in labels or not selected:
                continue
            label = labels[token]
            counts[category(
                selected,
                label["reference_decision"],
                label["predicted_decision"],
            )] += 1
            rows.append({
                "annotator_id": annotator,
                **label,
                "selected_operations": ";".join(sorted(selected)),
                "judgment": category(
                    selected,
                    label["reference_decision"],
                    label["predicted_decision"],
                ),
            })
        per_annotator[annotator] = dict(counts)

    summary = {
        "manifest_id": manifest["manifest_id"],
        "annotators": annotators,
        "case_count": len(tokens),
        "mean_pairwise_cohen_kappa": {
            op: (sum(values) / len(values) if values else None)
            for op, values in pairwise.items()
        },
        "mean_exact_set_agreement": sum(exact_values) / len(exact_values),
        "mean_pairwise_jaccard": sum(jaccard_values) / len(jaccard_values),
        "judgments_by_annotator": per_annotator,
    }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with (args.output / "case_judgments.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
