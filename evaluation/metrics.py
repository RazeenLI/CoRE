from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv
from typing import Any


def compute_fact_set_metrics(
    predicted_facts: set[tuple[Any, ...]],
    reference_facts: set[tuple[Any, ...]],
) -> dict[str, Any]:
    """Return PRF and exact match for two sets of normalized facts."""
    true_positive_items = predicted_facts & reference_facts
    false_positive_items = predicted_facts - reference_facts
    false_negative_items = reference_facts - predicted_facts
    true_positive = len(true_positive_items)
    false_positive = len(false_positive_items)
    false_negative = len(false_negative_items)

    if not predicted_facts and not reference_facts:
        precision = recall = f1 = 1.0
    else:
        precision = safe_divide(true_positive, true_positive + false_positive)
        recall = safe_divide(true_positive, true_positive + false_negative)
        f1 = safe_divide(2 * precision * recall, precision + recall)

    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact_match": predicted_facts == reference_facts,
        "predicted_count": len(predicted_facts),
        "reference_count": len(reference_facts),
        "true_positive_items": sorted(true_positive_items, key=repr),
        "false_positive_items": sorted(false_positive_items, key=repr),
        "false_negative_items": sorted(false_negative_items, key=repr),
    }

# -----------------------------
# help function
# -----------------------------
def safe_divide(
    numerator: int | float,
    denominator: int | float,
) -> float:
    if denominator == 0:
        return 0.0

    return numerator / denominator


def compute_decision_action_consistency(
    proposal: dict[str, Any],
) -> dict[str, Any]:
    """Check whether the proposal shape agrees with its declared decision."""
    decision = proposal.get("source_decision")
    actions = proposal.get("table_actions", [])
    if not isinstance(actions, list):
        actions = []
    table_action_types = [
        action.get("action") for action in actions if isinstance(action, dict)
    ]
    issues: list[str] = []
    if decision == "create_table":
        if table_action_types.count("create") != 1:
            issues.append("create_table requires exactly one create table action")
        if "map" in table_action_types:
            issues.append("create_table cannot map to an existing table")
    elif decision in {"extend_table", "insert_table"}:
        if table_action_types.count("map") != 1:
            issues.append(f"{decision} requires exactly one map table action")
        if "create" in table_action_types:
            issues.append(f"{decision} cannot create a table")
    else:
        issues.append("unsupported or missing source_decision")

    if decision == "insert_table":
        for action in actions:
            if not isinstance(action, dict):
                continue
            if any(
                column_action.get("action") == "create"
                for column_action in action.get("column_actions", [])
                if isinstance(column_action, dict)
            ):
                issues.append("insert_table cannot create columns")
                break
    return {"consistent": not issues, "issue_count": len(issues), "issues": issues}


def compute_rdb_complexity_features(
    rdb: dict[str, Any], incoming_table: dict[str, Any]
) -> dict[str, Any]:
    """Extract case-level schema-width, key, and FK-graph features."""
    tables = rdb.get("schema", {}).get("tables", {})
    if not isinstance(tables, dict):
        tables = {}
    widths = [
        len(table.get("columns", {}))
        for table in tables.values()
        if isinstance(table, dict)
    ]
    incoming_tables = incoming_table.get("schema", {}).get("tables", {})
    incoming_width = sum(
        len(table.get("columns", {}))
        for table in incoming_tables.values()
        if isinstance(table, dict)
    ) if isinstance(incoming_tables, dict) else 0

    constraints = rdb.get("constraints", {}).get("constraints", {})
    if not isinstance(constraints, dict):
        constraints = {}
    primary_keys = constraints.get("primary_keys", {})
    foreign_keys = constraints.get("foreign_keys", {})
    if not isinstance(primary_keys, dict):
        primary_keys = {}
    if not isinstance(foreign_keys, dict):
        foreign_keys = {}

    pk_widths = [len(cols) for cols in primary_keys.values() if isinstance(cols, list)]
    fk_widths: list[int] = []
    degree = {table: 0 for table in tables}
    fk_count = 0
    for source_table, items in foreign_keys.items():
        if not isinstance(items, list):
            continue
        for fk in items:
            if not isinstance(fk, dict):
                continue
            fk_count += 1
            columns = fk.get("columns")
            fk_widths.append(len(columns) if isinstance(columns, list) else 0)
            if source_table in degree:
                degree[source_table] += 1
            referenced_table = fk.get("referenced_table")
            if referenced_table in degree:
                degree[referenced_table] += 1

    return {
        "existing_table_count": len(tables),
        "existing_attribute_count": sum(widths),
        "incoming_attribute_count": incoming_width,
        "mean_attributes_per_relation": safe_divide(sum(widths), len(widths)),
        "max_attributes_per_relation": max(widths, default=0),
        "existing_foreign_key_count": fk_count,
        "foreign_keys_per_relation": safe_divide(fk_count, len(tables)),
        "mean_fk_degree": safe_divide(sum(degree.values()), len(degree)),
        "max_fk_degree": max(degree.values(), default=0),
        "composite_pk_count": sum(width > 1 for width in pk_widths),
        "mean_pk_width": safe_divide(sum(pk_widths), len(pk_widths)),
        "max_pk_width": max(pk_widths, default=0),
        "composite_fk_count": sum(width > 1 for width in fk_widths),
        "mean_fk_width": safe_divide(sum(fk_widths), len(fk_widths)),
        "max_fk_width": max(fk_widths, default=0),
    }


