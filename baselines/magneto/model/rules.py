from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuleThresholds:
    insert_table_confidence: float = 0.80
    extend_table_confidence: float = 0.45
    column_match_confidence: float = 0.65
    insert_coverage: float = 1.00


def build_rule_result(
    *,
    incoming_schema: dict[str, Any],
    existing_schema: dict[str, Any],
    existing_constraints: dict[str, Any],
    matching_result: dict[str, Any],
    thresholds: RuleThresholds,
) -> dict[str, Any]:
    """Convert schema matches to an Evolutor-shaped result using only rules."""

    incoming_name, incoming_table = _single_table(incoming_schema)
    source_columns = list(incoming_table.get("columns", {}))
    table_matches = matching_result.get("table_matches", [])
    best = table_matches[0] if table_matches else None

    accepted_matches: dict[str, str] = {}
    if best:
        for source_column, candidates in best.get("column_matches", {}).items():
            if candidates and candidates[0].get("confidence", 0.0) >= thresholds.column_match_confidence:
                accepted_matches[source_column] = candidates[0]["target_column"]

    coverage = len(accepted_matches) / len(source_columns) if source_columns else 0.0
    table_confidence = best.get("confidence", 0.0) if best else 0.0

    if (
        best
        and table_confidence >= thresholds.insert_table_confidence
        and coverage >= thresholds.insert_coverage
    ):
        decision_type = "insert_table"
        target_table = best["target_table"]
    elif (
        best
        and table_confidence >= thresholds.extend_table_confidence
        and accepted_matches
    ):
        decision_type = "extend_table"
        target_table = best["target_table"]
    else:
        decision_type = "create_table"
        inferred_name = _infer_created_table_name(incoming_name, incoming_table)
        if (
            inferred_name in existing_schema.get("tables", {})
            and incoming_name not in existing_schema.get("tables", {})
        ):
            inferred_name = incoming_name
        target_table = _unique_table_name(
            inferred_name,
            existing_schema,
        )

    placements: dict[str, dict[str, Any]] = {}
    for source_column in source_columns:
        if decision_type == "create_table":
            target_column = source_column
        else:
            target_column = accepted_matches.get(source_column, source_column)
        placements[source_column] = {
            "source_column": source_column,
            "target_table": target_table,
            "target_column": target_column,
            "reason": "Deterministic mapping from Magneto match evidence.",
        }

    constraint_signals: list[dict[str, Any]] = []
    if decision_type == "create_table":
        constraint_signals.extend(
            infer_primary_key_constraint(
                table_name=target_table,
                incoming_table=incoming_table,
            )
        )
    if decision_type in {"create_table", "extend_table"}:
        new_columns = {
            name: schema
            for name, schema in incoming_table.get("columns", {}).items()
            if decision_type == "create_table" or name not in accepted_matches
        }
        constraint_signals.extend(
            infer_foreign_key_constraints(
                table_name=target_table,
                columns=new_columns,
                existing_constraints=existing_constraints,
            )
        )

    return {
        "decision": {
            "decision_type": decision_type,
            "target_table": target_table,
            "related_tables": [],
            "reason": (
                f"Rule decision: table_confidence={table_confidence:.3f}, "
                f"matched_coverage={coverage:.3f}."
            ),
        },
        "column_placements": placements,
        "constraint_signals": constraint_signals,
        "rule_evidence": {
            "selected_match": best,
            "accepted_column_matches": accepted_matches,
            "matched_coverage": coverage,
            "thresholds": thresholds.__dict__,
        },
    }


def infer_primary_key_constraint(
    *,
    table_name: str,
    incoming_table: dict[str, Any],
) -> list[dict[str, Any]]:
    columns = incoming_table.get("columns", {})
    signals: list[dict[str, Any]] = []
    pk_column = _infer_primary_key(table_name, columns)
    if pk_column:
        signals.append(
            {
                "constraint_type": "primary_key",
                "table": table_name,
                "columns": [pk_column],
                "reason": "Non-null table identifier inferred by rule.",
            }
        )

    return signals


def infer_foreign_key_constraints(
    *,
    table_name: str,
    columns: dict[str, dict[str, Any]],
    existing_constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    constraints = existing_constraints.get("constraints", existing_constraints)
    primary_keys = constraints.get("primary_keys", {})
    for source_column in columns:
        for referenced_table, referenced_columns in primary_keys.items():
            if [source_column] != referenced_columns:
                continue
            signals.append(
                {
                    "constraint_type": "foreign_key",
                    "table": table_name,
                    "columns": [source_column],
                    "referenced_table": referenced_table,
                    "referenced_columns": referenced_columns,
                    "reason": "Column exactly matches an existing primary key.",
                }
            )
            break
    return signals


def _infer_primary_key(
    table_name: str,
    columns: dict[str, dict[str, Any]],
) -> str | None:
    singular = _singularize(_normalize(table_name))
    preferred = {f"{singular}_id", f"{_normalize(table_name)}_id"}
    for column_name, schema in columns.items():
        if _normalize(column_name) in preferred and schema.get("nullable") is False:
            return column_name
    return None


def _unique_table_name(name: str, existing_schema: dict[str, Any]) -> str:
    existing = set(existing_schema.get("tables", {}))
    if name not in existing:
        return name
    suffix = 2
    while f"{name}_{suffix}" in existing:
        suffix += 1
    return f"{name}_{suffix}"


def _infer_created_table_name(
    incoming_name: str,
    incoming_table: dict[str, Any],
) -> str:
    """Prefer the most specific non-null identifier as the entity name."""

    identifier_stems = []
    for column_name, schema in incoming_table.get("columns", {}).items():
        normalized = _normalize(column_name)
        if normalized.endswith("_id") and schema.get("nullable") is False:
            identifier_stems.append(normalized[:-3])

    incoming_tokens = set(_normalize(incoming_name).split("_"))
    compatible_stems = [
        stem
        for stem in identifier_stems
        if set(stem.split("_")) & incoming_tokens
    ]
    if compatible_stems:
        return max(compatible_stems, key=lambda stem: (stem.count("_"), len(stem)))
    return incoming_name


def _single_table(schema: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    tables = schema.get("tables", {})
    if len(tables) != 1:
        raise ValueError(f"Exactly one incoming table is required, got {len(tables)}.")
    name = next(iter(tables))
    return name, tables[name]


def _normalize(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _singularize(value: str) -> str:
    if value.endswith("ies"):
        return value[:-3] + "y"
    if value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value
