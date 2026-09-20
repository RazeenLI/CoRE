"""Shared helpers for loading per-operation decision P/R/F1 from evaluation
outputs.

This reproduces exactly the "Per-class precision, recall, and F1 for
evolution decisions" table in the paper (Experimental Evaluation.tex,
tab:operation-results): for each label in {insert_table, extend_table,
create_table}, treat decision_predicted vs. decision_reference as a
one-vs-rest classification problem and compute micro P/R/F1 over all
evaluated cases for that dataset/method (small+medium+large concatenated).

This is deliberately NOT proposal_fact_f1 / slice_operation_*_proposal_f1
from evaluation/aggregate_result.py -- that measures correctness of the
full predicted proposal, not decision classification, and gives very
different numbers. Verified to reproduce the paper table's values exactly
(e.g. TPC-DS/CoRE -> Insert P=0.659 R=0.900 F1=0.761).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.aggregate_result import (  # noqa: E402
    convert_result_rows,
    load_result_rows,
    summarize_dataset_results,
)

OUTPUTS_DIR = REPO_ROOT / "outputs"
SIZES = ["small", "medium", "large"]

# decision_reference / decision_predicted value -> display label
OPERATIONS = [
    ("insert_table", "Insert"),
    ("extend_table", "Extend"),
    ("create_table", "Create"),
]


def load_all_rows(dataset: str, method: str) -> list[dict]:
    """Concatenate small/medium/large result rows for one dataset/method,
    without filtering by evaluation_status (timing columns are populated
    regardless of whether the case was evaluated)."""
    rows: list[dict] = []
    for size in SIZES:
        path = OUTPUTS_DIR / dataset / method / f"{size}.csv"
        raw_rows = load_result_rows(path)
        rows.extend(convert_result_rows(raw_rows))
    return rows


def load_evaluated_rows(dataset: str, method: str) -> list[dict]:
    """Concatenate small/medium/large result rows for one dataset/method,
    keeping only cases with evaluation_status == "evaluated"."""
    return [
        row for row in load_all_rows(dataset, method)
        if row.get("evaluation_status") == "evaluated"
    ]


# pipeline stage -> its timing column in the per-case result CSVs
STAGE_TIMING_COLUMNS = [
    ("timing_steps_profiling_total_seconds", "Profile"),
    ("timing_steps_matching_total_seconds", "Select"),
    ("timing_steps_evolving_total_seconds", "Evolve"),
    ("timing_steps_validating_total_seconds", "Validate"),
]


def load_stage_timing_table(
    datasets: list[str],
    method: str,
) -> dict[str, list[float]]:
    """Build {dataset: [mean_profile_s, mean_select_s, mean_evolve_s,
    mean_validate_s]} for one method, averaged over all cases.

    Verified to reproduce the paper's per-stage latency numbers exactly
    (e.g. TPC-DS/CoRE -> [59.1, 6.2, 78.1, 8.0]).
    """
    data: dict[str, list[float]] = {}
    for dataset in datasets:
        rows = load_all_rows(dataset, method)
        data[dataset] = [
            sum(r.get(col) or 0.0 for r in rows) / len(rows)
            for col, _ in STAGE_TIMING_COLUMNS
        ]
    return data


def decision_class_prf(rows: list[dict], label: str) -> tuple[float, float, float]:
    """Micro precision/recall/F1 of predicting `label` as the decision,
    treating decision_predicted vs decision_reference as one-vs-rest."""
    tp = sum(
        1 for r in rows
        if r.get("decision_predicted") == label and r.get("decision_reference") == label
    )
    fp = sum(
        1 for r in rows
        if r.get("decision_predicted") == label and r.get("decision_reference") != label
    )
    fn = sum(
        1 for r in rows
        if r.get("decision_predicted") != label and r.get("decision_reference") == label
    )
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def decision_confusion_matrix(rows: list[dict], labels: list[str]):
    """Row-normalized confusion matrix: rows are reference operation, columns
    are predicted operation. mat[i, j] = P(predicted == labels[j] |
    reference == labels[i]) over the given evaluated rows.

    Matches the "Normalized decision confusion matrices" table in the paper
    (Experimental Evaluation.tex) -- verified to reproduce it exactly (e.g.
    TPC-DS/CoRE row for Ref. Insert -> [0.900, 0.083, 0.017]).
    """
    import numpy as np

    n = len(labels)
    mat = np.zeros((n, n))
    for i, reference in enumerate(labels):
        reference_rows = [r for r in rows if r.get("decision_reference") == reference]
        total = len(reference_rows)
        if not total:
            continue
        for j, predicted in enumerate(labels):
            count = sum(1 for r in reference_rows if r.get("decision_predicted") == predicted)
            mat[i, j] = count / total
    return mat


def summary_for_size(dataset: str, method: str, size: str) -> dict:
    """Per-case-size dataset summary (small/medium/large kept separate,
    unlike load_evaluated_rows which concatenates them)."""
    path = OUTPUTS_DIR / dataset / method / f"{size}.csv"
    rows = convert_result_rows(load_result_rows(path))
    return summarize_dataset_results(rows)


def load_scale_robustness_table(
    datasets: list[str],
    methods: list[tuple[str, str]],
    sizes: tuple[str, ...] = ("small", "medium", "large"),
) -> dict[tuple[str, str], dict[str, list[float]]]:
    """Build {(dataset, metric): {method_label: [val_small, val_medium,
    val_large]}} for metric in {"DMF1", "PropF1"} -- decision_macro_f1 and
    proposal_fact_micro_f1 from evaluation/aggregate_result.py, kept
    per-size (not concatenated across sizes).

    Verified to closely reproduce the reference numbers for this figure
    (e.g. TPC-DS/CoRE DMF1 -> [0.797, 0.871, 0.718] vs reference
    [0.80, 0.87, 0.72]).
    """
    data: dict[tuple[str, str], dict[str, list[float]]] = {}
    for dataset in datasets:
        dmf1: dict[str, list[float]] = {}
        propf1: dict[str, list[float]] = {}
        for method_dir, method_label in methods:
            dmf1[method_label] = []
            propf1[method_label] = []
            for size in sizes:
                summary = summary_for_size(dataset, method_dir, size)
                dmf1[method_label].append(summary["decision_macro_f1"])
                propf1[method_label].append(summary["proposal_fact_micro_f1"])
        data[(dataset, "DMF1")] = dmf1
        data[(dataset, "PropF1")] = propf1
    return data


def load_operation_f1_table(
    datasets: list[str],
    methods: list[tuple[str, str]],
) -> dict[str, dict[str, list[float]]]:
    """Build {dataset: {method_label: [f1_insert, f1_extend, f1_create]}}.

    `methods` is a list of (dir_name, display_label) pairs, e.g.
    ("magneto_llm", "Magneto-LLM").
    """
    data: dict[str, dict[str, list[float]]] = {}
    for dataset in datasets:
        data[dataset] = {}
        for method_dir, method_label in methods:
            rows = load_evaluated_rows(dataset, method_dir)
            data[dataset][method_label] = [
                decision_class_prf(rows, op_key)[2] for op_key, _ in OPERATIONS
            ]
    return data
