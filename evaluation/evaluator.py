from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from model.utils.io import load_rdb, load_table, load_json

from evaluation.validate import check_proposal_validity

from evaluation.metrics import (
    compute_decision_metrics,
    compute_target_table_metrics,
    compute_column_placement_metrics,
    compute_proposal_fact_metrics,
    compute_required_column_coverage,
    compute_proposal_validity_metrics,
    compute_non_target_preservation_metrics,
    compute_fact_set_metrics,
    extract_constraint_facts,
    extract_schema_facts,
)


# =====================================================
# Batch evaluation configuration
# =====================================================

# Edit these lists to select the experiment results to evaluate.
DATASETS = [
    "Chinook",
    "MONDIAL",
    "TPCDS",
]

MODELS = [
    "standard",
    "oneshot",
    "coma",
    "jl",
    "magneto",
    "no_profiler",
    "no_selector",
    "no_validator",
    "no_values",
    "santos",
    "embdi",
    "starmie",
]

SIZES = ["small", "medium", "large"]

DATA_ROOT = Path("data")
SAVE_ROOT = Path("save")
OUTPUT_ROOT = Path("outputs")
SAMPLE_NUM = 0


def compute_task_state_metrics(task_state: dict[str, Any]) -> dict[str, Any]:
    """Extract run completion and revision-loop counters from a saved task state."""
    results = task_state.get("results", {})
    if not isinstance(results, dict):
        results = {}
    validations = results.get("validating", [])
    if not isinstance(validations, list):
        validations = []
    validator_calls = len(validations)
    retries = max(validator_calls - 1, 0)
    exhausted = any(
        isinstance(item, dict)
        and (
            item.get("route") == "error"
            or any(
                "maximum retry" in str(issue).lower()
                for issue in item.get("issues", [])
            )
        )
        for item in validations
    )
    final_route = (
        validations[-1].get("route")
        if validations and isinstance(validations[-1], dict)
        else None
    )
    return {
        "pipeline_succeeded": task_state.get("status") == "succeeded",
        "validator_call_count": validator_calls,
        "retry_count": retries,
        "retried": retries > 0,
        "retry_exhausted": exhausted,
        "validator_final_route": final_route,
        "validator_accepted": final_route == "decision" if final_route else None,
    }


def flatten_dict(
    data: dict[str, Any],
    prefix: str = "",
) -> dict[str, Any]:
    """
    Flatten nested metric results for CSV storage.

    Example:
        {
            "precision": 0.8,
            "details": {
                "tp": 4
            }
        }

    becomes:
        {
            "precision": 0.8,
            "details_tp": 4
        }
    """
    result: dict[str, Any] = {}

    for key, value in data.items():
        output_key = f"{prefix}_{key}" if prefix else key

        if isinstance(value, dict):
            result.update(
                flatten_dict(
                    data=value,
                    prefix=output_key,
                )
            )
        elif isinstance(value, (list, set, tuple)):
            # CSV cells cannot directly store collections.
            result[output_key] = str(value)
        else:
            result[output_key] = value

    return result


