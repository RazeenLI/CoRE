from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OperationThresholds:
    column_match_confidence: float = 0.70
    insert_table_confidence: float = 0.70
    extend_table_confidence: float = 0.35
    insert_coverage: float = 1.00


def build_rule_result(
    *,
    matcher_name: str,
    incoming_schema: dict[str, Any],
    existing_schema: dict[str, Any],
    existing_constraints: dict[str, Any],
    matching_result: dict[str, Any],
    thresholds: OperationThresholds,
) -> dict[str, Any]:
    incoming_name, incoming_table = extract_single_table(incoming_schema)
    source_columns = list(incoming_table.get("columns", {}))
    best = next(iter(matching_result.get("table_matches", [])), None)
    accepted: dict[str, str] = {}
    if best:
        for source_column, candidates in best.get("column_matches", {}).items():
            if candidates and candidates[0]["confidence"] >= thresholds.column_match_confidence:
                accepted[source_column] = candidates[0]["target_column"]

    coverage = len(accepted) / len(source_columns) if source_columns else 0.0
    table_confidence = best.get("confidence", 0.0) if best else 0.0
    key_compatible = bool(best) and keys_compatible(
        incoming_name=incoming_name,
        incoming_table=incoming_table,
        target_table=best["target_table"],
        accepted_matches=accepted,
        existing_constraints=existing_constraints,
    )

    if (
        best
        and key_compatible
        and table_confidence >= thresholds.insert_table_confidence
        and coverage >= thresholds.insert_coverage
    ):
        decision_type = "insert_table"
        target_table = best["target_table"]
    elif (
        best
        and key_compatible
        and table_confidence >= thresholds.extend_table_confidence
        and accepted
    ):
        decision_type = "extend_table"
        target_table = best["target_table"]
    else:
        decision_type = "create_table"
        inferred_name = infer_created_table_name(incoming_name, incoming_table)
        if (
            inferred_name in existing_schema.get("tables", {})
            and incoming_name not in existing_schema.get("tables", {})
        ):
            inferred_name = incoming_name
        target_table = unique_table_name(inferred_name, existing_schema)

    placements = {
        source_column: {
            "source_column": source_column,
            "target_table": target_table,
            "target_column": (
                source_column
                if decision_type == "create_table"
                else accepted.get(source_column, source_column)
            ),
            "reason": f"Deterministic placement from {matcher_name.upper()} evidence.",
        }
        for source_column in source_columns
    }

    constraint_signals: list[dict[str, Any]] = []
    if decision_type == "create_table":
        constraint_signals.extend(
            infer_primary_key_constraint(target_table, incoming_table)
        )
    if decision_type in {"create_table", "extend_table"}:
        new_columns = {
            name: schema
            for name, schema in incoming_table.get("columns", {}).items()
            if decision_type == "create_table" or name not in accepted
        }
        constraint_signals.extend(
            infer_foreign_key_constraints(
                target_table,
                new_columns,
                existing_constraints,
            )
        )

    return {
        "decision": {
            "decision_type": decision_type,
            "target_table": target_table,
            "related_tables": [],
            "reason": (
                f"{matcher_name.upper()} rules: table_confidence={table_confidence:.3f}, "
                f"coverage={coverage:.3f}, key_compatible={key_compatible}."
            ),
        },
        "column_placements": placements,
        "constraint_signals": constraint_signals,
        "rule_evidence": {
            "matcher": matcher_name,
            "selected_match": best,
            "accepted_column_matches": accepted,
            "matched_coverage": coverage,
            "key_compatible": key_compatible,
            "thresholds": thresholds.__dict__,
        },
    }


def keys_compatible(
    *,
    incoming_name: str,
    incoming_table: dict[str, Any],
    target_table: str,
    accepted_matches: dict[str, str],
    existing_constraints: dict[str, Any],
) -> bool:
    source_key = infer_primary_key(incoming_name, incoming_table.get("columns", {}))
    constraints = existing_constraints.get("constraints", existing_constraints)
    target_key = constraints.get("primary_keys", {}).get(target_table, [])
    if source_key and target_key:
        return accepted_matches.get(source_key) in target_key
    # When key metadata is unavailable, exact normalized table names provide a
    # conservative fallback; general field overlap is not enough.
    return normalize_name(incoming_name) == normalize_name(target_table)


def infer_primary_key_constraint(
    table_name: str,
    incoming_table: dict[str, Any],
) -> list[dict[str, Any]]:
    column = infer_primary_key(table_name, incoming_table.get("columns", {}))
    if not column:
        return []
    return [{
        "constraint_type": "primary_key",
        "table": table_name,
        "columns": [column],
        "reason": "Non-null table identifier inferred by rule.",
    }]


def infer_foreign_key_constraints(
    table_name: str,
    columns: dict[str, dict[str, Any]],
    existing_constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    constraints = existing_constraints.get("constraints", existing_constraints)
    signals = []
    for source_column in columns:
        for referenced_table, referenced_columns in constraints.get("primary_keys", {}).items():
            if [source_column] == referenced_columns:
                signals.append({
                    "constraint_type": "foreign_key",
                    "table": table_name,
                    "columns": [source_column],
                    "referenced_table": referenced_table,
                    "referenced_columns": referenced_columns,
                    "reason": "Column exactly matches an existing primary key.",
                })
                break
    return signals


def infer_primary_key(
    table_name: str,
    columns: dict[str, dict[str, Any]],
) -> str | None:
    normalized_table = normalize_name(table_name)
    singular = singularize(normalized_table)
    preferred = {f"{normalized_table}_id", f"{singular}_id"}
    for column_name, schema in columns.items():
        if normalize_name(column_name) in preferred and schema.get("nullable") is False:
            return column_name
    return None


def infer_created_table_name(
    incoming_name: str,
    incoming_table: dict[str, Any],
) -> str:
    stems = []
    for column_name, schema in incoming_table.get("columns", {}).items():
        normalized = normalize_name(column_name)
        if normalized.endswith("_id") and schema.get("nullable") is False:
            stems.append(normalized[:-3])
    incoming_tokens = set(normalize_name(incoming_name).split("_"))
    compatible = [stem for stem in stems if set(stem.split("_")) & incoming_tokens]
    return max(compatible, key=lambda stem: (stem.count("_"), len(stem))) if compatible else incoming_name


def unique_table_name(name: str, existing_schema: dict[str, Any]) -> str:
    existing = set(existing_schema.get("tables", {}))
    if name not in existing:
        return name
    suffix = 2
    while f"{name}_{suffix}" in existing:
        suffix += 1
    return f"{name}_{suffix}"


def extract_single_table(schema: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    tables = schema.get("tables", {})
    if len(tables) != 1:
        raise ValueError(f"Exactly one incoming table is required, got {len(tables)}.")
    name = next(iter(tables))
    return name, tables[name]


def normalize_name(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def singularize(value: str) -> str:
    if value.endswith("ies"):
        return value[:-3] + "y"
    if value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value
