from __future__ import annotations

from copy import deepcopy
from typing import Any


FOREIGN_KEY_SECTION = "foreign_keys"


def filter_constraints_to_tables(
    existing_constraints: dict[str, Any],
    selected_tables: list[str] | set[str],
) -> dict[str, Any]:
    """Return the constraint subgraph induced by ``selected_tables``.

    Table-scoped constraint sections retain only selected source tables.
    Foreign keys additionally require their referenced table to be selected,
    so the Evolutor never receives a dangling relationship to a hidden table.
    The input object is not mutated.
    """

    selected = set(selected_tables)
    has_envelope = isinstance(existing_constraints.get("constraints"), dict)
    raw_body = (
        existing_constraints["constraints"]
        if has_envelope
        else existing_constraints
    )

    filtered_body: dict[str, Any] = {}

    for section_name, section_value in raw_body.items():
        if not isinstance(section_value, dict):
            filtered_body[section_name] = deepcopy(section_value)
            continue

        if section_name == FOREIGN_KEY_SECTION:
            filtered_foreign_keys: dict[str, list[dict[str, Any]]] = {}

            for source_table, foreign_keys in section_value.items():
                if source_table not in selected or not isinstance(foreign_keys, list):
                    continue

                retained = [
                    deepcopy(foreign_key)
                    for foreign_key in foreign_keys
                    if (
                        isinstance(foreign_key, dict)
                        and foreign_key.get("referenced_table") in selected
                    )
                ]

                if retained:
                    filtered_foreign_keys[source_table] = retained

            filtered_body[section_name] = filtered_foreign_keys
            continue

        filtered_body[section_name] = {
            table_name: deepcopy(definitions)
            for table_name, definitions in section_value.items()
            if table_name in selected
        }

    if not has_envelope:
        return filtered_body

    return {
        **{
            key: deepcopy(value)
            for key, value in existing_constraints.items()
            if key != "constraints"
        },
        "constraints": filtered_body,
    }