def save_results_csv(
    rows: list[dict[str, Any]],
    output_path: str | Path,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
        raise ValueError("No evaluation results to save.")

    fieldnames: list[str] = []

    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def evaluate_benchmark(
    benchmark_dir: str | Path,
    result_dir: str | Path,
    output_csv_path: str | Path,
    sample_num: int = 0,
) -> list[dict[str, Any]]:
    """
    Evaluate all case_* folders.

    Benchmark structure:
        benchmark_dir/
            case_0002/
                existing/
                incoming/
                expected/

    Model result structure:
        result_dir/
            case_0002/
                proposal.json
                database/

    Output:
        One CSV row per case.
    """
    benchmark_dir = Path(benchmark_dir)
    result_dir = Path(result_dir)

    case_dirs = sorted(
        path
        for path in benchmark_dir.glob("case_*")
        if path.is_dir()
    )

    if not case_dirs:
        raise ValueError(
            f"No case_* directories found: {benchmark_dir}"
        )

    all_results: list[dict[str, Any]] = []

    for case_dir in case_dirs:
        case_id = case_dir.name
        result_case_dir = result_dir / case_id

        predicted_rdb_path = result_case_dir / "database"
        predicted_proposal_path = result_case_dir / "proposal.json"
        task_state_path = result_case_dir / "task_state.json"

        timing_result: dict[str, Any] = {}
        task_state_result: dict[str, Any] = {}
        if task_state_path.exists():
            try:
                task_state = load_json(task_state_path)
                timing_result = task_state.get("timing", {})
                task_state_result = compute_task_state_metrics(task_state)
            except (FileNotFoundError, ValueError):
                timing_result = {}
                task_state_result = {}

        # ---------------------------------------------
        # 1. Load benchmark data
        # ---------------------------------------------

        existing_rdb = load_rdb(
            rdb_path=case_dir / "existing",
            sample_num=sample_num,
        )

        incoming_table = load_table(
            table_path=case_dir / "incoming",
            sample_num=sample_num,
        )

        expected_rdb = load_rdb(
            rdb_path=case_dir / "expected",
            sample_num=sample_num,
        )

        expected_proposal = load_json(
            case_dir / "expected" / "proposal.json"
        )

        # ---------------------------------------------
        # 2. Check whether model result exists
        # ---------------------------------------------

        missing_paths: list[str] = []

        if not predicted_rdb_path.exists():
            missing_paths.append(str(predicted_rdb_path))

        if not predicted_proposal_path.exists():
            missing_paths.append(str(predicted_proposal_path))

        if missing_paths:
            missing_result = {
                    "case_id": case_id,
                    "evaluation_status": "missing_result",
                    "result_available": False,
                    "error": (
                        "Missing model result: "
                        + ", ".join(missing_paths)
                    ),
                }
            missing_result.update(flatten_dict(timing_result, prefix="timing"))
            missing_result.update(flatten_dict(task_state_result, prefix="run"))
            all_results.append(missing_result)
            continue

        # ---------------------------------------------
        # 3. Load model result
        # ---------------------------------------------

        try:
            predicted_rdb = load_rdb(
                rdb_path=predicted_rdb_path,
                sample_num=sample_num,
            )

            predicted_proposal = load_json(
                predicted_proposal_path
            )

        except (FileNotFoundError, ValueError) as exc:
            failed_result = {
                    "case_id": case_id,
                    "evaluation_status": "result_load_failed",
                    "result_available": False,
                    "error": str(exc),
                }
            failed_result.update(flatten_dict(timing_result, prefix="timing"))
            failed_result.update(flatten_dict(task_state_result, prefix="run"))
            all_results.append(failed_result)
            continue

        # ---------------------------------------------
        # 4. Call metrics
        # ---------------------------------------------


        ##### Decision Accuracy #####

        decision_result = compute_decision_metrics(
            predicted_decision=predicted_proposal["source_decision"], # "create_table",
            reference_decision=expected_proposal["decision"], # "extend_table",
        )

        # print(json.dumps(expected_proposal, indent=4))

        ##### Target Table Accuracy #####

        reference_decision = expected_proposal["decision"]

        target_table_applicable = reference_decision in {"extend_table", "insert_table"}

        predicted_target_tables = [
            table_action["table"]
            for table_action in predicted_proposal.get("table_actions",[],)
            if (table_action.get("action") == "map" and table_action.get("table"))
        ]

        target_table_result = compute_target_table_metrics(
            predicted_target_tables=predicted_target_tables,
            reference_target_table=expected_proposal.get("target_table"),
            applicable=target_table_applicable,
        )

        ##### Column Placement #####

        predicted_column_placements: set[tuple[str, str, str]] = set()

        for table_action in predicted_proposal.get("table_actions", []):
            target_table = table_action["table"]

            for column_action in table_action.get("column_actions", []):
                source_columns = column_action.get("source_columns", [])
                target_columns = column_action.get("target_columns", [])

                for source_column, target_column in zip(source_columns, target_columns):
                    predicted_column_placements.add((source_column, target_table, target_column))

        reference_column_placements: set[tuple[str, str, str]] = set()

        for source_column, target_location in expected_proposal.get("column_placements", {}).items():
            target_table, target_column = target_location.split(".", maxsplit=1)

            reference_column_placements.add((source_column, target_table, target_column))

        column_placement_result = compute_column_placement_metrics(
            predicted_placements=predicted_column_placements,
            reference_placements=reference_column_placements,
        )

        ##### Proposal Fact #####
        predicted_proposal_facts: set[tuple[Any, ...]] = {("decision", predicted_proposal["source_decision"])}

        for table_action in predicted_proposal.get("table_actions", []):
            table_name = table_action["table"]
            table_action_type = table_action["action"]

            if table_action_type == "map":
                predicted_proposal_facts.add(("target_table", table_name))

            elif table_action_type == "create":
                predicted_proposal_facts.add(("create_table", table_name))

            for column_action in table_action.get("column_actions", []):
                column_action_type = column_action["action"]

                source_columns = column_action.get("source_columns", [],)
                target_columns = column_action.get("target_columns", [])

                for source_column, target_column in zip(source_columns, target_columns):
                    # Every column placement produces a map fact,
                    # regardless of whether the target column already
                    # exists or is newly created.
                    predicted_proposal_facts.add(("map", source_column, table_name, target_column))

                    if column_action_type == "create":
                        predicted_proposal_facts.add(("add_column", table_name, target_column))

        reference_proposal_facts: set[tuple[Any, ...]] = {("decision", expected_proposal["decision"])}

        reference_target_table = expected_proposal.get("target_table")

        if reference_target_table:
            reference_proposal_facts.add(("target_table", reference_target_table))

        created_table = expected_proposal.get("created_table")

        if created_table:
            reference_proposal_facts.add(("create_table", created_table))

        for table_name, columns in expected_proposal.get("added_columns", {}).items():
            for column_name in columns:
                reference_proposal_facts.add(("add_column", table_name, column_name))

        for source_column, target_location in (
            expected_proposal.get("column_placements", {}).items()):
            target_table, target_column = (target_location.split(".", maxsplit=1))

            reference_proposal_facts.add(("map", source_column, target_table, target_column))

        proposal_fact_result = compute_proposal_fact_metrics(
            predicted_facts=predicted_proposal_facts,
            reference_facts=reference_proposal_facts,
        )

        operation_only_result = compute_fact_set_metrics(
            predicted_facts={
                fact for fact in predicted_proposal_facts
                if fact[0] != "decision"
            },
            reference_facts={
                fact for fact in reference_proposal_facts
                if fact[0] != "decision"
            },
        )

        predicted_table_actions = {
            fact for fact in predicted_proposal_facts
            if fact[0] in {"target_table", "create_table"}
        }
        reference_table_actions = {
            fact for fact in reference_proposal_facts
            if fact[0] in {"target_table", "create_table"}
        }
        table_action_result = compute_fact_set_metrics(
            predicted_table_actions,
            reference_table_actions,
        )
        predicted_column_actions = {
            fact for fact in predicted_proposal_facts
            if fact[0] in {"map", "add_column"}
        }
        reference_column_actions = {
            fact for fact in reference_proposal_facts
            if fact[0] in {"map", "add_column"}
        }
        column_action_result = compute_fact_set_metrics(
            predicted_column_actions,
            reference_column_actions,
        )

        primary_key_result = compute_fact_set_metrics(
            extract_constraint_facts(predicted_rdb, {"primary_key"}),
            extract_constraint_facts(expected_rdb, {"primary_key"}),
        )
        foreign_key_result = compute_fact_set_metrics(
            extract_constraint_facts(predicted_rdb, {"foreign_key"}),
            extract_constraint_facts(expected_rdb, {"foreign_key"}),
        )
        final_constraint_result = compute_fact_set_metrics(
            extract_constraint_facts(predicted_rdb),
            extract_constraint_facts(expected_rdb),
        )
        final_schema_result = compute_fact_set_metrics(
            extract_schema_facts(predicted_rdb),
            extract_schema_facts(expected_rdb),
        )

        # -----------------------------------
        # Functional Validity
        # -----------------------------------

        ##### Required Column Coverage #####

        incoming_table_name = next(iter(incoming_table["schema"]["tables"]))

        required_columns = set(incoming_table["schema"]["tables"][incoming_table_name]["columns"])

        covered_columns: set[str] = set()

        for table_action in predicted_proposal.get("table_actions",[],):
            for column_action in table_action.get("column_actions",[],):
                if column_action.get("action") not in {"map","create"}:
                    continue

                covered_columns.update(column_action.get("source_columns",[]))

        required_column_coverage_result = compute_required_column_coverage(
            required_columns=required_columns,
            covered_columns=covered_columns,
        )

        # print(predicted_rdb)

        ##### Proposal Validity #####

        validity_data = check_proposal_validity(
            existing_rdb=existing_rdb,
            incoming_table=incoming_table,
            predicted_proposal=predicted_proposal,
            predicted_rdb=predicted_rdb,
        )

        proposal_validity_result = compute_proposal_validity_metrics(
            raw_valid=validity_data["raw_valid"],
            checked_valid=validity_data["checked_valid"],
            invalid_references=validity_data["invalid_references"],
            broken_foreign_keys=validity_data["broken_foreign_keys"],
            duplicate_definitions=validity_data["duplicate_definitions"],
            conflicting_operations=validity_data["conflicting_operations"],
        )

        validator_accepted = task_state_result.get("validator_accepted")
        validator_quality_result: dict[str, Any] = {
            "applicable": validator_accepted is not None,
            "accepted": validator_accepted,
            "actual_valid": validity_data["checked_valid"],
            "false_accept": (
                bool(validator_accepted) and not validity_data["checked_valid"]
                if validator_accepted is not None else None
            ),
            "false_reject": (
                not bool(validator_accepted) and validity_data["checked_valid"]
                if validator_accepted is not None else None
            ),
        }

        non_target_preservation_result = compute_non_target_preservation_metrics(
            existing_rdb=existing_rdb,
            predicted_rdb=predicted_rdb,
            protected_tables=expected_proposal["protected_tables"],
        )

        # ---------------------------------------------
        # 3. Build one CSV row for this case
        # ---------------------------------------------

        case_result: dict[str, Any] = {
            "case_id": case_id,
            "evaluation_status": "evaluated",
            "result_available": True,
            "error": "",
        }

        # print(json.dumps(case_result, indent=4))

        # case_result["decision"] = decision_result

        # case_result["target_table"] = target_table_result

        # case_result["column_placement"] = column_placement_result

        # case_result["proposal_fact"] = proposal_fact_result

        # case_result["required_column_coverage"] = required_column_coverage_result

        # case_result["proposal_validity"] = proposal_validity_result

        # case_result["non_target_preservation"] = non_target_preservation_result

        case_result.update(flatten_dict(decision_result, prefix="decision"))

        case_result.update(flatten_dict(target_table_result, prefix="target_table"))

        case_result.update(flatten_dict(column_placement_result, prefix="column_placement",))

        case_result.update(flatten_dict(proposal_fact_result, prefix="proposal_fact"))

        case_result.update(flatten_dict(operation_only_result, prefix="operation_only_fact"))
        case_result.update(flatten_dict(table_action_result, prefix="table_action"))
        case_result.update(flatten_dict(column_action_result, prefix="column_action"))
        case_result.update(flatten_dict(primary_key_result, prefix="primary_key"))
        case_result.update(flatten_dict(foreign_key_result, prefix="foreign_key"))
        case_result.update(flatten_dict(final_constraint_result, prefix="final_constraint"))
        case_result.update(flatten_dict(final_schema_result, prefix="final_schema"))

        case_result.update(flatten_dict(required_column_coverage_result, prefix="required_column_coverage"))

        case_result.update(flatten_dict(proposal_validity_result, prefix="proposal_validity"))
        case_result.update(flatten_dict(validator_quality_result, prefix="validator_quality"))

        case_result.update(flatten_dict(non_target_preservation_result, prefix="non_target_preservation"))

        case_result.update(flatten_dict(timing_result, prefix="timing"))
        case_result.update(flatten_dict(task_state_result, prefix="run"))

        # print(json.dumps(case_result, indent=4))

        all_results.append(case_result)

    # ---------------------------------------------
    # 4. Save all case results as one CSV
    # ---------------------------------------------

    save_results_csv(
        rows=all_results,
        output_path=output_csv_path,
    )

    return all_results

def main() -> None:
    for dataset in DATASETS:
        for model in MODELS:
            for size in SIZES:
                benchmark_dir = (
                    DATA_ROOT / dataset / "benchmarks" / size
                )
                result_dir = SAVE_ROOT / dataset / model / size
                output_path = OUTPUT_ROOT / dataset / model / f"{size}.csv"

                print(
                    f"[Evaluation] dataset={dataset} "
                    f"model={model} size={size}"
                )
                evaluate_benchmark(
                    benchmark_dir=benchmark_dir,
                    result_dir=result_dir,
                    output_csv_path=output_path,
                    sample_num=SAMPLE_NUM,
                )
                print(f"[Saved] {output_path}")


if __name__ == "__main__":
    main()