def _read_csv_multiset(path: Path, columns: list[str] | None = None) -> Counter[tuple[str, ...]]:
    if not path.exists():
        return Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        selected = columns or list(reader.fieldnames or [])
        return Counter(tuple(row.get(column, "") for column in selected) for row in reader)


def compute_final_tuple_metrics(
    predicted_rdb_path: str | Path,
    expected_rdb_path: str | Path,
    expected_schema: dict[str, Any],
) -> dict[str, Any]:
    """Compare complete final-table row multisets using the reference column order."""
    predicted_root = Path(predicted_rdb_path) / "tables"
    expected_root = Path(expected_rdb_path) / "tables"
    tables = expected_schema.get("tables", {})
    matched = predicted_total = expected_total = 0
    exact_tables = 0
    expected_table_names = set(tables)
    predicted_table_names = {path.stem for path in predicted_root.glob("*.csv")}
    all_table_names = expected_table_names | predicted_table_names
    for table_name in sorted(all_table_names):
        table = tables.get(table_name, {})
        columns = table.get("column_order") or list(table.get("columns", {}))
        if table_name not in expected_table_names:
            columns = None
        predicted = _read_csv_multiset(predicted_root / f"{table_name}.csv", columns)
        expected = (
            _read_csv_multiset(expected_root / f"{table_name}.csv", columns)
            if table_name in expected_table_names else Counter()
        )
        matched += sum((predicted & expected).values())
        predicted_total += sum(predicted.values())
        expected_total += sum(expected.values())
        exact_tables += (
            predicted == expected
            and (table_name in predicted_table_names) == (table_name in expected_table_names)
        )
    precision = safe_divide(matched, predicted_total)
    recall = safe_divide(matched, expected_total)
    return {
        "true_positive": matched,
        "false_positive": predicted_total - matched,
        "false_negative": expected_total - matched,
        "matched_row_count": matched,
        "predicted_row_count": predicted_total,
        "expected_row_count": expected_total,
        "precision": precision,
        "recall": recall,
        "f1": safe_divide(2 * precision * recall, precision + recall),
        "exact_match": exact_tables == len(all_table_names),
        "exact_table_rate": safe_divide(exact_tables, len(all_table_names)),
    }


def compute_tuple_incorporation_metrics(
    incoming_rows: list[dict[str, Any]],
    column_placements: dict[str, str],
    predicted_rdb_path: str | Path,
) -> dict[str, Any]:
    """Measure whether the incoming row values supplied to the run appear at their targets."""
    placements_by_table: dict[str, list[tuple[str, str]]] = {}
    for source_column, target_location in column_placements.items():
        if not isinstance(target_location, str) or "." not in target_location:
            continue
        target_table, target_column = target_location.split(".", maxsplit=1)
        placements_by_table.setdefault(target_table, []).append(
            (source_column, target_column)
        )

    required = matched = 0
    for target_table, placements in placements_by_table.items():
        target_columns = [target for _, target in placements]
        available = _read_csv_multiset(
            Path(predicted_rdb_path) / "tables" / f"{target_table}.csv",
            target_columns,
        )
        expected = Counter(
            tuple(str(row.get(source, "")) for source, _ in placements)
            for row in incoming_rows
        )
        required += sum(expected.values())
        matched += sum((expected & available).values())
    return {
        "applicable": bool(placements_by_table) and bool(incoming_rows),
        "matched_row_count": matched,
        "required_row_count": required,
        "accuracy": safe_divide(matched, required),
        "full_incorporation": required > 0 and matched == required,
    }


