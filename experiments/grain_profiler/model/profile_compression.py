from __future__ import annotations

from typing import Any


GRAIN_ROLES = {
    "identifier",
    "reference",
    "attribute",
    "measure",
    "temporal",
    "unknown",
}


def compact_profile(
    profile: dict[str, Any] | None,
    *,
    table_name: str | None = None,
) -> dict[str, Any]:
    """Remove profile fields that duplicate schema, samples, or explanations."""

    profile = profile or {}
    raw_table = profile.get("table", {})
    entity = _short_text(
        raw_table.get("entity") or table_name or "unknown",
        max_words=4,
    )
    row_grain = _normalise_row_grain(raw_table.get("row_grain"), entity)

    columns: dict[str, dict[str, str]] = {}
    for column_name, raw_column in profile.get("columns", {}).items():
        semantic_type = str(raw_column.get("semantic_type") or "unknown")
        grain_role = str(raw_column.get("grain_role") or "")
        if grain_role not in GRAIN_ROLES:
            grain_role = infer_grain_role(column_name, semantic_type)
        columns[column_name] = {
            "semantic_type": semantic_type,
            "business_concept": _short_text(
                raw_column.get("business_concept") or column_name,
                max_words=4,
            ),
            "grain_role": grain_role,
        }

    return {
        "table": {
            "entity": entity,
            "role": str(raw_table.get("role") or "unknown"),
            "row_grain": row_grain,
        },
        "columns": columns,
    }


def compact_profiles(profiles: dict[str, Any] | None) -> dict[str, Any]:
    """Apply the same compact representation to every existing RDB table."""

    profiles = profiles or {}
    raw_tables = profiles.get("tables", profiles)
    compact_tables = {
        table_name: compact_profile(table_profile, table_name=table_name)
        for table_name, table_profile in raw_tables.items()
        if isinstance(table_profile, dict)
    }
    return {
        "database": profiles.get("database"),
        "tables": compact_tables,
    }


def infer_grain_role(column_name: str, semantic_type: str) -> str:
    if semantic_type == "identifier":
        return "identifier"
    if semantic_type == "foreign_key_candidate":
        return "reference"
    if semantic_type in {"money", "quantity"}:
        return "measure"
    if semantic_type in {"date", "timestamp"}:
        return "temporal"
    if semantic_type == "unknown" and column_name.lower().endswith("_id"):
        return "reference"
    return "attribute"


def _normalise_row_grain(value: Any, entity: str) -> str:
    text = _short_text(value, max_words=6)
    if not text or text == "unknown":
        return _short_text(f"one row per {entity}", max_words=6)
    if text.lower().startswith("one row per"):
        return text
    return _short_text(f"one row per {text}", max_words=6)


def _short_text(value: Any, *, max_words: int) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return "unknown"
    return " ".join(text.split()[:max_words])
