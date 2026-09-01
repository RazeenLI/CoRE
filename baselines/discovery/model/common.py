from __future__ import annotations

from typing import Any

from baselines.traditional.model.matcher import build_table_match, types_compatible


def extract_single_table(schema: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    tables = schema.get("tables", {})
    if len(tables) != 1:
        raise ValueError(f"Exactly one incoming table is required, got {len(tables)}.")
    name = next(iter(tables))
    return name, tables[name]


def cosine_similarity(left: Any, right: Any) -> float:
    import numpy as np

    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator == 0.0:
        return 0.0
    return max(0.0, min(1.0, float(np.dot(left, right) / denominator)))


def maximum_weight_pairs(scores: list[list[float]]) -> list[tuple[int, int, float]]:
    """Return the maximum-weight rectangular assignment used by both papers."""

    if not scores or not scores[0]:
        return []
    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment
    except ImportError as exc:
        raise ImportError(
            "Discovery baselines require NumPy and SciPy from the experiment environment."
        ) from exc
    matrix = np.asarray(scores, dtype=float)
    rows, columns = linear_sum_assignment(matrix, maximize=True)
    return [(int(row), int(column), float(matrix[row, column])) for row, column in zip(rows, columns)]


def matches_from_scores(
    *,
    target_table: str,
    source_columns: list[str],
    target_columns: list[str],
    incoming_table: dict[str, Any],
    target_schema: dict[str, Any],
    scores: list[list[float]],
    assignment_threshold: float,
    reason: str,
    table_score: float | None = None,
) -> dict[str, Any]:
    column_matches = {column: [] for column in source_columns}
    for source_index, target_index, score in maximum_weight_pairs(scores):
        source_column = source_columns[source_index]
        target_column = target_columns[target_index]
        if score < assignment_threshold:
            continue
        if not types_compatible(
            incoming_table["columns"][source_column].get("type"),
            target_schema["columns"][target_column].get("type"),
        ):
            continue
        column_matches[source_column].append({
            "target_column": target_column,
            "confidence": score,
            "reason": reason,
        })
    result = build_table_match(
        target_table=target_table,
        source_columns=source_columns,
        column_matches=column_matches,
    )
    if table_score is not None:
        result["confidence"] = max(0.0, min(1.0, table_score))
    return result
