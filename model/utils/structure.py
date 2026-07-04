

from typing import Any


def get_column_values(
    rows: list[dict[str, Any]],
    column_name: str,
) -> list[Any]:
    return [row.get(column_name) for row in rows]