def compute_decision_metrics(
    predicted_decision: str,
    reference_decision: str,
) -> dict[str, Any]:
    """
    Compare the predicted decision with the reference decision.

    Args:
        predicted_decision:
            Decision generated by the model.
        reference_decision:
            Reference decision from the benchmark.

    Returns:
        {
            "predicted": str,
            "reference": str,
            "correct": bool,
        }
    """
    return {
        "predicted": predicted_decision,
        "reference": reference_decision,
        "correct": predicted_decision == reference_decision,
    }


def compute_target_table_metrics(
    predicted_target_tables: list[str],
    reference_target_table: str | None,
    applicable: bool,
) -> dict[str, Any]:
    """
    Compare the predicted existing target table with
    the reference target table.

    A prediction is correct only when exactly one existing
    target table is predicted and it equals the reference.
    """
    predicted_target_tables = sorted(
        set(predicted_target_tables)
    )

    predicted_target_table = (
        predicted_target_tables[0]
        if len(predicted_target_tables) == 1
        else None
    )

    correct = (
        predicted_target_table == reference_target_table
        if applicable
        else None
    )

    return {
        "applicable": applicable,
        "predicted": predicted_target_table,
        "reference": reference_target_table,
        "correct": correct,
        "predicted_table_count": len(predicted_target_tables),
        "predicted_tables": predicted_target_tables,
    }


def compute_column_placement_metrics(
    predicted_placements: set[tuple[str, str, str]],
    reference_placements: set[tuple[str, str, str]],
) -> dict[str, Any]:
    """
    Compute precision, recall, and F1 for incoming-column
    placements.

    Each placement has the form:
        (
            source_column,
            target_table,
            target_column,
        )
    """
    true_positive_items = (
        predicted_placements & reference_placements
    )

    false_positive_items = (
        predicted_placements - reference_placements
    )

    false_negative_items = (
        reference_placements - predicted_placements
    )

    true_positive = len(true_positive_items)
    false_positive = len(false_positive_items)
    false_negative = len(false_negative_items)

    # Both sets are empty: the prediction perfectly matches
    # the reference because neither contains placement facts.
    if not predicted_placements and not reference_placements:
        precision = 1.0
        recall = 1.0
        f1 = 1.0
    else:
        precision_denominator = (
            true_positive + false_positive
        )
        recall_denominator = (
            true_positive + false_negative
        )

        precision = (
            true_positive / precision_denominator
            if precision_denominator > 0
            else 0.0
        )

        recall = (
            true_positive / recall_denominator
            if recall_denominator > 0
            else 0.0
        )

        f1 = (
            2 * precision * recall
            / (precision + recall)
            if precision + recall > 0
            else 0.0
        )

    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "predicted_count": len(predicted_placements),
        "reference_count": len(reference_placements),
        "true_positive_items": sorted(true_positive_items),
        "false_positive_items": sorted(false_positive_items),
        "false_negative_items": sorted(false_negative_items),
    }

def compute_proposal_fact_metrics(
    predicted_facts: set[tuple[Any, ...]],
    reference_facts: set[tuple[Any, ...]],
) -> dict[str, Any]:
    """
    Compute precision, recall, and F1 between predicted
    and reference proposal facts.
    """
    true_positive_items = (
        predicted_facts & reference_facts
    )

    false_positive_items = (
        predicted_facts - reference_facts
    )

    false_negative_items = (
        reference_facts - predicted_facts
    )

    true_positive = len(true_positive_items)
    false_positive = len(false_positive_items)
    false_negative = len(false_negative_items)

    precision_denominator = (
        true_positive + false_positive
    )

    recall_denominator = (
        true_positive + false_negative
    )

    precision = (
        true_positive / precision_denominator
        if precision_denominator > 0
        else 0.0
    )

    recall = (
        true_positive / recall_denominator
        if recall_denominator > 0
        else 0.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall > 0
        else 0.0
    )

    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "predicted_count": len(predicted_facts),
        "reference_count": len(reference_facts),
        "true_positive_items": sorted(true_positive_items, key=repr),
        "false_positive_items": sorted(false_positive_items, key=repr),
        "false_negative_items": sorted(false_negative_items, key=repr),
    }

