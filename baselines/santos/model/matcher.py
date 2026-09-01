from __future__ import annotations

import re
from itertools import combinations
from typing import Any

from baselines.discovery.model.common import (
    extract_single_table,
    matches_from_scores,
    maximum_weight_pairs,
)
from model.utils.io import terminal_message


class SantosMatcher:
    """Modern-Pandas port of SANTOS's synthesized-KB matching path.

    Existing table values form the synthesized column and relationship
    indexes. The incoming table is then scored against those indexes. No
    benchmark-wide index is reused, so construction time belongs to the case.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.assignment_threshold = float(config.get("assignment_threshold", 0.20))
        self.relationship_weight = float(config.get("relationship_weight", 0.25))

    def __call__(
        self,
        *,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
        existing_schema: dict[str, Any],
        existing_values: dict[str, list[dict[str, Any]]],
        existing_profiles: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del existing_profiles
        incoming_name, incoming_table = extract_single_table(incoming_schema)
        source_columns = list(incoming_table.get("columns", {}))
        source_value_sets = column_value_sets(incoming_values, source_columns)
        source_pair_sets = relationship_value_sets(incoming_values, source_columns)

        table_matches = []
        for target_table, target_schema in existing_schema.get("tables", {}).items():
            target_columns = list(target_schema.get("columns", {}))
            target_rows = existing_values.get(target_table, [])
            target_value_sets = column_value_sets(target_rows, target_columns)
            target_pair_sets = relationship_value_sets(target_rows, target_columns)
            scores = [
                [containment(source_value_sets[src], target_value_sets[tgt]) for tgt in target_columns]
                for src in source_columns
            ]
            assignment = maximum_weight_pairs(scores)
            column_score = (
                sum(score for _, _, score in assignment) / len(source_columns)
                if source_columns else 0.0
            )
            relationship_score = aligned_relationship_score(
                assignment=assignment,
                source_pair_sets=source_pair_sets,
                target_pair_sets=target_pair_sets,
            )
            combined_score = (
                (1.0 - self.relationship_weight) * column_score
                + self.relationship_weight * relationship_score
            )
            table_matches.append(matches_from_scores(
                target_table=target_table,
                source_columns=source_columns,
                target_columns=target_columns,
                incoming_table=incoming_table,
                target_schema=target_schema,
                scores=scores,
                assignment_threshold=self.assignment_threshold,
                table_score=combined_score,
                reason="SANTOS synthesized-KB column-semantic overlap.",
            ))
        table_matches.sort(key=lambda item: (-item["confidence"], item["target_table"]))
        terminal_message(
            "success",
            f"SANTOS built a case-local synthesized KB and matched '{incoming_name}' "
            f"against {len(table_matches)} existing tables.",
            "\t",
        )
        return {
            "matcher": "santos",
            "index_scope": "current_case_existing_rdb",
            "table_matches": table_matches,
        }


def normalize_value(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()
    if not text or text in {"nan", "none", "null", "unknown"}:
        return None
    return " ".join(text.split())


def column_value_sets(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, set[str]]:
    result = {column: set() for column in columns}
    for row in rows:
        for column in columns:
            value = normalize_value(row.get(column))
            if value is not None:
                result[column].add(value)
    return result


def relationship_value_sets(
    rows: list[dict[str, Any]], columns: list[str]
) -> dict[tuple[int, int], set[tuple[str, str]]]:
    result: dict[tuple[int, int], set[tuple[str, str]]] = {}
    for left, right in combinations(range(len(columns)), 2):
        pairs = set()
        for row in rows:
            left_value = normalize_value(row.get(columns[left]))
            right_value = normalize_value(row.get(columns[right]))
            if left_value is not None and right_value is not None:
                pairs.add((left_value, right_value))
        result[(left, right)] = pairs
    return result


def containment(source: set[Any], target: set[Any]) -> float:
    if not source or not target:
        return 0.0
    return len(source & target) / len(source)


def aligned_relationship_score(
    *,
    assignment: list[tuple[int, int, float]],
    source_pair_sets: dict[tuple[int, int], set[tuple[str, str]]],
    target_pair_sets: dict[tuple[int, int], set[tuple[str, str]]],
) -> float:
    mapping = {source: target for source, target, score in assignment if score > 0.0}
    scores = []
    for (source_left, source_right), source_pairs in source_pair_sets.items():
        if source_left not in mapping or source_right not in mapping:
            continue
        target_left, target_right = mapping[source_left], mapping[source_right]
        reverse = target_left > target_right
        target_key = tuple(sorted((target_left, target_right)))
        target_pairs = target_pair_sets.get(target_key, set())
        if reverse:
            target_pairs = {(right, left) for left, right in target_pairs}
        if source_pairs and target_pairs:
            scores.append(containment(source_pairs, target_pairs))
    return sum(scores) / len(scores) if scores else 0.0
