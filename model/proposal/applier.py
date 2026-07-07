from copy import deepcopy
from typing import Any

from model.core.schemas import IntegrationProposal
from model.utils.io import terminal_message

from copy import deepcopy
from typing import Any

from model.core.schemas import IntegrationProposal


def apply_proposal(
    *,
    incoming_schema: dict[str, Any],
    existing_schema: dict[str, Any],
    existing_constraints: dict[str, Any],
    proposal: IntegrationProposal,
) -> dict[str, Any]:
    """
    Apply proposal and return before/after partial RDB.

    This function does not modify raw data.
    It only builds schema/constraint preview for validation.

    Returns:
        {
            "before": {
                "schema": {"tables": {...}},
                "constraints": {...}
            },
            "after": {
                "schema": {"tables": {...}},
                "constraints": {...}
            }
        }
    """

    touched_tables = _collect_touched_tables(proposal=proposal)

    terminal_message("info", f"Appling proposal for {list(touched_tables)}.", "\t")

    before = _build_partial_rdb(
        schema=existing_schema,
        constraints=existing_constraints,
        tables=touched_tables,
    )

    working_schema = deepcopy(existing_schema)
    working_constraints = deepcopy(existing_constraints)

    terminal_message("info", f"Working tabls {list(before['schema']['tables'].keys())}.", "\t")

    _apply_table_actions(
        incoming_schema=incoming_schema,
        working_schema=working_schema,
        proposal=proposal,
    )

    _apply_constraint_actions(
        working_constraints=working_constraints,
        proposal=proposal,
    )

    after = _build_partial_rdb(
        schema=working_schema,
        constraints=working_constraints,
        tables=touched_tables,
    )

    terminal_message("success", f"Preview finish with tables: {list(after['schema']['tables'].keys())}.", "\t")

    return {
        "before": before,
        "after": after,
    }

def _collect_touched_tables(
    *,
    proposal: IntegrationProposal,
) -> set[str]:
    touched_tables: set[str] = set()

    for table_action in proposal.get("table_actions", []):
        touched_tables.add(table_action["table"])

    for constraint_action in proposal.get("constraint_actions", []):
        touched_tables.add(constraint_action["table"])

        referenced_table = constraint_action.get("referenced_table")
        if referenced_table:
            touched_tables.add(referenced_table)

    return touched_tables

def _build_partial_rdb(
    *,
    schema: dict[str, Any],
    constraints: dict[str, Any],
    tables: set[str],
) -> dict[str, Any]:
    return {
        "schema": {
            "tables": _extract_tables(
                schema=schema,
                tables=tables,
            )
        },
        "constraints": _extract_related_constraints(
            constraints=constraints,
            tables=tables,
        ),
    }

def _extract_tables(
    *,
    schema: dict[str, Any],
    tables: set[str],
) -> dict[str, Any]:
    existing_tables = schema["tables"]

    return {
        table: deepcopy(existing_tables[table])
        for table in sorted(tables)
        if table in existing_tables
    }


def _apply_table_actions(
    *,
    incoming_schema: dict[str, Any],
    working_schema: dict[str, Any],
    proposal: IntegrationProposal,
) -> None:
    for table_action in proposal.get("table_actions", []):
        action = table_action["action"]

        if action == "map":
            _apply_map_table_action(
                incoming_schema=incoming_schema,
                working_schema=working_schema,
                table_action=table_action,
            )

        elif action == "create":
            _apply_create_table_action(
                incoming_schema=incoming_schema,
                working_schema=working_schema,
                table_action=table_action,
            )

        else:
            raise ValueError(f"Unsupported table action: {action}")

        table = table_action["table"]
        _normalize_column_order(
            table_schema=working_schema["tables"][table],
        )
        

def _apply_map_table_action(
    *,
    incoming_schema: dict[str, Any],
    working_schema: dict[str, Any],
    table_action: dict[str, Any],
) -> None:
    table = table_action["table"]

    working_schema["tables"][table].setdefault("columns", {})
    working_schema["tables"][table].setdefault(
        "column_order",
        list(working_schema["tables"][table]["columns"].keys()),
    )

    for column_action in table_action.get("column_actions", []):
        _apply_column_action(
            incoming_schema=incoming_schema,
            working_schema=working_schema,
            table=table,
            column_action=column_action,
        )


def _apply_create_table_action(
    *,
    incoming_schema: dict[str, Any],
    working_schema: dict[str, Any],
    table_action: dict[str, Any],
) -> None:
    table = table_action["table"]

    if table not in working_schema["tables"]:
        working_schema["tables"][table] = {
            "columns": {},
            "column_order": [],
        }

    working_schema["tables"][table].setdefault("columns", {})
    working_schema["tables"][table].setdefault("column_order", [])

    for column_action in table_action.get("column_actions", []):
        _apply_column_action(
            incoming_schema=incoming_schema,
            working_schema=working_schema,
            table=table,
            column_action=column_action,
        )