def compute_required_column_coverage(
    required_columns: set[str],
    covered_columns: set[str],
) -> dict[str, Any]:
    """
    Compute coverage of required incoming columns.

    The function only calculates the metric. It does not
    read proposal or schema structures.
    """
    covered_required_columns = (
        required_columns & covered_columns
    )

    missing_required_columns = (
        required_columns - covered_columns
    )

    unexpected_columns = (
        covered_columns - required_columns
    )

    required_count = len(required_columns)
    covered_count = len(
        covered_required_columns
    )

    coverage = (
        covered_count / required_count
        if required_count > 0
        else 1.0
    )

    return {
        "required_count": required_count,
        "covered_count": covered_count,
        "coverage": coverage,
        "full_coverage": (covered_count == required_count),
        # "covered_columns": sorted(covered_required_columns),
        # "missing_columns": sorted(missing_required_columns),
        # "unexpected_columns": sorted(unexpected_columns),
    }


def compute_proposal_validity_metrics(
    raw_valid: bool,
    checked_valid: bool,
    invalid_references: list[dict[str, Any]],
    broken_foreign_keys: list[dict[str, Any]],
    duplicate_definitions: list[dict[str, Any]],
    conflicting_operations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "raw_valid": raw_valid,
        "checked_valid": checked_valid,
        "invalid_reference_count": len(invalid_references),
        "broken_fk_count": len(broken_foreign_keys),
        "duplicate_definition_count": len(duplicate_definitions),
        "conflicting_operation_count": len(conflicting_operations),
        # "invalid_references": (invalid_references),
        # "broken_foreign_keys": (broken_foreign_keys),
        # "duplicate_definitions": (duplicate_definitions),
        # "conflicting_operations": (conflicting_operations),
    }




def _freeze(value: Any) -> Any:
    """
    Convert nested dictionaries and lists into hashable values.
    """
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item))for key, item in value.items()))

    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)

    if isinstance(value, set):
        return tuple(sorted((_freeze(item) for item in value), key=repr))

    return value


def extract_schema_facts(rdb: dict[str, Any]) -> set[tuple[Any, ...]]:
    """Normalize the complete schema into comparable table/column facts."""
    facts: set[tuple[Any, ...]] = set()
    tables = rdb.get("schema", {}).get("tables", {})
    if not isinstance(tables, dict):
        return facts

    for table_name, table in tables.items():
        facts.add(("table", table_name))
        if not isinstance(table, dict):
            continue
        columns = table.get("columns", {})
        if isinstance(columns, dict):
            for column_name, definition in columns.items():
                facts.add(
                    (
                        "column",
                        table_name,
                        column_name,
                        _freeze(definition),
                    )
                )
        order = table.get("column_order")
        if isinstance(order, list):
            facts.add(("column_order", table_name, tuple(order)))
    return facts


def extract_constraint_facts(
    rdb: dict[str, Any],
    constraint_types: set[str] | None = None,
) -> set[tuple[Any, ...]]:
    """Normalize explicit RDB constraints, optionally filtering fact types."""
    tables = set(rdb.get("schema", {}).get("tables", {}))
    facts = _extract_protected_facts(rdb, tables)
    constraint_fact_types = {
        "primary_key",
        "foreign_key",
        "unique_constraint",
        "check_constraint",
        "index",
    }
    facts = {fact for fact in facts if fact[0] in constraint_fact_types}
    if constraint_types is not None:
        facts = {fact for fact in facts if fact[0] in constraint_types}
    return facts


def _iter_constraint_definitions(value: Any) -> list[Any]:
    """
    Convert one table's constraint definitions into
    independent definitions.

    Examples:
        ["column_a", "column_b"]
            -> one composite definition

        [["column_a"], ["column_b"]]
            -> two definitions

        [{"expression": "..."}]
            -> one definition
    """
    if not isinstance(value, list):
        return [value]

    if not value:
        return []

    if all(isinstance(item, str) for item in value):
        return [value]

    return value


def _extract_foreign_key_facts(
    rdb: dict[str, Any],
    protected_tables: set[str],
) -> set[tuple[Any, ...]]:
    constraints = (rdb.get("constraints", {}).get("constraints", {}))

    foreign_keys = constraints.get("foreign_keys",{})

    if not isinstance(foreign_keys, dict):
        return set()

    facts: set[tuple[Any, ...]] = set()

    for source_table, definitions in foreign_keys.items():
        if not isinstance(definitions, list):
            continue

        for foreign_key in definitions:
            if not isinstance(foreign_key, dict):
                continue

            referenced_table = foreign_key.get("referenced_table")

            # An FK is protected if either endpoint is a
            # protected table.
            if (source_table not in protected_tables and referenced_table not in protected_tables):
                continue

            columns = _freeze(foreign_key.get("columns"))
            referenced_columns = _freeze(
                foreign_key.get("referenced_columns")
            )

            # Keep malformed values (for example null) as facts so they are
            # counted as mismatches instead of crashing or being discarded.
            facts.add(
                (
                    "foreign_key",
                    source_table,
                    columns,
                    referenced_table,
                    referenced_columns,
                )
            )

    return facts


