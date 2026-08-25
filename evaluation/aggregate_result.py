from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any

# from evaluation.evaluator import summarize_dataset_results


# =====================================================
# Input configuration
# =====================================================

RESULT_FILES: list[str | Path] = [
    "outputs/Chinook/standard/small.csv",
    "outputs/Chinook/standard/medium.csv",
    "outputs/Chinook/standard/large.csv",
]


# Metrics shown as subcolumns under each size.
METRICS: list[str] = [
    "result_coverage",

    "decision_accuracy",
    "decision_macro_f1",

    "target_table_accuracy",

    "column_placement_micro_precision",
    "column_placement_micro_recall",
    "column_placement_micro_f1",
    "column_placement_macro_f1",

    "proposal_fact_micro_precision",
    "proposal_fact_micro_recall",
    "proposal_fact_micro_f1",
    "proposal_fact_macro_f1",

    "required_column_micro_coverage",
    "required_column_full_coverage_rate",

    "proposal_raw_valid_rate",
    "proposal_checked_valid_rate",

    "non_target_mean_preservation",
    "non_target_full_preservation_rate",

    "timing_end_to_end_seconds_mean",
]


OUTPUT_DIR = Path("outputs/summary")

DECIMALS = 4


# =====================================================
# File parsing and loading
# =====================================================

def parse_result_filename(
    path: str | Path,
) -> tuple[str, str, str, str]:
    """
    Parse either of these result path structures:

        method_dataset_size_times.csv
        <root>/<dataset>/<method>/<size>.csv
        <root>/<dataset>/<method>/<size>_<times>.csv

    A nested path without an explicit times suffix is treated
    as the first run (times="1").

    Returns:
        method
        dataset
        size
        times
    """
    path = Path(path)

    flat_parts = path.stem.rsplit("_", 3)

    if len(flat_parts) == 4:
        method, dataset, size, times = flat_parts
    elif len(path.parts) >= 4:
        method = path.parent.name
        dataset = path.parent.parent.name

        size_times_match = re.fullmatch(
            r"(.+)_([0-9]+)",
            path.stem,
        )

        if size_times_match:
            size, times = size_times_match.groups()
        else:
            size = path.stem
            times = "1"
    else:
        raise ValueError(
            "Result path must follow either "
            "'method_dataset_size_times.csv' or "
            "'<root>/<dataset>/<method>/<size>.csv': "
            f"{path.name}"
        )

    if not method:
        raise ValueError(
            f"Missing method in filename: {path.name}"
        )

    if not dataset:
        raise ValueError(
            f"Missing dataset in filename: {path.name}"
        )

    if not size:
        raise ValueError(
            f"Missing size in filename: {path.name}"
        )

    if not times:
        raise ValueError(
            f"Missing times in filename: {path.name}"
        )

    return method, dataset, size, times


def load_result_rows(
    path: str | Path,
) -> list[dict[str, Any]]:
    """
    Load one case-level evaluation CSV.

    Each row represents one benchmark case.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Result file does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    if not rows:
        raise ValueError(
            f"Result CSV contains no rows: {path}"
        )

    return rows


# =====================================================
# CSV value conversion
# =====================================================

def _convert_csv_value(
    value: Any,
) -> Any:
    """
    Convert CSV strings back into bool/int/float values
    expected by summarize_dataset_results().
    """
    if not isinstance(value, str):
        return value

    stripped = value.strip()

    if stripped == "":
        return None

    if stripped == "True":
        return True

    if stripped == "False":
        return False

    if stripped == "None":
        return None

    try:
        return int(stripped)
    except ValueError:
        pass

    try:
        return float(stripped)
    except ValueError:
        return value


def convert_result_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert numeric and boolean CSV values back into
    Python values.
    """
    return [
        {
            key: _convert_csv_value(value)
            for key, value in row.items()
        }
        for row in rows
    ]


# =====================================================
# Statistics
# =====================================================

def _natural_sort_key(
    value: str,
) -> list[Any]:
    """
    Sort:
        size_2 before size_10
    """
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    ]


def format_metric_values(
    values: list[float],
    decimals: int = 4,
) -> str:
    """
    Format repeated experiment results.

    One result:
        0.8123

    Multiple results:
        0.8123 ± 0.0245
    """
    if not values:
        return ""

    if len(values) == 1:
        return f"{values[0]:.{decimals}f}"

    return (
        f"{mean(values):.{decimals}f}"
        f" ± "
        f"{stdev(values):.{decimals}f}"
    )


