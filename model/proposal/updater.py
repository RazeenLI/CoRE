from __future__ import annotations

from copy import deepcopy
from typing import Any


CONSTRAINT_SECTIONS = [
    "primary_keys",
    "foreign_keys",
    "unique_constraints",
    "check_constraints",
    "indexes",
    "inferred_constraints",
]


def apply_update_plan_to_existing_parts(
    schema: dict[str, Any],
    constraints: dict[str, Any],
    profiles: dict[str, Any] | None,
    update_plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """
    Apply a partial update plan to separated existing RDB parts.

    Important:
    - This function assumes update_plan is already valid.
    - It does NOT repair schema problems such as empty column_order.
    - It does NOT regenerate profiles.
    - Profile update currently only merges aliases without duplication.
    """
    if not isinstance(schema, dict):
        raise TypeError("schema must be a dict.")

    if not isinstance(constraints, dict):
        raise TypeError("constraints must be a dict.")

    if profiles is not None and not isinstance(profiles, dict):
        raise TypeError("profiles must be a dict or None.")

    if not isinstance(update_plan, dict):
        raise TypeError("update_plan must be a dict.")

    before_partial = update_plan.get("before", {})
    after_partial = update_plan.get("after", update_plan)

    before_tables = _get_partial_schema_tables(before_partial)
    after_tables = _get_partial_schema_tables(after_partial)

    affected_tables = set(before_tables) | set(after_tables)
    removed_tables = set(before_tables) - set(after_tables)

    updated_schema = _apply_schema_update(
        schema=schema,
        after_tables=after_tables,
        removed_tables=removed_tables,
    )

    updated_constraints = _apply_constraints_update(
        constraints=constraints,
        before_partial=before_partial,
        after_partial=after_partial,
        affected_tables=affected_tables,
        removed_tables=removed_tables,
    )

    updated_profiles = _apply_profiles_update_aliases_only(
        profiles=profiles,
        before_partial=before_partial,
        after_partial=after_partial,
        removed_tables=removed_tables,
    )

    return updated_schema, updated_constraints, updated_profiles


def _get_partial_schema_tables(partial_rdb: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(partial_rdb, dict):
        return {}

    schema = partial_rdb.get("schema", {})
    if not isinstance(schema, dict):
        return {}

    tables = schema.get("tables", {})
    if not isinstance(tables, dict):
        raise ValueError("partial schema.tables must be a dict.")

    return tables


def _apply_schema_update(
    schema: dict[str, Any],
    after_tables: dict[str, Any],
    removed_tables: set[str],
) -> dict[str, Any]:
    """
    Apply schema update exactly.

    No column_order repair.
    No schema normalization.
    The incoming after table schema is assumed to be valid.
    """
    updated_schema = deepcopy(schema)

    target_tables = updated_schema.setdefault("tables", {})
    if not isinstance(target_tables, dict):
        raise ValueError("schema.tables must be a dict.")

    for table_name in removed_tables:
        target_tables.pop(table_name, None)

    for table_name, table_schema in after_tables.items():
        target_tables[table_name] = deepcopy(table_schema)

    return updated_schema


def _apply_constraints_update(
    constraints: dict[str, Any],
    before_partial: dict[str, Any],
    after_partial: dict[str, Any],
    affected_tables: set[str],
    removed_tables: set[str],
) -> dict[str, Any]:
    """
    Apply constraints update by table.

    For each constraint section:
    - if table appears in after section, replace that table's constraints
    - if table appeared before but disappeared after, remove that table's constraints
    - unrelated tables are untouched
    """
    updated_constraints = deepcopy(constraints)

    target_body = _get_constraint_body(updated_constraints)
    before_body = _extract_partial_constraint_body(before_partial)
    after_body = _extract_partial_constraint_body(after_partial)

    for section in CONSTRAINT_SECTIONS:
        target_section = target_body.setdefault(section, {})

        if not isinstance(target_section, dict):
            raise ValueError(f"constraints.{section} must be a dict.")

        before_section = before_body.get(section, {})
        after_section = after_body.get(section, {})

        if not isinstance(before_section, dict):
            before_section = {}

        if not isinstance(after_section, dict):
            after_section = {}

        for table_name in removed_tables:
            target_section.pop(table_name, None)

        for table_name in affected_tables:
            if table_name in after_section:
                target_section[table_name] = deepcopy(after_section[table_name])
            elif table_name in before_section:
                target_section.pop(table_name, None)

    return updated_constraints


def _get_constraint_body(constraints: dict[str, Any]) -> dict[str, Any]:
    """
    Supports both:

    {
        "database": "...",
        "constraints": {
            "primary_keys": {...}
        }
    }

    and:

    {
        "primary_keys": {...}
    }
    """
    if "constraints" in constraints:
        body = constraints.setdefault("constraints", {})
    else:
        body = constraints

    if not isinstance(body, dict):
        raise ValueError("constraints body must be a dict.")

    for section in CONSTRAINT_SECTIONS:
        body.setdefault(section, {})

    return body


def _extract_partial_constraint_body(partial_rdb: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(partial_rdb, dict):
        return {}

    constraints_obj = partial_rdb.get("constraints", {})
    if not isinstance(constraints_obj, dict):
        return {}

    if "constraints" in constraints_obj and isinstance(constraints_obj["constraints"], dict):
        return constraints_obj["constraints"]

    return constraints_obj


def _apply_profiles_update_aliases_only(
    profiles: dict[str, Any] | None,
    before_partial: dict[str, Any],
    after_partial: dict[str, Any],
    removed_tables: set[str],
) -> dict[str, Any] | None:
    """
    Update profiles conservatively.

    Current policy:
    - remove profiles for removed tables
    - merge table aliases without duplication
    - merge column aliases without duplication

    TODO:
    - decide whether table.summary should be updated
    - decide whether table.entity / table.role should be updated
    - decide whether column.meaning should be updated
    - decide whether column.semantic_type should be updated
    - decide whether column.business_concept should be updated
    - decide whether value_patterns should be merged or recomputed
    """
    if profiles is None:
        return None

    updated_profiles = deepcopy(profiles)

    target_profile_tables = updated_profiles.setdefault("tables", {})
    if not isinstance(target_profile_tables, dict):
        raise ValueError("profiles.tables must be a dict.")

    for table_name in removed_tables:
        target_profile_tables.pop(table_name, None)

    after_profile_tables = _get_partial_profile_tables(after_partial)

    # If update_plan does not contain profiles, do nothing else.
    if not after_profile_tables:
        return updated_profiles

    for table_name, after_table_profile in after_profile_tables.items():
        if table_name not in target_profile_tables:
            # TODO:
            # New table profile creation policy is not finalized.
            # For now, copy the after profile only if the update plan explicitly provides it.
            target_profile_tables[table_name] = deepcopy(after_table_profile)
            continue

        target_table_profile = target_profile_tables[table_name]

        _merge_table_aliases_only(
            target_table_profile=target_table_profile,
            source_table_profile=after_table_profile,
        )

        _merge_column_aliases_only(
            target_table_profile=target_table_profile,
            source_table_profile=after_table_profile,
        )

    # before_partial is currently unused for profile merging.
    # It is kept in the function signature because profile diff logic may need it later.
    _ = before_partial

    return updated_profiles


def _get_partial_profile_tables(partial_rdb: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(partial_rdb, dict):
        return {}

    profiles = partial_rdb.get("profiles", {})
    if not isinstance(profiles, dict):
        return {}

    tables = profiles.get("tables", {})
    if not isinstance(tables, dict):
        raise ValueError("partial profiles.tables must be a dict.")

    return tables


def _merge_table_aliases_only(
    target_table_profile: dict[str, Any],
    source_table_profile: dict[str, Any],
) -> None:
    target_table_meta = target_table_profile.setdefault("table", {})
    source_table_meta = source_table_profile.get("table", {})

    if not isinstance(target_table_meta, dict):
        raise ValueError("target table profile.table must be a dict.")

    if not isinstance(source_table_meta, dict):
        return

    source_aliases = source_table_meta.get("aliases", [])
    if source_aliases:
        target_table_meta["aliases"] = _merge_alias_lists(
            target_table_meta.get("aliases", []),
            source_aliases,
        )


def _merge_column_aliases_only(
    target_table_profile: dict[str, Any],
    source_table_profile: dict[str, Any],
) -> None:
    target_columns = target_table_profile.setdefault("columns", {})
    source_columns = source_table_profile.get("columns", {})

    if not isinstance(target_columns, dict):
        raise ValueError("target table profile.columns must be a dict.")

    if not isinstance(source_columns, dict):
        return

    for column_name, source_column_profile in source_columns.items():
        if not isinstance(source_column_profile, dict):
            continue

        if column_name not in target_columns:
            # TODO:
            # New column profile creation policy is not finalized.
            # For now, copy the after column profile only if the update plan explicitly provides it.
            target_columns[column_name] = deepcopy(source_column_profile)
            continue

        target_column_profile = target_columns[column_name]
        if not isinstance(target_column_profile, dict):
            continue

        source_aliases = source_column_profile.get("aliases", [])
        if source_aliases:
            target_column_profile["aliases"] = _merge_alias_lists(
                target_column_profile.get("aliases", []),
                source_aliases,
            )


def _merge_alias_lists(
    existing_aliases: Any,
    new_aliases: Any,
) -> list[str]:
    if not isinstance(existing_aliases, list):
        existing_aliases = []

    if not isinstance(new_aliases, list):
        new_aliases = []

    merged: list[str] = []
    seen: set[str] = set()

    for alias in existing_aliases + new_aliases:
        if not isinstance(alias, str):
            continue

        normalized = alias.strip()
        if not normalized:
            continue

        key = normalized.lower()
        if key in seen:
            continue

        seen.add(key)
        merged.append(normalized)

    return merged