def _extract_protected_columns(
    rdb: dict[str, Any],
    protected_tables: set[str],
) -> dict[tuple[str, str], Any]:
    """
    Return protected columns and their complete definitions.

    Key:
        (table_name, column_name)

    Value:
        frozen column definition
    """
    schema_tables = (rdb.get("schema", {}).get("tables", {}))

    if not isinstance(schema_tables, dict):
        return {}

    columns: dict[tuple[str, str], Any] = {}

    for table_name in protected_tables:
        table_data = schema_tables.get(table_name)

        if not isinstance(table_data, dict):
            continue

        table_columns = table_data.get("columns", {})

        if not isinstance(table_columns, dict):
            continue

        for column_name, column_definition in (table_columns.items()):
            columns[(table_name, column_name)] = _freeze(column_definition)

    return columns


def _extract_protected_facts(
    rdb: dict[str, Any],
    protected_tables: set[str],
) -> set[tuple[Any, ...]]:
    """
    Extract schema and explicit constraint facts belonging
    to protected tables.

    Profiles, sample values and inferred constraints are
    intentionally excluded.
    """
    facts: set[tuple[Any, ...]] = set()

    schema_tables = (rdb.get("schema", {}).get("tables", {}))

    if not isinstance(schema_tables, dict):
        schema_tables = {}

    # -------------------------------------------------
    # Table and column facts
    # -------------------------------------------------

    for table_name in protected_tables:
        table_data = schema_tables.get(table_name)

        if not isinstance(table_data, dict):
            continue

        facts.add(("table", table_name))

        columns = table_data.get("columns", {})

        if isinstance(columns, dict):
            for column_name, column_definition in (columns.items()):
                facts.add(("column", table_name, column_name, _freeze(column_definition)))

        column_order = table_data.get("column_order", [])

        if isinstance(column_order, list):
            facts.add(("column_order", table_name, tuple(column_order)))

    # -------------------------------------------------
    # Explicit constraint facts
    # -------------------------------------------------

    constraints = (rdb.get("constraints", {}).get("constraints", {}))

    if not isinstance(constraints, dict):
        constraints = {}

    primary_keys = constraints.get("primary_keys", {})

    if isinstance(primary_keys, dict):
        for table_name in protected_tables:
            columns = primary_keys.get(table_name)

            if isinstance(columns, list):
                facts.add(("primary_key", table_name, tuple(columns)))

    for constraint_type, fact_type in [("unique_constraints", "unique_constraint"), ("check_constraints", "check_constraint"), ("indexes", "index",)]:
        constraint_data = constraints.get(constraint_type, {})

        if not isinstance(constraint_data, dict):
            continue

        for table_name in protected_tables:
            definitions = constraint_data.get(table_name)

            if definitions is None:
                continue

            for definition in (_iter_constraint_definitions(definitions)):
                facts.add((fact_type, table_name, _freeze(definition)))

    facts.update(_extract_foreign_key_facts(rdb=rdb, protected_tables=protected_tables))

    return facts


def _get_fact_tables(
    fact: tuple[Any, ...],
) -> set[str]:
    fact_type = fact[0]

    if fact_type == "foreign_key":
        tables = {fact[1]}

        if isinstance(fact[3], str):
            tables.add(fact[3])

        return tables

    if fact_type in {"table", "column", "column_order", "primary_key", "unique_constraint", "check_constraint", "index"}:
        return {fact[1]}

    return set()