def get_metric_value(
    summary: dict[str, Any],
    metric_name: str,
) -> float | None:
    value = summary.get(metric_name)

    if value is None:
        return None

    if isinstance(value, bool):
        return float(value)

    if isinstance(value, (int, float)):
        return float(value)

    raise TypeError(
        f"Metric '{metric_name}' is not numeric: "
        f"{value!r}"
    )


# =====================================================
# Run-level summaries
# =====================================================

def summarize_result_file(
    path: str | Path,
) -> dict[str, Any]:
    """
    Convert one case-level result CSV into one run-level
    summary.

    This reuses summarize_dataset_results() from evaluator.py.
    """
    raw_rows = load_result_rows(path)
    converted_rows = convert_result_rows(raw_rows)

    return summarize_dataset_results(
        converted_rows
    )


def collect_run_data(
    result_files: list[str | Path],
) -> dict[
    str,
    dict[
        str,
        dict[
            str,
            dict[
                str,
                dict[str, Any],
            ],
        ],
    ],
]:
    """
    Output structure:

        data[dataset][method][size][times] = {
            "rows": [...],
            "summary": {...},
            "path": ...
        }
    """
    data: dict[
        str,
        dict[
            str,
            dict[
                str,
                dict[
                    str,
                    dict[str, Any],
                ],
            ],
        ],
    ] = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(dict)
        )
    )

    for result_file in result_files:
        method, dataset, size, times = (
            parse_result_filename(result_file)
        )

        if times in data[dataset][method][size]:
            raise ValueError(
                "Duplicate result for "
                f"method={method}, "
                f"dataset={dataset}, "
                f"size={size}, "
                f"times={times}"
            )

        raw_rows = load_result_rows(result_file)
        rows = convert_result_rows(raw_rows)

        summary = summarize_dataset_results(rows)

        data[dataset][method][size][times] = {
            "path": str(result_file),
            "rows": rows,
            "summary": summary,
        }

    return data


# =====================================================
# Size-level and total aggregation
# =====================================================

def collect_size_metric_values(
    size_runs: dict[
        str,
        dict[str, Any],
    ],
    metric_name: str,
) -> list[float]:
    """
    Collect one metric across repeated times for one
    method/dataset/size.
    """
    values: list[float] = []

    for run_data in size_runs.values():
        value = get_metric_value(
            summary=run_data["summary"],
            metric_name=metric_name,
        )

        if value is not None:
            values.append(value)

    return values


def build_total_run_summaries(
    method_data: dict[
        str,
        dict[
            str,
            dict[str, Any],
        ],
    ],
) -> dict[str, dict[str, Any]]:
    """
    Build total summaries per times.

    For one method and dataset:

        small_1 + large_1 -> total run 1
        small_2 + large_2 -> total run 2

    Each total run is calculated by concatenating all
    case-level rows from every size with the same times.
    """
    rows_by_times: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for size_runs in method_data.values():
        for times, run_data in size_runs.items():
            rows_by_times[times].extend(
                run_data["rows"]
            )

    total_summaries: dict[
        str,
        dict[str, Any],
    ] = {}

    for times, rows in rows_by_times.items():
        total_summaries[times] = (
            summarize_dataset_results(rows)
        )

    return total_summaries


def collect_total_metric_values(
    total_summaries: dict[
        str,
        dict[str, Any],
    ],
    metric_name: str,
) -> list[float]:
    values: list[float] = []

    for summary in total_summaries.values():
        value = get_metric_value(
            summary=summary,
            metric_name=metric_name,
        )

        if value is not None:
            values.append(value)

    return values



# =====================================================
# Summarize Total file
# =====================================================
def _safe_divide(
    numerator: int | float,
    denominator: int | float,
) -> float:
    if denominator == 0:
        return 0.0

    return numerator / denominator


def _mean(
    values: list[float],
) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)


