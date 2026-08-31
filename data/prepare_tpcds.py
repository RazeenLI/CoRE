#!/usr/bin/env python3
"""Convert official TPC-DS ``dsdgen`` output into the common parsed format.

Run ``parse_sql.py`` on ``tpcds.sql`` and ``tpcds_ri.sql`` first.  This
script then removes the generator-only ``dbgen_version`` table and streams
the pipe-delimited ``.dat`` files into per-table CSV files.
"""

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any


EXCLUDED_TABLES = {"dbgen_version"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def convert_table(source: Path, destination: Path, columns: list[str]) -> int:
    row_count = 0
    with source.open("r", encoding="utf-8", newline="") as src, destination.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        reader = csv.reader(src, delimiter="|")
        writer = csv.writer(dst)
        writer.writerow(columns)

        for line_number, row in enumerate(reader, start=1):
            # dsdgen terminates every record with a pipe, which csv.reader
            # exposes as one additional empty field.
            if row and row[-1] == "":
                row.pop()
            if len(row) != len(columns):
                raise ValueError(
                    f"{source}:{line_number}: expected {len(columns)} fields, "
                    f"found {len(row)}"
                )
            writer.writerow(row)
            row_count += 1

    return row_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert official TPC-DS .dat files to parsed table CSVs."
    )
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--parsed", type=Path, required=True)
    args = parser.parse_args()

    schema_path = args.parsed / "schema.json"
    constraints_path = args.parsed / "constraints.json"
    schema = read_json(schema_path)
    constraints = read_json(constraints_path)

    for table in EXCLUDED_TABLES:
        schema.get("tables", {}).pop(table, None)
        constraint_data = constraints.get("constraints", {})
        constraint_data.get("primary_keys", {}).pop(table, None)
        foreign_keys = constraint_data.get("foreign_keys", {})
        foreign_keys.pop(table, None)
        for source_table, table_fks in list(foreign_keys.items()):
            foreign_keys[source_table] = [
                fk
                for fk in table_fks
                if fk.get("referenced_table") != table
            ]

    tables = schema.get("tables", {})
    if len(tables) != 24:
        raise ValueError(f"Expected 24 TPC-DS business tables, found {len(tables)}")

    tables_dir = args.parsed / "tables"
    if tables_dir.exists():
        shutil.rmtree(tables_dir)
    tables_dir.mkdir(parents=True)

    row_counts: dict[str, int] = {}
    for table, table_schema in tables.items():
        source = args.raw_dir / f"{table}.dat"
        if not source.exists():
            raise FileNotFoundError(f"Missing dsdgen output: {source}")
        columns = list(table_schema.get("columns", {}))
        row_counts[table] = convert_table(
            source, tables_dir / f"{table}.csv", columns
        )

    write_json(schema_path, schema)
    write_json(constraints_path, constraints)
    summary = {
        "database": schema.get("database", "TPCDS"),
        "scale_factor": 1,
        "table_count": len(tables),
        "row_count": sum(row_counts.values()),
        "rows_by_table": row_counts,
        "excluded_tables": sorted(EXCLUDED_TABLES),
        "source_format": "TPC-DS Tools dsdgen pipe-delimited .dat",
    }
    write_json(args.parsed / "import_summary.json", summary)

    print(f"table_count: {summary['table_count']}")
    print(f"row_count:   {summary['row_count']}")
    print(f"tables:      {tables_dir}")
    print(f"summary:     {args.parsed / 'import_summary.json'}")


if __name__ == "__main__":
    main()