def compute_non_target_preservation_metrics(
    existing_rdb: dict[str, Any],
    predicted_rdb: dict[str, Any],
    protected_tables: list[str],
) -> dict[str, Any]:
    """
    Measure whether protected existing schema facts remain
    unchanged in the predicted RDB.

    Non-target preservation:
        preserved protected facts
        / all original protected facts
    """
    protected_table_set = set(protected_tables)

    existing_schema_tables = (existing_rdb.get("schema", {}).get("tables", {}))

    if not isinstance(existing_schema_tables, dict):
        existing_schema_tables = {}

    unknown_protected_tables = sorted(protected_table_set - set(existing_schema_tables))

    valid_protected_tables = (protected_table_set & set(existing_schema_tables))

    if not valid_protected_tables:
        return {
            "applicable": False,
            "score": None,
            "protected_table_count": 0,
            "protected_fact_count": 0,
            "preserved_fact_count": 0,
            "missing_protected_fact_count": 0,
            "unexpected_added_fact_count": 0,
            "unexpected_table_modification_count": 0,
            "unexpected_table_modification_rate": None,
            "protected_column_count": 0,
            "unexpected_column_modification_count": 0,
            "unexpected_column_modification_rate": None,
            "unexpected_fk_attachment_count": 0,
            "modified_tables": [],
            "modified_columns": [],
            "missing_protected_facts": [],
            "unexpected_added_facts": [],
            "unexpected_fk_attachments": [],
            "unknown_protected_tables": (
                unknown_protected_tables
            ),
        }

    existing_facts = _extract_protected_facts(rdb=existing_rdb, protected_tables=valid_protected_tables)

    predicted_facts = _extract_protected_facts(rdb=predicted_rdb, protected_tables=valid_protected_tables)

    preserved_facts = (existing_facts & predicted_facts)

    missing_protected_facts = (existing_facts - predicted_facts)

    unexpected_added_facts = (predicted_facts - existing_facts)

    protected_fact_count = len(existing_facts)
    preserved_fact_count = len(preserved_facts)

    score = (preserved_fact_count / protected_fact_count if protected_fact_count > 0 else 1.0)

    # -------------------------------------------------
    # Table-level modifications
    # -------------------------------------------------

    modified_tables: list[str] = []

    for table_name in sorted(valid_protected_tables):
        existing_table_facts = {fact for fact in existing_facts if table_name in _get_fact_tables(fact)}

        predicted_table_facts = {fact for fact in predicted_facts if table_name in _get_fact_tables(fact)}

        if (existing_table_facts != predicted_table_facts):
            modified_tables.append(table_name)

    unexpected_table_modification_count = len(modified_tables)

    unexpected_table_modification_rate = (unexpected_table_modification_count / len(valid_protected_tables))

    # -------------------------------------------------
    # Column-level modifications
    # -------------------------------------------------

    existing_columns = _extract_protected_columns(rdb=existing_rdb, protected_tables=valid_protected_tables,)

    predicted_columns = _extract_protected_columns(rdb=predicted_rdb, protected_tables=valid_protected_tables)

    all_column_keys = (set(existing_columns) | set(predicted_columns))

    modified_column_keys = {column_key for column_key in all_column_keys if (existing_columns.get(column_key) != predicted_columns.get(column_key))}

    modified_columns = sorted(f"{table}.{column}" for table, column in modified_column_keys)

    unexpected_column_modification_count = len(modified_column_keys)

    # Use the union as denominator so the rate remains
    # between 0 and 1, including added columns.
    unexpected_column_modification_rate = (unexpected_column_modification_count / len(all_column_keys) if all_column_keys else 0.0)

    # -------------------------------------------------
    # Unexpected FK attachments
    # -------------------------------------------------

    existing_foreign_keys = (_extract_foreign_key_facts(rdb=existing_rdb, protected_tables=valid_protected_tables))

    predicted_foreign_keys = (_extract_foreign_key_facts(rdb=predicted_rdb, protected_tables=valid_protected_tables))

    unexpected_fk_attachments = (predicted_foreign_keys - existing_foreign_keys)

    return {
        "applicable": True,
        "score": score,
        "protected_table_count": len(valid_protected_tables),
        "protected_fact_count": (protected_fact_count),
        "preserved_fact_count": (preserved_fact_count),
        "missing_protected_fact_count": len(missing_protected_facts),
        "unexpected_added_fact_count": len(unexpected_added_facts),
        "unexpected_table_modification_count": (unexpected_table_modification_count),
        "unexpected_table_modification_rate": (unexpected_table_modification_rate),
        "protected_column_count": len(existing_columns),
        "unexpected_column_modification_count": (unexpected_column_modification_count),
        "unexpected_column_modification_rate": (unexpected_column_modification_rate),
        "unexpected_fk_attachment_count": len(unexpected_fk_attachments),
        "modified_tables": modified_tables,
        "modified_columns": modified_columns,
        "missing_protected_facts": sorted(missing_protected_facts, key=repr),
        "unexpected_added_facts": sorted(unexpected_added_facts, key=repr),
        "unexpected_fk_attachments": sorted(unexpected_fk_attachments, key=repr),
        "unknown_protected_tables": (unknown_protected_tables),
    }
