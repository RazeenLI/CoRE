from __future__ import annotations

import json
from typing import Any


PROPOSAL_DECISION_TYPES = {
    "extend_table",
    "create_table",
    "no_schema_change",
    "review",
    "insert_table",
}

TABLE_ACTION_TYPES = {
    "map",
    "create",
}

COLUMN_ACTION_TYPES = {
    "map",
    "create",
    "drop",
    "split",
    "merge",
    "derive",
}

CONSTRAINT_ACTION_TYPES = {
    "add_primary_key",
    "add_foreign_key",
    "add_unique_constraint",
    "add_index",
}


def _is_string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) and item for item in value)
    )


def _append_unique(
    items: list[dict[str, Any]],
    seen: set[str],
    item: dict[str, Any],
) -> None:
    key = json.dumps(
        item,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )

    if key not in seen:
        items.append(item)
        seen.add(key)


def _get_schema_tables(
    rdb: dict[str, Any],
) -> dict[str, Any]:
    tables = rdb.get("schema", {}).get("tables", {})

    if not isinstance(tables, dict):
        return {}

    return tables


def _get_constraints(
    rdb: dict[str, Any],
) -> dict[str, Any]:
    constraints = (
        rdb.get("constraints", {})
        .get("constraints", {})
    )

    if not isinstance(constraints, dict):
        return {}

    return constraints


def _get_table_columns(
    tables: dict[str, Any],
    table: str,
) -> dict[str, Any]:
    table_data = tables.get(table, {})

    if not isinstance(table_data, dict):
        return {}

    columns = table_data.get("columns", {})

    if not isinstance(columns, dict):
        return {}

    return columns


def _get_column_type(
    tables: dict[str, Any],
    table: str,
    column: str,
) -> str | None:
    column_data = _get_table_columns(
        tables,
        table,
    ).get(column)

    if not isinstance(column_data, dict):
        return None

    data_type = column_data.get("type")

    return data_type if isinstance(data_type, str) else None


def _types_compatible(
    source_type: str | None,
    target_type: str | None,
) -> bool:
    if source_type is None or target_type is None:
        return True

    source_type = source_type.lower().strip()
    target_type = target_type.lower().strip()

    if source_type == target_type:
        return True

    compatible_groups = [
        {
            "smallint",
            "integer",
            "bigint",
        },
        {
            "float",
            "double",
            "real",
            "decimal",
            "numeric",
        },
        {
            "string",
            "text",
            "varchar",
            "char",
        },
        {
            "date",
            "datetime",
            "timestamp",
        },
    ]

    return any(
        source_type in group
        and target_type in group
        for group in compatible_groups
    )


def _foreign_key_key(
    table: str,
    columns: list[str],
    referenced_table: str,
    referenced_columns: list[str],
) -> tuple[
    str,
    tuple[str, ...],
    str,
    tuple[str, ...],
]:
    return (
        table,
        tuple(columns),
        referenced_table,
        tuple(referenced_columns),
    )


def _collect_foreign_keys(
    constraints: dict[str, Any],
) -> set[
    tuple[
        str,
        tuple[str, ...],
        str,
        tuple[str, ...],
    ]
]:
    result: set[
        tuple[
            str,
            tuple[str, ...],
            str,
            tuple[str, ...],
        ]
    ] = set()

    foreign_keys = constraints.get(
        "foreign_keys",
        {},
    )

    if not isinstance(foreign_keys, dict):
        return result

    for table, table_foreign_keys in foreign_keys.items():
        if not isinstance(table_foreign_keys, list):
            continue

        for foreign_key in table_foreign_keys:
            if not isinstance(foreign_key, dict):
                continue

            columns = foreign_key.get("columns", [])
            referenced_table = foreign_key.get(
                "referenced_table"
            )
            referenced_columns = foreign_key.get(
                "referenced_columns",
                [],
            )

            if (
                isinstance(table, str)
                and _is_string_list(columns)
                and isinstance(referenced_table, str)
                and referenced_table
                and _is_string_list(referenced_columns)
            ):
                result.add(
                    _foreign_key_key(
                        table=table,
                        columns=columns,
                        referenced_table=referenced_table,
                        referenced_columns=referenced_columns,
                    )
                )

    return result


def _collect_column_constraints(
    constraints: dict[str, Any],
    constraint_name: str,
) -> set[tuple[str, tuple[str, ...]]]:
    result: set[tuple[str, tuple[str, ...]]] = set()

    values = constraints.get(
        constraint_name,
        {},
    )

    if not isinstance(values, dict):
        return result

    for table, definitions in values.items():
        if not isinstance(table, str):
            continue

        if (
            constraint_name == "primary_keys"
            and _is_string_list(definitions)
        ):
            result.add(
                (
                    table,
                    tuple(definitions),
                )
            )
            continue

        if not isinstance(definitions, list):
            continue

        for columns in definitions:
            if _is_string_list(columns):
                result.add(
                    (
                        table,
                        tuple(columns),
                    )
                )

    return result


