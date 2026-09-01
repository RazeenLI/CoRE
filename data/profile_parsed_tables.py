#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

# Add project root to Python import path.
# This allows importing model.* when this script is run from data/.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.agents.profiler_agent import ProfilerAgent


"""
Batch profile parsed relational tables with ProfilerAgent.

Expected input directory produced by data/parse_sql.py:

    parsed/
      schema.json
      constraints.json          # optional for this script
      tables/
        <table_name>.csv

Example:

    python data/profile_parsed_tables.py \
      --parsed data/Chinook/parsed \
      --output data/Chinook/parsed/profiles.json \
      --model-name Qwen/Qwen3-8B \
      --sample-num 5

For ablation / deterministic profile skeleton only:

    python data/profile_parsed_tables.py \
      --parsed data/Chinook/parsed \
      --output data/Chinook/parsed/profiles.no_llm.json \
      --sample-num 5 \
      --no-llm
"""


# -----------------------------
# JSON / CSV utilities
# -----------------------------


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {path}")

    return data


def save_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_sample_rows(csv_path: Path, sample_num: int = 0) -> list[dict[str, Any]]:
    if not csv_path.exists():
        return []

    rows: list[dict[str, Any]] = []

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            rows.append(dict(row))

            if sample_num > 0 and len(rows) >= sample_num:
                break

    return rows


# -----------------------------
# Schema shaping
# -----------------------------


def build_single_table_schema(
    database_name: str,
    table_name: str,
    table_schema: dict[str, Any],
) -> dict[str, Any]:
    """
    ProfilerAgent expects incoming_schema to contain exactly one table.
    This wraps one table from parsed/schema.json into that shape.
    """
    return {
        "database": database_name,
        "tables": {
            table_name: table_schema,
        },
    }