def _apply_column_action(
    *,
    incoming_schema: dict[str, Any],
    working_schema: dict[str, Any],
    table: str,
    column_action: dict[str, Any],
) -> None:
    action = column_action["action"]

    if action == "map":
        return

    if action == "create":
        _apply_create_column_action(
            incoming_schema=incoming_schema,
            working_schema=working_schema,
            table=table,
            column_action=column_action,
        )
        return

    if action == "drop":
        _apply_drop_column_action(
            working_schema=working_schema,
            table=table,
            column_action=column_action,
        )
        return

    if action in {"split", "merge", "derive"}:
        raise NotImplementedError(
            f"Column action '{action}' is reserved but not implemented."
        )

    raise ValueError(f"Unsupported column action: {action}")


def _apply_create_column_action(
    *,
    incoming_schema: dict[str, Any],
    working_schema: dict[str, Any],
    table: str,
    column_action: dict[str, Any],
) -> None:
    source_columns = column_action["source_columns"]
    target_columns = column_action["target_columns"]

    table_schema = working_schema["tables"][table]
    table_schema.setdefault("columns", {})
    table_schema.setdefault("column_order", list(table_schema["columns"].keys()))

    for source_column, target_column in zip(source_columns, target_columns):
        source_column_schema = _get_source_column_schema(
            incoming_schema=incoming_schema,
            source_column=source_column,
        )

        table_schema["columns"][target_column] = deepcopy(source_column_schema)

        if target_column not in table_schema["column_order"]:
            table_schema["column_order"].append(target_column)


def _apply_drop_column_action(
    *,
    working_schema: dict[str, Any],
    table: str,
    column_action: dict[str, Any],
) -> None:
    table_schema = working_schema["tables"][table]
    table_schema.setdefault("columns", {})
    table_schema.setdefault("column_order", list(table_schema["columns"].keys()))

    for target_column in column_action["target_columns"]:
        table_schema["columns"].pop(target_column, None)

        if target_column in table_schema["column_order"]:
            table_schema["column_order"].remove(target_column)


def _apply_constraint_actions(
    *,
    working_constraints: dict[str, Any],
    proposal: IntegrationProposal,
) -> None:
    constraints = working_constraints["constraints"]

    for constraint_action in proposal.get("constraint_actions", []):
        action = constraint_action["action"]

        if action == "add_primary_key":
            constraints.setdefault("primary_keys", {})
            constraints["primary_keys"][constraint_action["table"]] = constraint_action["columns"]

        elif action == "add_foreign_key":
            constraints.setdefault("foreign_keys", {})
            table = constraint_action["table"]
            constraints["foreign_keys"].setdefault(table, [])
            constraints["foreign_keys"][table].append(
                {
                    "columns": constraint_action["columns"],
                    "referenced_table": constraint_action["referenced_table"],
                    "referenced_columns": constraint_action["referenced_columns"],
                }
            )

        elif action == "add_unique_constraint":
            constraints.setdefault("unique_constraints", {})
            table = constraint_action["table"]
            constraints["unique_constraints"].setdefault(table, [])
            constraints["unique_constraints"][table].append(
                constraint_action["columns"]
            )

        elif action == "add_index":
            constraints.setdefault("indexes", {})
            table = constraint_action["table"]
            constraints["indexes"].setdefault(table, [])
            constraints["indexes"][table].append(
                constraint_action["columns"]
            )

        else:
            raise ValueError(f"Unsupported constraint action: {action}")
        

def _get_source_column_schema(
    *,
    incoming_schema: dict[str, Any],
    source_column: str,
) -> dict[str, Any]:
    if "columns" in incoming_schema:
        return incoming_schema["columns"][source_column]

    if "tables" in incoming_schema:
        for table_schema in incoming_schema["tables"].values():
            columns = table_schema.get("columns", {})
            if source_column in columns:
                return columns[source_column]

    raise KeyError(f"Source column not found in incoming_schema: {source_column}")


def _extract_related_constraints(
    *,
    constraints: dict[str, Any],
    tables: set[str],
) -> dict[str, Any]:
    raw_constraints = constraints["constraints"]

    result: dict[str, Any] = {
        "primary_keys": {},
        "foreign_keys": {},
        "unique_constraints": {},
        "indexes": {},
    }

    for table, columns in raw_constraints.get("primary_keys", {}).items():
        if table in tables:
            result["primary_keys"][table] = deepcopy(columns)

    for table, fks in raw_constraints.get("foreign_keys", {}).items():
        related_fks = []

        for fk in fks:
            if table in tables or fk.get("referenced_table") in tables:
                related_fks.append(deepcopy(fk))

        if related_fks:
            result["foreign_keys"][table] = related_fks

    for table, unique_constraints in raw_constraints.get("unique_constraints", {}).items():
        if table in tables:
            result["unique_constraints"][table] = deepcopy(unique_constraints)

    for table, indexes in raw_constraints.get("indexes", {}).items():
        if table in tables:
            result["indexes"][table] = deepcopy(indexes)

    return result

def _normalize_column_order(
    *,
    table_schema: dict[str, Any],
) -> None:
    columns = table_schema.setdefault("columns", {})
    column_order = table_schema.setdefault("column_order", [])

    # Remove columns that no longer exist.
    column_order[:] = [
        column
        for column in column_order
        if column in columns
    ]

    # Append columns that exist but are missing from column_order.
    for column in columns:
        if column not in column_order:
            column_order.append(column)