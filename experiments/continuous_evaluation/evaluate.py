from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from evaluation.evaluator import evaluate_benchmark, save_results_csv


ROOT = Path(__file__).resolve().parents[2]


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=("Spider", "TPCDS"), required=True)
    parser.add_argument("--mode", choices=("oracle", "rollout"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    benchmark_root = ROOT / "data" / "continuous_benchmark" / args.dataset
    result_root = ROOT / "save" / "continuous" / args.dataset / args.mode
    output_root = ROOT / "outputs" / "continuous" / args.dataset
    output_root.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []

    for sequence_dir in sorted(benchmark_root.glob("sequence_*")):
        result_sequence = result_root / sequence_dir.name
        with tempfile.TemporaryDirectory(prefix="core-continuous-eval-") as temp:
            temp_root = Path(temp)
            staged_benchmark = temp_root / "benchmark"
            staged_results = temp_root / "results"
            staged_benchmark.mkdir()
            staged_results.mkdir()
            for step_dir in sorted((sequence_dir / "steps").glob("step_*")):
                case_name = step_dir.name.replace("step_", "case_")
                case_dir = staged_benchmark / case_name
                case_dir.mkdir()
                os.symlink(step_dir / "oracle_existing", case_dir / "existing", target_is_directory=True)
                os.symlink(step_dir / "incoming", case_dir / "incoming", target_is_directory=True)
                os.symlink(step_dir / "expected", case_dir / "expected", target_is_directory=True)
                result_step = result_sequence / step_dir.name
                os.symlink(result_step, staged_results / case_name, target_is_directory=True)
            rows = evaluate_benchmark(
                benchmark_dir=staged_benchmark,
                result_dir=staged_results,
                output_csv_path=temp_root / "rows.csv",
                sample_num=3,
            )
            for row in rows:
                row["dataset"] = args.dataset
                row["mode"] = args.mode
                row["sequence"] = sequence_dir.name
                row["step"] = int(str(row["case_id"]).split("_")[-1])
                all_rows.append(row)

    save_results_csv(all_rows, output_root / f"{args.mode}.csv")
    by_step: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        if row.get("evaluation_status") == "evaluated":
            by_step[int(row["step"])].append(row)
    step_summary = {}
    for step, rows in sorted(by_step.items()):
        step_summary[str(step)] = {
            "coverage": len(rows),
            "decision_macro_f1": decision_macro_f1(rows),
            "proposal_micro_f1": proposal_micro_f1(rows),
            "schema_exact": mean([float(row["final_schema_exact_match"]) for row in rows]),
            "structural_validity": mean([
                float(row["proposal_validity_checked_valid"]) for row in rows
            ]),
        }
    summary = {
        "dataset": args.dataset,
        "mode": args.mode,
        "expected_cases": 50,
        "evaluated_cases": sum(len(rows) for rows in by_step.values()),
        "steps": step_summary,
        "final_step": step_summary.get("10", {}),
    }
    (output_root / f"{args.mode}_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