def _aggregate_prf(
    rows: list[dict[str, Any]],
    prefix: str,
) -> dict[str, Any]:
    """
    Aggregate case-level TP/FP/FN into dataset-level
    micro and macro metrics.
    """
    total_tp = sum(
        int(row.get(f"{prefix}_true_positive") or 0)
        for row in rows
    )

    total_fp = sum(
        int(row.get(f"{prefix}_false_positive") or 0)
        for row in rows
    )

    total_fn = sum(
        int(row.get(f"{prefix}_false_negative") or 0)
        for row in rows
    )

    micro_precision = _safe_divide(
        total_tp,
        total_tp + total_fp,
    )

    micro_recall = _safe_divide(
        total_tp,
        total_tp + total_fn,
    )

    micro_f1 = _safe_divide(
        2 * micro_precision * micro_recall,
        micro_precision + micro_recall,
    )

    precision_values = [
        float(row[f"{prefix}_precision"])
        for row in rows
        if row.get(f"{prefix}_precision") is not None
    ]

    recall_values = [
        float(row[f"{prefix}_recall"])
        for row in rows
        if row.get(f"{prefix}_recall") is not None
    ]

    f1_values = [
        float(row[f"{prefix}_f1"])
        for row in rows
        if row.get(f"{prefix}_f1") is not None
    ]

    return {
        f"{prefix}_micro_precision": micro_precision,
        f"{prefix}_micro_recall": micro_recall,
        f"{prefix}_micro_f1": micro_f1,
        f"{prefix}_macro_precision": _mean(
            precision_values
        ),
        f"{prefix}_macro_recall": _mean(
            recall_values
        ),
        f"{prefix}_macro_f1": _mean(
            f1_values
        ),
    }