def normalize_profile(
    table_name: str,
    table_schema: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """
    Enforce the final per-table benchmark profile structure.

    ProfilerAgent already fills deterministic fields before calling the LLM:
        - table.name
        - table.column_count
        - columns.<col>.name
        - columns.<col>.dtype
        - columns.<col>.value_patterns

    This function makes the saved benchmark JSON stable even if an LLM omits
    fields or returns malformed optional values.
    """
    columns_schema = table_schema.get("columns", {})
    column_order = table_schema.get("column_order", list(columns_schema.keys()))

    table_profile = profile.get("table", {})
    if not isinstance(table_profile, dict):
        table_profile = {}

    normalized_table = {
        "name": table_name,
        "column_count": len(column_order),
        "summary": as_str(table_profile.get("summary", "")),
        "entity": as_str(table_profile.get("entity", "unknown")) or "unknown",
        "role": normalize_role(table_profile.get("role", "unknown")),
        "aliases": as_str_list(table_profile.get("aliases", [])),
    }

    raw_columns = profile.get("columns", {})
    if not isinstance(raw_columns, dict):
        raw_columns = {}

    normalized_columns: dict[str, Any] = {}

    for column_name in column_order:
        column_schema = columns_schema.get(column_name, {})
        column_profile = raw_columns.get(column_name, {})
        if not isinstance(column_profile, dict):
            column_profile = {}

        normalized_columns[column_name] = {
            "name": column_name,
            "dtype": as_str(column_profile.get("dtype", column_schema.get("type", "unknown"))) or "unknown",
            "value_patterns": as_str_list(column_profile.get("value_patterns", [])),
            "meaning": as_str(column_profile.get("meaning", "")),
            "semantic_type": normalize_semantic_type(column_profile.get("semantic_type", "unknown")),
            "business_concept": as_str(column_profile.get("business_concept", "unknown")) or "unknown",
            "aliases": as_str_list(column_profile.get("aliases", [])),
        }

    return {
        "table": normalized_table,
        "columns": normalized_columns,
    }


# -----------------------------
# Field normalization
# -----------------------------


ALLOWED_TABLE_ROLES = {
    "entity_table",
    "transaction_table",
    "lookup_table",
    "relationship_table",
    "unknown",
}


ALLOWED_SEMANTIC_TYPES = {
    "identifier",
    "foreign_key_candidate",
    "person_name",
    "organization_name",
    "email",
    "phone",
    "address",
    "country",
    "city",
    "date",
    "timestamp",
    "money",
    "quantity",
    "category",
    "status",
    "description",
    "code",
    "boolean",
    "unknown",
}


def as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def as_str_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        value = [value]

    if not isinstance(value, list):
        return []

    out: list[str] = []
    seen: set[str] = set()

    for item in value:
        item_str = as_str(item)
        if not item_str:
            continue

        key = item_str.lower()
        if key in seen:
            continue

        out.append(item_str)
        seen.add(key)

    return out


def normalize_role(value: Any) -> str:
    role = as_str(value)
    return role if role in ALLOWED_TABLE_ROLES else "unknown"


def normalize_semantic_type(value: Any) -> str:
    semantic_type = as_str(value)
    return semantic_type if semantic_type in ALLOWED_SEMANTIC_TYPES else "unknown"


# -----------------------------
# Profiling pipeline
# -----------------------------


def create_llm_client(
    model_name: str | None,
    device_map: str,
    no_llm: bool,
) -> Any | None:
    if no_llm:
        return None

    if not model_name:
        raise ValueError("--model-name is required unless --no-llm is set.")

    # Keep heavyweight model dependencies optional for deterministic profiling.
    from model.core.llm_client import HFLLMClient

    return HFLLMClient(
        model_name=model_name,
        device_map=device_map,
    )


def profile_one_table(
    profiler: ProfilerAgent,
    database_name: str,
    table_name: str,
    table_schema: dict[str, Any],
    tables_dir: Path,
    sample_num: int,
) -> dict[str, Any]:
    incoming_schema = build_single_table_schema(
        database_name=database_name,
        table_name=table_name,
        table_schema=table_schema,
    )

    incoming_values = load_sample_rows(
        csv_path=tables_dir / f"{table_name}.csv",
        sample_num=sample_num,
    )

    profile = profiler(
        incoming_schema=incoming_schema,
        incoming_values=incoming_values,
    )

    return normalize_profile(
        table_name=table_name,
        table_schema=table_schema,
        profile=profile,
    )


def profile_all_tables(
    parsed_dir: Path,
    output_path: Path,
    model_name: str | None,
    device_map: str = "auto",
    sample_num: int = 5,
    no_llm: bool = False,
    profiler: ProfilerAgent | None = None,
    llm_enabled: bool | None = None,
) -> dict[str, Any]:
    schema_path = parsed_dir / "schema.json"
    tables_dir = parsed_dir / "tables"

    schema = load_json(schema_path)
    database_name = schema.get("database", parsed_dir.name)
    tables = schema.get("tables", {})

    if not isinstance(tables, dict) or not tables:
        raise ValueError(f"No tables found in schema: {schema_path}")

    if profiler is None:
        llm_client = create_llm_client(
            model_name=model_name,
            device_map=device_map,
            no_llm=no_llm,
        )
        profiler = ProfilerAgent(llm_client=llm_client)
        llm_enabled = llm_client is not None
    elif llm_enabled is None:
        llm_enabled = not no_llm

    output: dict[str, Any] = {
        "database": database_name,
        "profile_version": "v1",
        "source": {
            "parsed_dir": str(parsed_dir),
            "schema_path": str(schema_path),
            "tables_dir": str(tables_dir),
            "sample_num": sample_num,
            "llm_enabled": bool(llm_enabled),
            "model_name": model_name if llm_enabled else None,
        },
        "tables": {},
    }

    for table_name, table_schema in tables.items():
        if not isinstance(table_schema, dict):
            raise ValueError(f"Invalid schema for table {table_name!r}: expected object.")

        output["tables"][table_name] = profile_one_table(
            profiler=profiler,
            database_name=database_name,
            table_name=table_name,
            table_schema=table_schema,
            tables_dir=tables_dir,
            sample_num=sample_num,
        )

    save_json(output, output_path)
    return output


# -----------------------------
# CLI
# -----------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile tables produced by parse_sql.py and save table_profiles.json."
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--parsed",
        type=Path,
        help="Parsed directory containing schema.json and tables/*.csv.",
    )
    input_group.add_argument(
        "--parsed-root",
        type=Path,
        help="Root containing multiple <database>/schema.json parsed directories.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path. Defaults to <parsed>/table_profiles.json.",
    )
    parser.add_argument(
        "--output-name",
        default="profiles.json",
        help="Per-database output filename in --parsed-root mode.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip an existing output file in --parsed-root mode.",
    )

    parser.add_argument(
        "--model-name",
        type=str,
        default=None,
        help="Hugging Face model name, e.g. Qwen/Qwen3-8B.",
    )

    parser.add_argument(
        "--device-map",
        type=str,
        default="auto",
        help='Transformers device_map. Common values: "auto", "cuda:0", "cpu".',
    )

    parser.add_argument(
        "--sample-num",
        type=int,
        default=5,
        help="Number of CSV rows to sample per table. Use 0 for all rows.",
    )

    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM call and save deterministic profile skeletons only.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.parsed is not None:
        parsed_dir = args.parsed
        output_path = args.output or parsed_dir / "profiles.json"
        result = profile_all_tables(
            parsed_dir=parsed_dir,
            output_path=output_path,
            model_name=args.model_name,
            device_map=args.device_map,
            sample_num=args.sample_num,
            no_llm=args.no_llm,
        )
        print(f"table_profiles: {output_path}")
        print(f"database:       {result['database']}")
        print(f"table_count:    {len(result['tables'])}")
        print(f"llm_enabled:    {result['source']['llm_enabled']}")
        return

    if args.output is not None:
        raise ValueError("--output is only valid with --parsed; use --output-name for --parsed-root.")

    parsed_dirs = sorted(
        path.parent for path in args.parsed_root.glob("*/schema.json")
    )
    if not parsed_dirs:
        raise FileNotFoundError(f"No parsed databases found under {args.parsed_root}")

    llm_client = create_llm_client(
        model_name=args.model_name,
        device_map=args.device_map,
        no_llm=args.no_llm,
    )
    shared_profiler = ProfilerAgent(llm_client=llm_client)
    completed = skipped = 0
    for index, parsed_dir in enumerate(parsed_dirs, start=1):
        output_path = parsed_dir / args.output_name
        if args.skip_existing and output_path.exists():
            skipped += 1
            print(f"[{index}/{len(parsed_dirs)}] skip {parsed_dir.name}")
            continue
        result = profile_all_tables(
            parsed_dir=parsed_dir,
            output_path=output_path,
            model_name=args.model_name,
            device_map=args.device_map,
            sample_num=args.sample_num,
            no_llm=args.no_llm,
            profiler=shared_profiler,
            llm_enabled=llm_client is not None,
        )
        completed += 1
        print(
            f"[{index}/{len(parsed_dirs)}] {result['database']}: "
            f"tables={len(result['tables'])} output={output_path}"
        )
    print(f"completed: {completed}")
    print(f"skipped:   {skipped}")


if __name__ == "__main__":
    main()
