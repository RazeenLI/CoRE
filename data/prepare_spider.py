#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from data.parse_sql import clean_identifier, normalize_type
except ModuleNotFoundError:  # Direct execution: python data/prepare_spider.py
    from parse_sql import clean_identifier, normalize_type


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def normalize_sqlite_type(type_raw: str) -> dict[str, Any]:
    normalized = normalize_type(type_raw)
    if normalized.get("type"):
        return normalized

    normalized["type"] = "unknown"
    return normalized


def unique_normalized_names(names: list[str], object_kind: str, database: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    reverse: dict[str, str] = {}
    for original in names:
        normalized = clean_identifier(original)
        if not normalized:
            raise ValueError(f"Empty normalized {object_kind} name in {database}: {original!r}")
        if normalized in reverse and reverse[normalized] != original:
            raise ValueError(
                f"Colliding {object_kind} names in {database}: "
                f"{reverse[normalized]!r} and {original!r} -> {normalized!r}"
            )
        mapping[original] = normalized
        reverse[normalized] = original
    return mapping


def inspect_database(
    sqlite_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[dict[str, Any]]]]:
    connection = sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        original_tables = [
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        table_names = unique_normalized_names(original_tables, "table", sqlite_path.stem)
        schema: dict[str, Any] = {"database": sqlite_path.stem, "tables": {}}
        constraints: dict[str, Any] = {
            "database": sqlite_path.stem,
            "constraints": {
                "primary_keys": {},
                "foreign_keys": {},
                "unique_constraints": {},
                "check_constraints": {},
                "indexes": {},
                "inferred_constraints": {},
            },
        }
        rows_by_table: dict[str, list[dict[str, Any]]] = {}
        column_maps: dict[str, dict[str, str]] = {}
        primary_keys: dict[str, list[str]] = {}

        for original_table in original_tables:
            table = table_names[original_table]
            quoted_table = quote_identifier(original_table)
            table_info = list(connection.execute(f"PRAGMA table_info({quoted_table})"))
            original_columns = [row["name"] for row in table_info]
            column_map = unique_normalized_names(original_columns, "column", f"{sqlite_path.stem}.{table}")
            column_maps[original_table] = column_map

            columns: dict[str, Any] = {}
            pk_parts: list[tuple[int, str]] = []
            for column_info in table_info:
                original_column = column_info["name"]
                column = column_map[original_column]
                column_schema = normalize_sqlite_type(column_info["type"] or "")
                column_schema["nullable"] = not bool(column_info["notnull"] or column_info["pk"])
                if column_info["dflt_value"] is not None:
                    column_schema["default"] = str(column_info["dflt_value"])
                columns[column] = column_schema
                if column_info["pk"]:
                    pk_parts.append((int(column_info["pk"]), column))

            primary_key = [column for _, column in sorted(pk_parts)]
            primary_keys[original_table] = primary_key
            if primary_key:
                constraints["constraints"]["primary_keys"][table] = primary_key

            schema["tables"][table] = {"columns": columns}
            query = f"SELECT * FROM {quoted_table}"
            rows_by_table[table] = [
                {column_map[key]: value for key, value in dict(row).items()}
                for row in connection.execute(query)
            ]

        for original_table in original_tables:
            table = table_names[original_table]
            quoted_table = quote_identifier(original_table)
            grouped_fks: dict[int, list[sqlite3.Row]] = defaultdict(list)
            for fk_row in connection.execute(f"PRAGMA foreign_key_list({quoted_table})"):
                grouped_fks[int(fk_row["id"])].append(fk_row)

            for fk_rows in grouped_fks.values():
                fk_rows.sort(key=lambda row: int(row["seq"]))
                referenced_original = fk_rows[0]["table"]
                if referenced_original not in table_names:
                    continue
                referenced_table = table_names[referenced_original]
                referenced_map = column_maps[referenced_original]
                referenced_pk = primary_keys[referenced_original]
                source_columns = [column_maps[original_table][row["from"]] for row in fk_rows]
                referenced_columns = []
                for index, row in enumerate(fk_rows):
                    referenced_column = row["to"]
                    if referenced_column is None:
                        if index >= len(referenced_pk):
                            referenced_columns = []
                            break
                        referenced_columns.append(referenced_pk[index])
                    else:
                        referenced_columns.append(referenced_map[referenced_column])
                if not referenced_columns:
                    continue
                constraints["constraints"]["foreign_keys"].setdefault(table, []).append(
                    {
                        "columns": source_columns,
                        "referenced_table": referenced_table,
                        "referenced_columns": referenced_columns,
                    }
                )

            for index_row in connection.execute(f"PRAGMA index_list({quoted_table})"):
                if index_row["origin"] == "pk":
                    continue
                index_name = index_row["name"]
                quoted_index = quote_identifier(index_name)
                index_columns = [
                    column_maps[original_table][row["name"]]
                    for row in connection.execute(f"PRAGMA index_info({quoted_index})")
                    if row["name"] is not None
                ]
                if not index_columns:
                    continue
                key = "unique_constraints" if index_row["unique"] else "indexes"
                constraints["constraints"][key].setdefault(table, []).append(index_columns)

        return schema, constraints, rows_by_table
    finally:
        connection.close()


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.hex()
    return value


def write_parsed_database(
    sqlite_path: Path,
    output_dir: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    if output_dir.exists() and overwrite:
        shutil.rmtree(output_dir)

    schema, constraints, rows_by_table = inspect_database(sqlite_path)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "schema.json").write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "constraints.json").write_text(
        json.dumps(constraints, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    for table, table_schema in schema["tables"].items():
        columns = list(table_schema["columns"])
        with (tables_dir / f"{table}.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for row in rows_by_table[table]:
                writer.writerow({column: csv_value(row.get(column)) for column in columns})

    return {
        "database": schema["database"],
        "sqlite_path": str(sqlite_path),
        "output_dir": str(output_dir),
        "table_count": len(schema["tables"]),
        "column_count": sum(len(table["columns"]) for table in schema["tables"].values()),
        "row_count": sum(len(rows) for rows in rows_by_table.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Spider SQLite databases to parsed AIRDB RDBs.")
    parser.add_argument("--input-root", type=Path, default=Path("data/Spider/raw"))
    parser.add_argument("--output-root", type=Path, default=Path("data/Spider/parsed"))
    parser.add_argument("--database", action="append", default=[], help="Database name to import; repeatable.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    selected = set(args.database)
    sqlite_paths = sorted(args.input_root.rglob("*.sqlite"))
    if selected:
        sqlite_paths = [path for path in sqlite_paths if path.stem in selected]
        missing = selected - {path.stem for path in sqlite_paths}
        if missing:
            raise FileNotFoundError(f"Spider databases not found: {sorted(missing)}")
    if not sqlite_paths:
        raise FileNotFoundError(f"No SQLite databases found under {args.input_root}")

    summaries = []
    for index, sqlite_path in enumerate(sqlite_paths, start=1):
        output_dir = args.output_root / sqlite_path.stem
        summary = write_parsed_database(sqlite_path, output_dir, overwrite=args.overwrite)
        summaries.append(summary)
        print(
            f"[{index}/{len(sqlite_paths)}] {sqlite_path.stem}: "
            f"tables={summary['table_count']} rows={summary['row_count']}"
        )

    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "import_summary.json").write_text(
        json.dumps({"database_count": len(summaries), "databases": summaries}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
