# utils/io.py

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_rdb(
    rdb_path: str | Path, 
    sample_num: int = 0,
) -> dict[str, Any]:
    """
    Load an existing RDB folder.

    Expected folder structure:
        rdb_path/
          schema.json
          constraints.json
          tables/
            <table_name>.csv

    Args:
        rdb_path:
            Path to the RDB folder.
        sample_num:
            Maximum number of sample rows to load per table.
            If the CSV has fewer rows than sample_num, all rows are loaded.

    Returns:
        existing_rdb:
            {
                "schema": dict,
                "constraints": dict,
                "sample_values": dict[str, list[dict[str, Any]]]
            }
    """
    rdb_path = Path(rdb_path)

    # if sample_num < 0:
    #     raise ValueError("sample_num must be >= 0")

    schema_path = rdb_path / "schema.json"
    constraints_path = rdb_path / "constraints.json"
    tables_dir = rdb_path / "tables"

    if not rdb_path.exists():
        raise FileNotFoundError(f"RDB path does not exist: {rdb_path}")

    if not schema_path.exists():
        raise FileNotFoundError(f"schema.json not found: {schema_path}")

    if not constraints_path.exists():
        raise FileNotFoundError(f"constraints.json not found: {constraints_path}")

    if not tables_dir.exists():
        raise FileNotFoundError(f"tables directory not found: {tables_dir}")

    schema = load_json(schema_path)
    constraints = load_json(constraints_path)

    tables = schema.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("schema.json must contain a dict field: 'tables'")

    sample_values: dict[str, list[dict[str, Any]]] = {}

    for table_name in tables.keys():
        csv_path = tables_dir / f"{table_name}.csv"
        sample_values[table_name] = load_csv_sample(csv_path, sample_num)

    existing_rdb: dict[str, Any] = {
        "schema": schema,
        "constraints": constraints,
        "sample_values": sample_values,
    }

    return existing_rdb

def load_table(
    table_path: str | Path,
    sample_num: int = 0,
) -> dict[str, Any]:
    table_path = Path(table_path)

    schema_path = table_path / "schema.json"
    csv_path = table_path / "table.csv"

    schema = load_json(schema_path)

    rows = load_csv_sample(csv_path, sample_num)

    return {
        "schema": schema,
        "sample_values": rows,
    }

def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {path}")

    return data

def load_csv_sample(
    path: Path, 
    sample_num: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader):
            if i >= sample_num:
                break

            rows.append(dict(row))

    return rows

def save_rdb(
    existing_rdb: dict[str, Any],
    save_root_path: str | Path,
    folder_name: str,
) -> Path:
    save_path = Path(save_root_path) / folder_name
    tables_dir = save_path / "tables"

    tables_dir.mkdir(parents=True, exist_ok=True)

    with (save_path / "schema.json").open("w", encoding="utf-8") as f:
        json.dump(existing_rdb["schema"], f, indent=2, ensure_ascii=False)

    with (save_path / "constraints.json").open("w", encoding="utf-8") as f:
        json.dump(existing_rdb["constraints"], f, indent=2, ensure_ascii=False)

    for table_name, rows in existing_rdb["sample_values"].items():
        csv_path = tables_dir / f"{table_name}.csv"
        _save_table_csv(csv_path, rows)

    return save_path


def _save_table_csv(
    csv_path: Path,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        csv_path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)