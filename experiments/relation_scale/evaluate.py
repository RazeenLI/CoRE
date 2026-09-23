from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation.evaluator import evaluate_benchmark


ROOT = Path(__file__).resolve().parents[2]
DATASETS = ("Chinook", "Spider")
LEVELS = ("original", "25", "50", "100")


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def decision_macro_f1(rows: list[dict[str, Any]]) -> float | None:
    scores = []
    for operation in ("insert_table", "extend_table", "create_table"):
        tp = sum(row["decision_predicted"] == operation and row["decision_reference"] == operation for row in rows)
        fp = sum(row["decision_predicted"] == operation and row["decision_reference"] != operation for row in rows)
        fn = sum(row["decision_predicted"] != operation and row["decision_reference"] == operation for row in rows)
        denominator = 2 * tp + fp + fn
        scores.append((2 * tp / denominator) if denominator else 0.0)
    return mean(scores)


def proposal_micro_f1(rows: list[dict[str, Any]]) -> float | None:
    tp = sum(int(row["proposal_fact_true_positive"]) for row in rows)
    fp = sum(int(row["proposal_fact_false_positive"]) for row in rows)
    fn = sum(int(row["proposal_fact_false_negative"]) for row in rows)
    denominator = 2 * tp + fp + fn
    return (2 * tp / denominator) if denominator else None


def main() -> None:
    summary: dict[str, Any] = {}
    for dataset in DATASETS:
        summary[dataset] = {}
        for level in LEVELS:
            split = f"scale_{level}"
            rows = evaluate_benchmark(
                benchmark_dir=ROOT / "data" / dataset / "benchmarks" / split,
                result_dir=ROOT / "save" / dataset / "standard" / split,
                output_csv_path=ROOT / "outputs" / dataset / "standard" / f"{split}.csv",
                sample_num=3,
            )
            evaluated = [row for row in rows if row.get("evaluation_status") == "evaluated"]
            summary[dataset][level] = {
                "coverage": len(evaluated),
                "decision_macro_f1": decision_macro_f1(evaluated),
                "proposal_micro_f1": proposal_micro_f1(evaluated),
                "latency_seconds": mean([
                    float(row["timing_end_to_end_seconds"]) for row in evaluated
                    if row.get("timing_end_to_end_seconds") is not None
                ]),
            }
    output = ROOT / "outputs" / "relation_scale_summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