def check_proposal_validity(
    existing_rdb: dict[str, Any],
    incoming_table: dict[str, Any],
    predicted_proposal: dict[str, Any],
    predicted_rdb: dict[str, Any],
) -> dict[str, Any]:
    invalid_references: list[dict[str, Any]] = []
    broken_foreign_keys: list[dict[str, Any]] = []
    duplicate_definitions: list[dict[str, Any]] = []
    conflicting_operations: list[dict[str, Any]] = []

    invalid_seen: set[str] = set()
    broken_fk_seen: set[str] = set()
    duplicate_seen: set[str] = set()
    conflict_seen: set[str] = set()

    raw_valid = True

    existing_tables = _get_schema_tables(existing_rdb)
    predicted_tables = _get_schema_tables(predicted_rdb)

    incoming_tables = (
        incoming_table
        .get("schema", {})
        .get("tables", {})
    )

    if not isinstance(incoming_tables, dict):
        incoming_tables = {}

    incoming_columns: set[str] = set()

    for table_data in incoming_tables.values():
        if not isinstance(table_data, dict):
            continue

        columns = table_data.get("columns", {})

        if isinstance(columns, dict):
            incoming_columns.update(columns.keys())

    existing_constraints = _get_constraints(
        existing_rdb
    )
    predicted_constraints = _get_constraints(
        predicted_rdb
    )

    # -------------------------------------------------
    # 1. Validate source decision
    # -------------------------------------------------

    source_decision = predicted_proposal.get(
        "source_decision"
    )

    if (
        not isinstance(source_decision, str)
        or source_decision not in PROPOSAL_DECISION_TYPES
    ):
        raw_valid = False

        _append_unique(
            invalid_references,
            invalid_seen,
            {
                "object": "source_decision",
                "value": source_decision,
                "reason": "unsupported_decision_type",
            },
        )

    # -------------------------------------------------
    # 2. Validate table actions
    # -------------------------------------------------

    table_actions = predicted_proposal.get(
        "table_actions",
        [],
    )

    if not isinstance(table_actions, list):
        raw_valid = False

        _append_unique(
            invalid_references,
            invalid_seen,
            {
                "object": "table_actions",
                "reason": "table_actions_must_be_list",
            },
        )

        table_actions = []

    seen_table_actions: set[
        tuple[str, str]
    ] = set()

    table_action_types: dict[
        str,
        set[str],
    ] = {}

    seen_column_actions: set[
        tuple[
            str,
            str,
            tuple[str, ...],
            tuple[str, ...],
        ]
    ] = set()

    target_column_actions: dict[
        tuple[str, str],
        set[str],
    ] = {}

    mapped_tables: set[str] = set()
    created_tables: set[str] = set()

    all_column_action_types: list[str] = []

    for table_action_index, table_action in enumerate(
        table_actions
    ):
        if not isinstance(table_action, dict):
            raw_valid = False

            _append_unique(
                invalid_references,
                invalid_seen,
                {
                    "object": "table_action",
                    "index": table_action_index,
                    "reason": "table_action_must_be_object",
                },
            )
            continue

        table_action_type = table_action.get(
            "action"
        )
        table = table_action.get("table")

        if table_action_type not in TABLE_ACTION_TYPES:
            raw_valid = False

            _append_unique(
                invalid_references,
                invalid_seen,
                {
                    "object": "table_action",
                    "index": table_action_index,
                    "table": table,
                    "action": table_action_type,
                    "reason": "unsupported_table_action",
                },
            )
            continue

        if not isinstance(table, str) or not table:
            raw_valid = False

            _append_unique(
                invalid_references,
                invalid_seen,
                {
                    "object": "table_action",
                    "index": table_action_index,
                    "action": table_action_type,
                    "reason": "missing_table",
                },
            )
            continue

        table_action_key = (
            table_action_type,
            table,
        )

        if table_action_key in seen_table_actions:
            _append_unique(
                duplicate_definitions,
                duplicate_seen,
                {
                    "object": "table_action",
                    "table": table,
                    "action": table_action_type,
                },
            )

        seen_table_actions.add(table_action_key)

        table_action_types.setdefault(
            table,
            set(),
        ).add(table_action_type)

        if table_action_type == "map":
            mapped_tables.add(table)

            if table not in existing_tables:
                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "table",
                        "table": table,
                        "action": "map",
                        "reason": (
                            "mapped_table_not_found_"
                            "in_existing_rdb"
                        ),
                    },
                )

            if table not in predicted_tables:
                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "table",
                        "table": table,
                        "action": "map",
                        "reason": (
                            "mapped_table_not_found_"
                            "in_predicted_rdb"
                        ),
                    },
                )

        elif table_action_type == "create":
            created_tables.add(table)

            if table in existing_tables:
                _append_unique(
                    conflicting_operations,
                    conflict_seen,
                    {
                        "object": "table",
                        "table": table,
                        "action": "create",
                        "reason": (
                            "created_table_already_exists"
                        ),
                    },
                )

            if table not in predicted_tables:
                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "table",
                        "table": table,
                        "action": "create",
                        "reason": (
                            "created_table_not_found_"
                            "in_predicted_rdb"
                        ),
                    },
                )

        existing_columns = _get_table_columns(
            existing_tables,
            table,
        )
        predicted_columns = _get_table_columns(
            predicted_tables,
            table,
        )

        column_actions = table_action.get(
            "column_actions",
            [],
        )

        if not isinstance(column_actions, list):
            raw_valid = False

            _append_unique(
                invalid_references,
                invalid_seen,
                {
                    "object": "column_actions",
                    "table": table,
                    "reason": (
                        "column_actions_must_be_list"
                    ),
                },
            )
            continue

        for column_action_index, column_action in enumerate(
            column_actions
        ):
            if not isinstance(column_action, dict):
                raw_valid = False

                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "column_action",
                        "table": table,
                        "index": column_action_index,
                        "reason": (
                            "column_action_must_be_object"
                        ),
                    },
                )
                continue

            column_action_type = column_action.get(
                "action"
            )

            if column_action_type not in COLUMN_ACTION_TYPES:
                raw_valid = False

                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "column_action",
                        "table": table,
                        "index": column_action_index,
                        "action": column_action_type,
                        "reason": (
                            "unsupported_column_action"
                        ),
                    },
                )
                continue

            all_column_action_types.append(
                column_action_type
            )

            source_columns = column_action.get(
                "source_columns",
                [],
            )
            target_columns = column_action.get(
                "target_columns",
                [],
            )

            if not _is_string_list(source_columns):
                raw_valid = False

                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "column_action",
                        "table": table,
                        "action": column_action_type,
                        "reason": (
                            "source_columns_must_be_"
                            "a_string_list"
                        ),
                        "source_columns": source_columns,
                    },
                )
                continue

            if not _is_string_list(target_columns):
                raw_valid = False

                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "column_action",
                        "table": table,
                        "action": column_action_type,
                        "reason": (
                            "target_columns_must_be_"
                            "a_string_list"
                        ),
                        "target_columns": target_columns,
                    },
                )
                continue

            valid_shape = True

            if column_action_type in {
                "map",
                "create",
            }:
                valid_shape = (
                    len(source_columns) > 0
                    and len(source_columns)
                    == len(target_columns)
                )

            elif column_action_type == "drop":
                valid_shape = (
                    len(target_columns) > 0
                )

            elif column_action_type == "split":
                valid_shape = (
                    len(source_columns) == 1
                    and len(target_columns) >= 2
                )

            elif column_action_type == "merge":
                valid_shape = (
                    len(source_columns) >= 2
                    and len(target_columns) == 1
                )

            elif column_action_type == "derive":
                valid_shape = (
                    len(target_columns) >= 1
                )

            if not valid_shape:
                raw_valid = False

                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "column_action",
                        "table": table,
                        "action": column_action_type,
                        "source_columns": source_columns,
                        "target_columns": target_columns,
                        "reason": (
                            "invalid_column_action_shape"
                        ),
                    },
                )
                continue

            column_action_key = (
                table,
                column_action_type,
                tuple(source_columns),
                tuple(target_columns),
            )

            if column_action_key in seen_column_actions:
                _append_unique(
                    duplicate_definitions,
                    duplicate_seen,
                    {
                        "object": "column_action",
                        "table": table,
                        "action": column_action_type,
                        "source_columns": source_columns,
                        "target_columns": target_columns,
                    },
                )

            seen_column_actions.add(
                column_action_key
            )

            for target_column in target_columns:
                target_column_actions.setdefault(
                    (
                        table,
                        target_column,
                    ),
                    set(),
                ).add(column_action_type)

            # -----------------------------------------
            # Validate source columns
            # -----------------------------------------

            if column_action_type in {
                "map",
                "create",
                "split",
                "merge",
            }:
                for source_column in source_columns:
                    if source_column not in incoming_columns:
                        _append_unique(
                            invalid_references,
                            invalid_seen,
                            {
                                "object": "source_column",
                                "column": source_column,
                                "table": table,
                                "action": column_action_type,
                                "reason": (
                                    "source_column_not_found_"
                                    "in_incoming"
                                ),
                            },
                        )

            elif column_action_type == "derive":
                for source_column in source_columns:
                    if (
                        source_column not in incoming_columns
                        and source_column
                        not in existing_columns
                    ):
                        _append_unique(
                            invalid_references,
                            invalid_seen,
                            {
                                "object": "source_column",
                                "column": source_column,
                                "table": table,
                                "action": "derive",
                                "reason": (
                                    "derive_source_not_found"
                                ),
                            },
                        )

            # -----------------------------------------
            # Validate target columns
            # -----------------------------------------

            if column_action_type == "map":
                for target_column in target_columns:
                    if target_column not in existing_columns:
                        _append_unique(
                            invalid_references,
                            invalid_seen,
                            {
                                "object": "target_column",
                                "table": table,
                                "column": target_column,
                                "action": "map",
                                "reason": (
                                    "mapped_column_not_found_"
                                    "in_existing_rdb"
                                ),
                            },
                        )

                    if target_column not in predicted_columns:
                        _append_unique(
                            invalid_references,
                            invalid_seen,
                            {
                                "object": "target_column",
                                "table": table,
                                "column": target_column,
                                "action": "map",
                                "reason": (
                                    "mapped_column_not_found_"
                                    "in_predicted_rdb"
                                ),
                            },
                        )

            elif column_action_type == "create":
                for target_column in target_columns:
                    if target_column in existing_columns:
                        _append_unique(
                            conflicting_operations,
                            conflict_seen,
                            {
                                "object": "target_column",
                                "table": table,
                                "column": target_column,
                                "action": "create",
                                "reason": (
                                    "created_column_already_exists"
                                ),
                            },
                        )

                    if target_column not in predicted_columns:
                        _append_unique(
                            invalid_references,
                            invalid_seen,
                            {
                                "object": "target_column",
                                "table": table,
                                "column": target_column,
                                "action": "create",
                                "reason": (
                                    "created_column_not_found_"
                                    "in_predicted_rdb"
                                ),
                            },
                        )

            elif column_action_type == "drop":
                for target_column in target_columns:
                    if target_column not in existing_columns:
                        _append_unique(
                            invalid_references,
                            invalid_seen,
                            {
                                "object": "target_column",
                                "table": table,
                                "column": target_column,
                                "action": "drop",
                                "reason": (
                                    "dropped_column_not_found_"
                                    "in_existing_rdb"
                                ),
                            },
                        )

                    if target_column in predicted_columns:
                        _append_unique(
                            conflicting_operations,
                            conflict_seen,
                            {
                                "object": "target_column",
                                "table": table,
                                "column": target_column,
                                "action": "drop",
                                "reason": (
                                    "dropped_column_still_exists_"
                                    "in_predicted_rdb"
                                ),
                            },
                        )

            elif column_action_type in {
                "split",
                "merge",
                "derive",
            }:
                for target_column in target_columns:
                    if target_column not in predicted_columns:
                        _append_unique(
                            invalid_references,
                            invalid_seen,
                            {
                                "object": "target_column",
                                "table": table,
                                "column": target_column,
                                "action": column_action_type,
                                "reason": (
                                    "target_column_not_found_"
                                    "in_predicted_rdb"
                                ),
                            },
                        )

    # -------------------------------------------------
    # 3. Detect table and column conflicts
    # -------------------------------------------------

    for table, actions in table_action_types.items():
        if "map" in actions and "create" in actions:
            _append_unique(
                conflicting_operations,
                conflict_seen,
                {
                    "object": "table",
                    "table": table,
                    "actions": sorted(actions),
                    "reason": (
                        "table_mapped_and_created"
                    ),
                },
            )

    for (
        table,
        target_column,
    ), actions in target_column_actions.items():
        if "drop" in actions and len(actions) > 1:
            _append_unique(
                conflicting_operations,
                conflict_seen,
                {
                    "object": "target_column",
                    "table": table,
                    "column": target_column,
                    "actions": sorted(actions),
                    "reason": (
                        "column_dropped_and_modified"
                    ),
                },
            )

        if "map" in actions and "create" in actions:
            _append_unique(
                conflicting_operations,
                conflict_seen,
                {
                    "object": "target_column",
                    "table": table,
                    "column": target_column,
                    "actions": sorted(actions),
                    "reason": (
                        "column_mapped_and_created"
                    ),
                },
            )

    # -------------------------------------------------
    # 4. Check decision/action consistency
    # -------------------------------------------------

    if (
        source_decision == "create_table"
        and not created_tables
    ):
        _append_unique(
            conflicting_operations,
            conflict_seen,
            {
                "object": "source_decision",
                "decision": source_decision,
                "reason": (
                    "create_table_decision_without_"
                    "create_table_action"
                ),
            },
        )

    if (
        source_decision == "extend_table"
        and not mapped_tables
    ):
        _append_unique(
            conflicting_operations,
            conflict_seen,
            {
                "object": "source_decision",
                "decision": source_decision,
                "reason": (
                    "extend_table_decision_without_"
                    "mapped_table"
                ),
            },
        )

    if source_decision == "no_schema_change":
        schema_change_actions = {
            "create",
            "drop",
            "split",
            "merge",
            "derive",
        }

        if (
            created_tables
            or schema_change_actions.intersection(
                all_column_action_types
            )
        ):
            _append_unique(
                conflicting_operations,
                conflict_seen,
                {
                    "object": "source_decision",
                    "decision": source_decision,
                    "reason": (
                        "no_schema_change_contains_"
                        "schema_change_actions"
                    ),
                },
            )

    # -------------------------------------------------
    # 5. Validate constraint actions
    # -------------------------------------------------

    constraint_actions = predicted_proposal.get(
        "constraint_actions",
        [],
    )

    if not isinstance(constraint_actions, list):
        raw_valid = False

        _append_unique(
            invalid_references,
            invalid_seen,
            {
                "object": "constraint_actions",
                "reason": (
                    "constraint_actions_must_be_list"
                ),
            },
        )

        constraint_actions = []

    existing_primary_keys = (
        _collect_column_constraints(
            existing_constraints,
            "primary_keys",
        )
    )
    predicted_primary_keys = (
        _collect_column_constraints(
            predicted_constraints,
            "primary_keys",
        )
    )

    existing_foreign_keys = (
        _collect_foreign_keys(
            existing_constraints
        )
    )
    predicted_foreign_keys = (
        _collect_foreign_keys(
            predicted_constraints
        )
    )

    existing_unique_constraints = (
        _collect_column_constraints(
            existing_constraints,
            "unique_constraints",
        )
    )
    predicted_unique_constraints = (
        _collect_column_constraints(
            predicted_constraints,
            "unique_constraints",
        )
    )

    existing_indexes = (
        _collect_column_constraints(
            existing_constraints,
            "indexes",
        )
    )
    predicted_indexes = (
        _collect_column_constraints(
            predicted_constraints,
            "indexes",
        )
    )

    seen_constraint_actions: set[
        tuple[Any, ...]
    ] = set()

    for constraint_index, constraint_action in enumerate(
        constraint_actions
    ):
        if not isinstance(constraint_action, dict):
            raw_valid = False

            _append_unique(
                invalid_references,
                invalid_seen,
                {
                    "object": "constraint_action",
                    "index": constraint_index,
                    "reason": (
                        "constraint_action_must_be_object"
                    ),
                },
            )
            continue

        action = constraint_action.get("action")
        table = constraint_action.get("table")
        columns = constraint_action.get(
            "columns",
            [],
        )

        if action not in CONSTRAINT_ACTION_TYPES:
            raw_valid = False

            _append_unique(
                invalid_references,
                invalid_seen,
                {
                    "object": "constraint_action",
                    "index": constraint_index,
                    "action": action,
                    "reason": (
                        "unsupported_constraint_action"
                    ),
                },
            )
            continue

        if not isinstance(table, str) or not table:
            raw_valid = False

            _append_unique(
                invalid_references,
                invalid_seen,
                {
                    "object": "constraint_action",
                    "index": constraint_index,
                    "action": action,
                    "reason": "missing_table",
                },
            )
            continue

        if not _is_string_list(columns):
            raw_valid = False

            _append_unique(
                invalid_references,
                invalid_seen,
                {
                    "object": "constraint_action",
                    "table": table,
                    "action": action,
                    "columns": columns,
                    "reason": (
                        "columns_must_be_a_string_list"
                    ),
                },
            )
            continue

        if table not in predicted_tables:
            _append_unique(
                invalid_references,
                invalid_seen,
                {
                    "object": "constraint_table",
                    "table": table,
                    "action": action,
                    "reason": (
                        "table_not_found_in_predicted_rdb"
                    ),
                },
            )
        else:
            predicted_columns = _get_table_columns(
                predicted_tables,
                table,
            )

            for column in columns:
                if column not in predicted_columns:
                    _append_unique(
                        invalid_references,
                        invalid_seen,
                        {
                            "object": (
                                "constraint_column"
                            ),
                            "table": table,
                            "column": column,
                            "action": action,
                            "reason": (
                                "column_not_found_"
                                "in_predicted_rdb"
                            ),
                        },
                    )

        # ---------------------------------------------
        # Primary key
        # ---------------------------------------------

        if action == "add_primary_key":
            constraint_key = (
                action,
                table,
                tuple(columns),
            )

            if constraint_key in seen_constraint_actions:
                _append_unique(
                    duplicate_definitions,
                    duplicate_seen,
                    {
                        "object": "primary_key",
                        "table": table,
                        "columns": columns,
                    },
                )

            seen_constraint_actions.add(
                constraint_key
            )

            primary_key_fact = (
                table,
                tuple(columns),
            )

            if primary_key_fact in existing_primary_keys:
                _append_unique(
                    duplicate_definitions,
                    duplicate_seen,
                    {
                        "object": "primary_key",
                        "table": table,
                        "columns": columns,
                        "reason": (
                            "primary_key_already_exists"
                        ),
                    },
                )

            existing_table_primary_keys = {
                key
                for key in existing_primary_keys
                if key[0] == table
            }

            if (
                existing_table_primary_keys
                and primary_key_fact
                not in existing_table_primary_keys
            ):
                _append_unique(
                    conflicting_operations,
                    conflict_seen,
                    {
                        "object": "primary_key",
                        "table": table,
                        "columns": columns,
                        "reason": (
                            "table_already_has_"
                            "different_primary_key"
                        ),
                    },
                )

            if primary_key_fact not in predicted_primary_keys:
                _append_unique(
                    conflicting_operations,
                    conflict_seen,
                    {
                        "object": "primary_key",
                        "table": table,
                        "columns": columns,
                        "reason": (
                            "primary_key_action_not_applied"
                        ),
                    },
                )

        # ---------------------------------------------
        # Foreign key
        # ---------------------------------------------

        elif action == "add_foreign_key":
            referenced_table = constraint_action.get(
                "referenced_table"
            )
            referenced_columns = constraint_action.get(
                "referenced_columns",
                [],
            )

            if (
                not isinstance(referenced_table, str)
                or not referenced_table
            ):
                raw_valid = False

                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "foreign_key",
                        "table": table,
                        "columns": columns,
                        "reason": (
                            "missing_referenced_table"
                        ),
                    },
                )
                continue

            if not _is_string_list(
                referenced_columns
            ):
                raw_valid = False

                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "foreign_key",
                        "table": table,
                        "columns": columns,
                        "referenced_table": (
                            referenced_table
                        ),
                        "referenced_columns": (
                            referenced_columns
                        ),
                        "reason": (
                            "referenced_columns_must_"
                            "be_a_string_list"
                        ),
                    },
                )
                continue

            foreign_key_fact = _foreign_key_key(
                table=table,
                columns=columns,
                referenced_table=referenced_table,
                referenced_columns=referenced_columns,
            )

            constraint_key = (
                action,
                *foreign_key_fact,
            )

            if constraint_key in seen_constraint_actions:
                _append_unique(
                    duplicate_definitions,
                    duplicate_seen,
                    {
                        "object": "foreign_key",
                        "table": table,
                        "columns": columns,
                        "referenced_table": (
                            referenced_table
                        ),
                        "referenced_columns": (
                            referenced_columns
                        ),
                    },
                )

            seen_constraint_actions.add(
                constraint_key
            )

            broken_reasons: list[str] = []

            if len(columns) != len(
                referenced_columns
            ):
                broken_reasons.append(
                    "foreign_key_arity_mismatch"
                )

            if referenced_table not in predicted_tables:
                broken_reasons.append(
                    "referenced_table_not_found"
                )

                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "table",
                        "table": referenced_table,
                        "reason": (
                            "referenced_table_not_found_"
                            "in_predicted_rdb"
                        ),
                    },
                )
            else:
                target_columns = _get_table_columns(
                    predicted_tables,
                    referenced_table,
                )

                for referenced_column in referenced_columns:
                    if (
                        referenced_column
                        not in target_columns
                    ):
                        broken_reasons.append(
                            "referenced_column_not_found:"
                            f"{referenced_column}"
                        )

            if table in predicted_tables:
                source_table_columns = (
                    _get_table_columns(
                        predicted_tables,
                        table,
                    )
                )

                for column in columns:
                    if column not in source_table_columns:
                        broken_reasons.append(
                            "source_column_not_found:"
                            f"{column}"
                        )

            if (
                table in predicted_tables
                and referenced_table
                in predicted_tables
                and len(columns)
                == len(referenced_columns)
            ):
                for (
                    source_column,
                    referenced_column,
                ) in zip(
                    columns,
                    referenced_columns,
                ):
                    source_type = _get_column_type(
                        predicted_tables,
                        table,
                        source_column,
                    )
                    target_type = _get_column_type(
                        predicted_tables,
                        referenced_table,
                        referenced_column,
                    )

                    if not _types_compatible(
                        source_type,
                        target_type,
                    ):
                        broken_reasons.append(
                            "incompatible_types:"
                            f"{source_column}={source_type},"
                            f"{referenced_column}={target_type}"
                        )

            if broken_reasons:
                _append_unique(
                    broken_foreign_keys,
                    broken_fk_seen,
                    {
                        "table": table,
                        "columns": columns,
                        "referenced_table": (
                            referenced_table
                        ),
                        "referenced_columns": (
                            referenced_columns
                        ),
                        "reasons": broken_reasons,
                    },
                )

            if foreign_key_fact in existing_foreign_keys:
                _append_unique(
                    duplicate_definitions,
                    duplicate_seen,
                    {
                        "object": "foreign_key",
                        "table": table,
                        "columns": columns,
                        "referenced_table": (
                            referenced_table
                        ),
                        "referenced_columns": (
                            referenced_columns
                        ),
                        "reason": (
                            "foreign_key_already_exists"
                        ),
                    },
                )

            if foreign_key_fact not in predicted_foreign_keys:
                _append_unique(
                    conflicting_operations,
                    conflict_seen,
                    {
                        "object": "foreign_key",
                        "table": table,
                        "columns": columns,
                        "referenced_table": (
                            referenced_table
                        ),
                        "referenced_columns": (
                            referenced_columns
                        ),
                        "reason": (
                            "foreign_key_action_not_applied"
                        ),
                    },
                )

        # ---------------------------------------------
        # Unique constraint
        # ---------------------------------------------

        elif action == "add_unique_constraint":
            constraint_fact = (
                table,
                tuple(columns),
            )

            constraint_key = (
                action,
                table,
                tuple(columns),
            )

            if constraint_key in seen_constraint_actions:
                _append_unique(
                    duplicate_definitions,
                    duplicate_seen,
                    {
                        "object": "unique_constraint",
                        "table": table,
                        "columns": columns,
                    },
                )

            seen_constraint_actions.add(
                constraint_key
            )

            if (
                constraint_fact
                in existing_unique_constraints
            ):
                _append_unique(
                    duplicate_definitions,
                    duplicate_seen,
                    {
                        "object": "unique_constraint",
                        "table": table,
                        "columns": columns,
                        "reason": (
                            "unique_constraint_"
                            "already_exists"
                        ),
                    },
                )

            if (
                constraint_fact
                not in predicted_unique_constraints
            ):
                _append_unique(
                    conflicting_operations,
                    conflict_seen,
                    {
                        "object": "unique_constraint",
                        "table": table,
                        "columns": columns,
                        "reason": (
                            "unique_constraint_action_"
                            "not_applied"
                        ),
                    },
                )

        # ---------------------------------------------
        # Index
        # ---------------------------------------------

        elif action == "add_index":
            constraint_fact = (
                table,
                tuple(columns),
            )

            constraint_key = (
                action,
                table,
                tuple(columns),
            )

            if constraint_key in seen_constraint_actions:
                _append_unique(
                    duplicate_definitions,
                    duplicate_seen,
                    {
                        "object": "index",
                        "table": table,
                        "columns": columns,
                    },
                )

            seen_constraint_actions.add(
                constraint_key
            )

            if constraint_fact in existing_indexes:
                _append_unique(
                    duplicate_definitions,
                    duplicate_seen,
                    {
                        "object": "index",
                        "table": table,
                        "columns": columns,
                        "reason": "index_already_exists",
                    },
                )

            if constraint_fact not in predicted_indexes:
                _append_unique(
                    conflicting_operations,
                    conflict_seen,
                    {
                        "object": "index",
                        "table": table,
                        "columns": columns,
                        "reason": (
                            "index_action_not_applied"
                        ),
                    },
                )

    # -------------------------------------------------
    # 6. Validate final predicted RDB primary keys
    # -------------------------------------------------

    predicted_primary_key_data = (
        predicted_constraints.get(
            "primary_keys",
            {},
        )
    )

    if isinstance(predicted_primary_key_data, dict):
        for table, columns in (
            predicted_primary_key_data.items()
        ):
            if table not in predicted_tables:
                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "primary_key_table",
                        "table": table,
                        "reason": (
                            "table_not_found_in_"
                            "predicted_rdb"
                        ),
                    },
                )
                continue

            if not _is_string_list(columns):
                raw_valid = False

                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "primary_key",
                        "table": table,
                        "columns": columns,
                        "reason": (
                            "primary_key_columns_must_"
                            "be_a_string_list"
                        ),
                    },
                )
                continue

            table_columns = _get_table_columns(
                predicted_tables,
                table,
            )

            for column in columns:
                if column not in table_columns:
                    _append_unique(
                        invalid_references,
                        invalid_seen,
                        {
                            "object": "primary_key_column",
                            "table": table,
                            "column": column,
                            "reason": (
                                "column_not_found_in_"
                                "predicted_rdb"
                            ),
                        },
                    )

    # -------------------------------------------------
    # 7. Validate final predicted RDB foreign keys
    # -------------------------------------------------

    predicted_foreign_key_data = (
        predicted_constraints.get(
            "foreign_keys",
            {},
        )
    )

    actual_foreign_keys_seen: set[
        tuple[
            str,
            tuple[str, ...],
            str,
            tuple[str, ...],
        ]
    ] = set()

    if isinstance(predicted_foreign_key_data, dict):
        for table, foreign_keys in (
            predicted_foreign_key_data.items()
        ):
            if not isinstance(foreign_keys, list):
                raw_valid = False

                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": "foreign_keys",
                        "table": table,
                        "reason": (
                            "foreign_keys_must_be_list"
                        ),
                    },
                )
                continue

            for foreign_key in foreign_keys:
                if not isinstance(foreign_key, dict):
                    raw_valid = False

                    _append_unique(
                        invalid_references,
                        invalid_seen,
                        {
                            "object": "foreign_key",
                            "table": table,
                            "reason": (
                                "foreign_key_must_be_object"
                            ),
                        },
                    )
                    continue

                columns = foreign_key.get(
                    "columns",
                    [],
                )
                referenced_table = foreign_key.get(
                    "referenced_table"
                )
                referenced_columns = foreign_key.get(
                    "referenced_columns",
                    [],
                )

                if (
                    not _is_string_list(columns)
                    or not isinstance(
                        referenced_table,
                        str,
                    )
                    or not referenced_table
                    or not _is_string_list(
                        referenced_columns
                    )
                ):
                    raw_valid = False

                    _append_unique(
                        broken_foreign_keys,
                        broken_fk_seen,
                        {
                            "table": table,
                            "columns": columns,
                            "referenced_table": (
                                referenced_table
                            ),
                            "referenced_columns": (
                                referenced_columns
                            ),
                            "reasons": [
                                "malformed_foreign_key"
                            ],
                        },
                    )
                    continue

                foreign_key_fact = _foreign_key_key(
                    table=table,
                    columns=columns,
                    referenced_table=referenced_table,
                    referenced_columns=referenced_columns,
                )

                if (
                    foreign_key_fact
                    in actual_foreign_keys_seen
                ):
                    _append_unique(
                        duplicate_definitions,
                        duplicate_seen,
                        {
                            "object": "foreign_key",
                            "table": table,
                            "columns": columns,
                            "referenced_table": (
                                referenced_table
                            ),
                            "referenced_columns": (
                                referenced_columns
                            ),
                            "reason": (
                                "duplicate_foreign_key_"
                                "in_predicted_rdb"
                            ),
                        },
                    )

                actual_foreign_keys_seen.add(
                    foreign_key_fact
                )

                broken_reasons: list[str] = []

                if table not in predicted_tables:
                    broken_reasons.append(
                        "source_table_not_found"
                    )

                    _append_unique(
                        invalid_references,
                        invalid_seen,
                        {
                            "object": "table",
                            "table": table,
                            "reason": (
                                "foreign_key_source_table_"
                                "not_found"
                            ),
                        },
                    )
                else:
                    source_table_columns = (
                        _get_table_columns(
                            predicted_tables,
                            table,
                        )
                    )

                    for column in columns:
                        if (
                            column
                            not in source_table_columns
                        ):
                            broken_reasons.append(
                                "source_column_not_found:"
                                f"{column}"
                            )

                if referenced_table not in predicted_tables:
                    broken_reasons.append(
                        "referenced_table_not_found"
                    )

                    _append_unique(
                        invalid_references,
                        invalid_seen,
                        {
                            "object": "table",
                            "table": referenced_table,
                            "reason": (
                                "foreign_key_referenced_"
                                "table_not_found"
                            ),
                        },
                    )
                else:
                    target_table_columns = (
                        _get_table_columns(
                            predicted_tables,
                            referenced_table,
                        )
                    )

                    for column in referenced_columns:
                        if (
                            column
                            not in target_table_columns
                        ):
                            broken_reasons.append(
                                "referenced_column_not_found:"
                                f"{column}"
                            )

                if len(columns) != len(
                    referenced_columns
                ):
                    broken_reasons.append(
                        "foreign_key_arity_mismatch"
                    )

                if (
                    table in predicted_tables
                    and referenced_table
                    in predicted_tables
                    and len(columns)
                    == len(referenced_columns)
                ):
                    for (
                        source_column,
                        target_column,
                    ) in zip(
                        columns,
                        referenced_columns,
                    ):
                        source_type = _get_column_type(
                            predicted_tables,
                            table,
                            source_column,
                        )
                        target_type = _get_column_type(
                            predicted_tables,
                            referenced_table,
                            target_column,
                        )

                        if not _types_compatible(
                            source_type,
                            target_type,
                        ):
                            broken_reasons.append(
                                "incompatible_types:"
                                f"{source_column}={source_type},"
                                f"{target_column}={target_type}"
                            )

                if broken_reasons:
                    _append_unique(
                        broken_foreign_keys,
                        broken_fk_seen,
                        {
                            "table": table,
                            "columns": columns,
                            "referenced_table": (
                                referenced_table
                            ),
                            "referenced_columns": (
                                referenced_columns
                            ),
                            "reasons": broken_reasons,
                        },
                    )

    # -------------------------------------------------
    # 8. Validate predicted unique constraints/indexes
    # -------------------------------------------------

    for constraint_name, object_name in [
        (
            "unique_constraints",
            "unique_constraint",
        ),
        (
            "indexes",
            "index",
        ),
    ]:
        constraint_data = predicted_constraints.get(
            constraint_name,
            {},
        )

        if not isinstance(constraint_data, dict):
            continue

        seen_definitions: set[
            tuple[str, tuple[str, ...]]
        ] = set()

        for table, definitions in constraint_data.items():
            if table not in predicted_tables:
                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": f"{object_name}_table",
                        "table": table,
                        "reason": (
                            "table_not_found_in_"
                            "predicted_rdb"
                        ),
                    },
                )
                continue

            if not isinstance(definitions, list):
                raw_valid = False

                _append_unique(
                    invalid_references,
                    invalid_seen,
                    {
                        "object": object_name,
                        "table": table,
                        "reason": (
                            f"{constraint_name}_must_be_list"
                        ),
                    },
                )
                continue

            table_columns = _get_table_columns(
                predicted_tables,
                table,
            )

            for columns in definitions:
                if not _is_string_list(columns):
                    raw_valid = False

                    _append_unique(
                        invalid_references,
                        invalid_seen,
                        {
                            "object": object_name,
                            "table": table,
                            "columns": columns,
                            "reason": (
                                "columns_must_be_a_"
                                "string_list"
                            ),
                        },
                    )
                    continue

                definition_key = (
                    table,
                    tuple(columns),
                )

                if definition_key in seen_definitions:
                    _append_unique(
                        duplicate_definitions,
                        duplicate_seen,
                        {
                            "object": object_name,
                            "table": table,
                            "columns": columns,
                            "reason": (
                                f"duplicate_{object_name}_"
                                "in_predicted_rdb"
                            ),
                        },
                    )

                seen_definitions.add(
                    definition_key
                )

                for column in columns:
                    if column not in table_columns:
                        _append_unique(
                            invalid_references,
                            invalid_seen,
                            {
                                "object": (
                                    f"{object_name}_column"
                                ),
                                "table": table,
                                "column": column,
                                "reason": (
                                    "column_not_found_in_"
                                    "predicted_rdb"
                                ),
                            },
                        )

    checked_valid = (
        raw_valid
        and not invalid_references
        and not broken_foreign_keys
        and not duplicate_definitions
        and not conflicting_operations
    )

    return {
        "raw_valid": raw_valid,
        "checked_valid": checked_valid,
        "invalid_references": invalid_references,
        "broken_foreign_keys": broken_foreign_keys,
        "duplicate_definitions": duplicate_definitions,
        "conflicting_operations": conflicting_operations,
    }