def summarize_dataset_results(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Summarize all case-level rows from one experiment.

    Input:
        rows from one result CSV.

    Output:
        one dataset-level summary dictionary.
    """
    evaluated_rows = [
        row
        for row in rows
        if row.get("evaluation_status") == "evaluated"
    ]

    total_case_count = len(rows)
    evaluated_case_count = len(evaluated_rows)

    summary: dict[str, Any] = {
        "total_case_count": total_case_count,
        "evaluated_case_count": evaluated_case_count,
        "missing_result_count": sum(
            row.get("evaluation_status")
            == "missing_result"
            for row in rows
        ),
        "result_load_failed_count": sum(
            row.get("evaluation_status")
            == "result_load_failed"
            for row in rows
        ),
        "result_coverage": _safe_divide(
            evaluated_case_count,
            total_case_count,
        ),
    }

    if not evaluated_rows:
        return summary

    # -------------------------------------------------
    # Decision
    # -------------------------------------------------

    decision_correct_count = sum(
        bool(row.get("decision_correct"))
        for row in evaluated_rows
    )

    summary["decision_accuracy"] = _safe_divide(
        decision_correct_count,
        evaluated_case_count,
    )

    reference_decisions = [
        str(row["decision_reference"])
        for row in evaluated_rows
    ]

    predicted_decisions = [
        str(row["decision_predicted"])
        for row in evaluated_rows
    ]

    decision_classes = sorted(
        set(reference_decisions)
        | set(predicted_decisions)
    )

    class_f1_values: list[float] = []

    for decision_class in decision_classes:
        tp = sum(
            reference == decision_class
            and predicted == decision_class
            for reference, predicted in zip(
                reference_decisions,
                predicted_decisions,
            )
        )

        fp = sum(
            reference != decision_class
            and predicted == decision_class
            for reference, predicted in zip(
                reference_decisions,
                predicted_decisions,
            )
        )

        fn = sum(
            reference == decision_class
            and predicted != decision_class
            for reference, predicted in zip(
                reference_decisions,
                predicted_decisions,
            )
        )

        precision = _safe_divide(
            tp,
            tp + fp,
        )

        recall = _safe_divide(
            tp,
            tp + fn,
        )

        f1 = _safe_divide(
            2 * precision * recall,
            precision + recall,
        )

        class_f1_values.append(f1)

        prefix = f"decision_{decision_class}"

        summary[f"{prefix}_precision"] = precision
        summary[f"{prefix}_recall"] = recall
        summary[f"{prefix}_f1"] = f1

    summary["decision_macro_f1"] = _mean(
        class_f1_values
    )

    # -------------------------------------------------
    # Target table
    # -------------------------------------------------

    target_rows = [
        row
        for row in evaluated_rows
        if row.get("target_table_applicable") is True
    ]

    target_correct_count = sum(
        bool(row.get("target_table_correct"))
        for row in target_rows
    )

    summary["target_table_accuracy"] = _safe_divide(
        target_correct_count,
        len(target_rows),
    )

    # -------------------------------------------------
    # Column placement
    # -------------------------------------------------

    summary.update(
        _aggregate_prf(
            rows=evaluated_rows,
            prefix="column_placement",
        )
    )

    # -------------------------------------------------
    # Proposal facts
    # -------------------------------------------------

    summary.update(
        _aggregate_prf(
            rows=evaluated_rows,
            prefix="proposal_fact",
        )
    )

    # -------------------------------------------------
    # Required column coverage
    # -------------------------------------------------

    required_count = sum(
        int(
            row.get(
                "required_column_coverage_required_count"
            )
            or 0
        )
        for row in evaluated_rows
    )

    covered_count = sum(
        int(
            row.get(
                "required_column_coverage_covered_count"
            )
            or 0
        )
        for row in evaluated_rows
    )

    full_coverage_count = sum(
        bool(
            row.get(
                "required_column_coverage_full_coverage"
            )
        )
        for row in evaluated_rows
    )

    summary["required_column_micro_coverage"] = (
        _safe_divide(
            covered_count,
            required_count,
        )
    )

    summary["required_column_mean_coverage"] = _mean(
        [
            float(
                row.get(
                    "required_column_coverage_coverage"
                )
                or 0.0
            )
            for row in evaluated_rows
        ]
    )

    summary[
        "required_column_full_coverage_rate"
    ] = _safe_divide(
        full_coverage_count,
        evaluated_case_count,
    )

    # -------------------------------------------------
    # Proposal validity
    # -------------------------------------------------

    raw_valid_count = sum(
        bool(row.get("proposal_validity_raw_valid"))
        for row in evaluated_rows
    )

    checked_valid_count = sum(
        bool(
            row.get(
                "proposal_validity_checked_valid"
            )
        )
        for row in evaluated_rows
    )

    summary["proposal_raw_valid_rate"] = (
        _safe_divide(
            raw_valid_count,
            evaluated_case_count,
        )
    )

    summary["proposal_checked_valid_rate"] = (
        _safe_divide(
            checked_valid_count,
            evaluated_case_count,
        )
    )

    summary[
        "proposal_invalid_reference_count"
    ] = sum(
        int(
            row.get(
                "proposal_validity_invalid_reference_count"
            )
            or 0
        )
        for row in evaluated_rows
    )

    summary["proposal_broken_fk_count"] = sum(
        int(
            row.get(
                "proposal_validity_broken_fk_count"
            )
            or 0
        )
        for row in evaluated_rows
    )

    summary[
        "proposal_duplicate_definition_count"
    ] = sum(
        int(
            row.get(
                "proposal_validity_"
                "duplicate_definition_count"
            )
            or 0
        )
        for row in evaluated_rows
    )

    summary[
        "proposal_conflicting_operation_count"
    ] = sum(
        int(
            row.get(
                "proposal_validity_"
                "conflicting_operation_count"
            )
            or 0
        )
        for row in evaluated_rows
    )

    # -------------------------------------------------
    # Non-target preservation
    # -------------------------------------------------

    preservation_rows = [
        row
        for row in evaluated_rows
        if row.get(
            "non_target_preservation_applicable"
        ) is True
    ]

    preservation_scores = [
        float(
            row.get(
                "non_target_preservation_score"
            )
            or 0.0
        )
        for row in preservation_rows
    ]

    summary["non_target_mean_preservation"] = (
        _mean(preservation_scores)
    )

    full_preservation_count = sum(
        score == 1.0
        for score in preservation_scores
    )

    summary[
        "non_target_full_preservation_rate"
    ] = _safe_divide(
        full_preservation_count,
        len(preservation_rows),
    )

    summary[
        "non_target_unexpected_table_modification_count"
    ] = sum(
        int(
            row.get(
                "non_target_preservation_"
                "unexpected_table_modification_count"
            )
            or 0
        )
        for row in preservation_rows
    )

    summary[
        "non_target_unexpected_column_modification_count"
    ] = sum(
        int(
            row.get(
                "non_target_preservation_"
                "unexpected_column_modification_count"
            )
            or 0
        )
        for row in preservation_rows
    )

    summary[
        "non_target_unexpected_fk_attachment_count"
    ] = sum(
        int(
            row.get(
                "non_target_preservation_"
                "unexpected_fk_attachment_count"
            )
            or 0
        )
        for row in preservation_rows
    )

    timing_keys = sorted(
        {
            key
            for row in evaluated_rows
            for key in row
            if key.startswith("timing_")
            and (
                key.endswith("_seconds")
                or key.endswith("_call_count")
            )
        }
    )

    for key in timing_keys:
        values = [
            float(row[key])
            for row in evaluated_rows
            if row.get(key) not in {None, ""}
        ]
        if not values:
            continue
        summary[f"{key}_mean"] = mean(values)
        summary[f"{key}_stdev"] = (
            stdev(values) if len(values) > 1 else 0.0
        )

    return summary
# =====================================================
# Dataset summary CSV
# =====================================================

def write_dataset_summary(
    dataset: str,
    dataset_data: dict[
        str,
        dict[
            str,
            dict[
                str,
                dict[str, Any],
            ],
        ],
    ],
    metrics: list[str],
    output_path: str | Path,
    decimals: int = 4,
) -> None:
    """
    Create one summary CSV for one dataset.

    Header structure:

        method
        size_1
            metric_a
            metric_b
        size_2
            metric_a
            metric_b
        total
            metric_a
            metric_b
    """
    methods = sorted(
        dataset_data,
        key=_natural_sort_key,
    )

    sizes = sorted(
        {
            size
            for method_data in dataset_data.values()
            for size in method_data
        },
        key=_natural_sort_key,
    )

    first_header = ["method"]
    second_header = [""]

    for size in sizes:
        first_header.extend(
            [size] * len(metrics)
        )
        second_header.extend(metrics)

    first_header.extend(
        ["total"] * len(metrics)
    )
    second_header.extend(metrics)

    output_rows: list[list[str]] = [
        first_header,
        second_header,
    ]

    for method in methods:
        method_data = dataset_data[method]
        row: list[str] = [method]

        # ---------------------------------------------
        # Each size
        # ---------------------------------------------

        for size in sizes:
            size_runs = method_data.get(
                size,
                {},
            )

            for metric_name in metrics:
                values = collect_size_metric_values(
                    size_runs=size_runs,
                    metric_name=metric_name,
                )

                row.append(
                    format_metric_values(
                        values=values,
                        decimals=decimals,
                    )
                )

        # ---------------------------------------------
        # Total across sizes, grouped by times
        # ---------------------------------------------

        total_summaries = build_total_run_summaries(
            method_data
        )

        for metric_name in metrics:
            values = collect_total_metric_values(
                total_summaries=total_summaries,
                metric_name=metric_name,
            )

            row.append(
                format_metric_values(
                    values=values,
                    decimals=decimals,
                )
            )

        output_rows.append(row)

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # CSV
    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.writer(file)
        writer.writerows(output_rows)

    # Markdown
    markdown_output_path = (
        output_path.with_suffix(".md")
    )

    write_markdown_table(
        dataset=dataset,
        output_rows=output_rows,
        output_path=markdown_output_path,
    )

    # LaTeX
    latex_output_path = (
        output_path.with_suffix(".tex")
    )

    write_latex_table(
        dataset=dataset,
        output_rows=output_rows,
        sizes=sizes,
        metrics=metrics,
        output_path=latex_output_path,
    )


def aggregate_result_files(
    result_files: list[str | Path],
    metrics: list[str],
    output_dir: str | Path,
    decimals: int = 4,
) -> None:
    """
    Generate one summary CSV for each dataset.
    """
    output_dir = Path(output_dir)

    all_data = collect_run_data(
        result_files
    )

    for dataset, dataset_data in all_data.items():
        output_path = (
            output_dir
            / f"{dataset}_summary.csv"
        )

        write_dataset_summary(
            dataset=dataset,
            dataset_data=dataset_data,
            metrics=metrics,
            output_path=output_path,
            decimals=decimals,
        )

        print(
            f"[Saved] {dataset}: {output_path}"
        )


def _escape_markdown(
    value: Any,
) -> str:
    return (
        str(value)
        .replace("|", r"\|")
        .replace("\n", "<br>")
    )


def write_markdown_table(
    dataset: str,
    output_rows: list[list[str]],
    output_path: str | Path,
) -> None:
    """
    Write the dataset summary as a Markdown table.

    Since Markdown does not support merged headers, the
    two CSV headers are flattened into:

        size / metric
    """
    if len(output_rows) < 2:
        raise ValueError(
            "output_rows must contain two header rows."
        )

    dataset_header = output_rows[0]
    metric_header = output_rows[1]
    data_rows = output_rows[2:]

    headers = ["method"]

    for index in range(1, len(dataset_header)):
        headers.append(
            f"{dataset_header[index]} / "
            f"{metric_header[index]}"
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines: list[str] = [
        f"# {dataset} Summary",
        "",
        "| "
        + " | ".join(
            _escape_markdown(value)
            for value in headers
        )
        + " |",
        "| "
        + " | ".join(
            "---"
            for _ in headers
        )
        + " |",
    ]

    for row in data_rows:
        lines.append(
            "| "
            + " | ".join(
                _escape_markdown(value)
                for value in row
            )
            + " |"
        )

    output_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _escape_latex(
    value: Any,
) -> str:
    text = str(value)

    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }

    return "".join(
        replacements.get(character, character)
        for character in text
    )


def _format_latex_metric_cell(
    value: Any,
) -> str:
    """
    Convert:
        0.8123 ± 0.0245

    into:
        $0.8123 \\pm 0.0245$
    """
    if value is None:
        return ""

    text = str(value).strip()

    if not text:
        return ""

    if " ± " in text:
        mean_value, std_value = text.split(
            " ± ",
            maxsplit=1,
        )

        return (
            f"${_escape_latex(mean_value)} "
            f"\\pm {_escape_latex(std_value)}$"
        )

    try:
        float(text)
        return f"${text}$"
    except ValueError:
        return _escape_latex(text)


def write_latex_table(
    dataset: str,
    output_rows: list[list[str]],
    sizes: list[str],
    metrics: list[str],
    output_path: str | Path,
) -> None:
    """
    Write a complete LaTeX table with grouped size headers.

    Requires:
        \\usepackage{booktabs}
        \\usepackage{graphicx}
    """
    if len(output_rows) < 2:
        raise ValueError(
            "output_rows must contain two header rows."
        )

    data_rows = output_rows[2:]
    column_groups = sizes + ["total"]

    metric_count = len(metrics)
    value_column_count = (
        len(column_groups) * metric_count
    )

    column_format = (
        "l"
        + "c" * value_column_count
    )

    first_header_cells = ["Method"]

    for group_name in column_groups:
        first_header_cells.append(
            f"\\multicolumn{{{metric_count}}}"
            f"{{c}}{{{_escape_latex(group_name)}}}"
        )

    second_header_cells = [""]

    for _ in column_groups:
        second_header_cells.extend(
            _escape_latex(metric_name)
            for metric_name in metrics
        )

    cmidrules: list[str] = []
    start_column = 2

    for _ in column_groups:
        end_column = (
            start_column + metric_count - 1
        )

        cmidrules.append(
            f"\\cmidrule(lr)"
            f"{{{start_column}-{end_column}}}"
        )

        start_column = end_column + 1

    latex_lines: list[str] = [
        "% Requires \\usepackage{booktabs}",
        "% Requires \\usepackage{graphicx}",
        "\\begin{table}[htbp]",
        "\\centering",
        f"\\caption{{{_escape_latex(dataset)} summary}}",
        f"\\label{{tab:{_escape_latex(dataset.lower())}_summary}}",
        "\\resizebox{\\textwidth}{!}{%",
        f"\\begin{{tabular}}{{{column_format}}}",
        "\\toprule",
        " & ".join(first_header_cells) + r" \\",
        " ".join(cmidrules),
        " & ".join(second_header_cells) + r" \\",
        "\\midrule",
    ]

    for row in data_rows:
        method = _escape_latex(row[0])

        metric_cells = [
            _format_latex_metric_cell(value)
            for value in row[1:]
        ]

        latex_lines.append(
            " & ".join(
                [method, *metric_cells]
            )
            + r" \\"
        )

    latex_lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}%",
            "}",
            "\\end{table}",
            "",
        ]
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        "\n".join(latex_lines),
        encoding="utf-8",
    )


def main() -> None:
    aggregate_result_files(
        result_files=RESULT_FILES,
        metrics=METRICS,
        output_dir=OUTPUT_DIR,
        decimals=DECIMALS,
    )


if __name__ == "__main__":
    main()
