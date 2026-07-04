#!/usr/bin/env python3

import argparse
import copy
import csv
import json
import random
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple


try:
    import yaml
except ImportError as e:
    raise SystemExit("Missing dependency: pip install pyyaml") from e

"""
python data/form_benchmark.py data/Chinook/benchmarks/configs/small_case_A_remove_columns.yaml
python data/form_benchmark.py data/Chinook/benchmarks/configs/small_case_B_remove_table.yaml
python data/form_benchmark.py data/Chinook/benchmarks/configs/small_case_C_remove_relationship_table.yaml
python data/form_benchmark.py data/Chinook/benchmarks/configs/small_case_D_project_columns.yaml
python data/form_benchmark.py data/Chinook/benchmarks/configs/small_pipeline_ABC.yaml
"""
# -----------------------------
# IO
# -----------------------------

def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing table CSV: {path}")

    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, Any]], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()

        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def read_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# -----------------------------
# Row / column selection
# -----------------------------

def stable_step_name(raw_name: str, idx: int, incoming_table: str) -> str:
    if raw_name:
        return raw_name

    return f"step_{idx:02d}_{incoming_table}"


def select_rows(
    rows: List[Dict[str, str]],
    policy: Dict[str, Any],
    seed: int,
) -> List[Dict[str, str]]:
    mode = policy.get("mode", "all")

    if mode == "all":
        return copy.deepcopy(rows)

    if mode == "first_n":
        return copy.deepcopy(rows[: int(policy["n"])])

    if mode == "ratio":
        ratio = float(policy["ratio"])
        if ratio >= 1.0:
            return copy.deepcopy(rows)
        n = int(round(len(rows) * ratio))
        rng = random.Random(seed)
        indices = sorted(rng.sample(range(len(rows)), n))
        return copy.deepcopy([rows[i] for i in indices])

    if mode == "random_n":
        n = min(int(policy["n"]), len(rows))
        rng = random.Random(seed)
        indices = sorted(rng.sample(range(len(rows)), n))
        return copy.deepcopy([rows[i] for i in indices])

    raise ValueError(f"Unsupported row_policy mode: {mode}")



def project_rows(rows: List[Dict[str, Any]], columns: List[str]) -> List[Dict[str, Any]]:
    return [{col: row.get(col, "") for col in columns} for row in rows]

def normalize_column_mapping(
    step: Dict[str, Any],
    expected_table_cols: Dict[str, List[str]],
) -> Dict[str, str]:
    """
    Return mapping:
        source_column -> incoming_column

    Supported YAML:
      1. column_mapping:
           source_col: incoming_col

      2. incoming_columns:
           - col1
           - col2

      3. incoming_columns: "*"
    """
    source_table = step["source_table"]

    if "column_mapping" in step:
        mapping = step["column_mapping"]

        if not isinstance(mapping, dict):
            raise ValueError("column_mapping must be a dict: source_col -> incoming_col")

        return dict(mapping)

    incoming_cols = step.get("incoming_columns", "*")

    if incoming_cols == "*":
        return {
            col: col
            for col in expected_table_cols[source_table]
        }

    return {
        col: col
        for col in incoming_cols
    }


def project_rows_with_mapping(
    rows: List[Dict[str, Any]],
    column_mapping: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Project source rows into incoming rows with optional column renaming.

    column_mapping:
        source_column -> incoming_column
    """
    projected = []

    for row in rows:
        new_row = {}

        for source_col, incoming_col in column_mapping.items():
            new_row[incoming_col] = row.get(source_col, "")

        projected.append(new_row)

    return projected


def make_single_table_schema_with_mapping(
    source_schema: Dict[str, Any],
    source_table: str,
    incoming_table: str,
    column_mapping: Dict[str, str],
) -> Dict[str, Any]:
    """
    Build incoming schema from source table with optional column renaming.

    column_mapping:
        source_column -> incoming_column
    """
    source_table_schema = source_schema["tables"][source_table]

    incoming_columns = {}

    for source_col, incoming_col in column_mapping.items():
        incoming_columns[incoming_col] = copy.deepcopy(
            source_table_schema["columns"][source_col]
        )

    return {
        "database": "incoming",
        "tables": {
            incoming_table: {
                "columns": incoming_columns,
                "column_order": list(column_mapping.values()),
            }
        },
    }

def make_incoming_profile_for_step_with_mapping(
    source_profiles: Dict[str, Any],
    source_table: str,
    incoming_table: str,
    column_mapping: Dict[str, str],
) -> Dict[str, Any]:
    """
    Build one-table profile for a step with optional table/column renaming.

    column_mapping:
        source_column -> incoming_column
    """
    source_tables = source_profiles.get("tables", {})

    out: Dict[str, Any] = {
        "database": "incoming",
        "tables": {},
    }

    if source_table not in source_tables:
        return out

    table_profile = copy.deepcopy(source_tables[source_table])

    renamed_columns = {}

    for source_col, incoming_col in column_mapping.items():
        source_col_profile = table_profile.get("columns", {}).get(source_col)

        if source_col_profile is None:
            continue

        incoming_col_profile = copy.deepcopy(source_col_profile)
        incoming_col_profile["name"] = incoming_col
        renamed_columns[incoming_col] = incoming_col_profile

    table_profile["columns"] = renamed_columns

    if "table" in table_profile:
        table_profile["table"]["name"] = incoming_table
        table_profile["table"]["column_count"] = len(column_mapping)

    out["tables"][incoming_table] = table_profile

    return out

def unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []

    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)

    return out


# -----------------------------
# Schema construction
# -----------------------------

def all_source_tables(source_schema: Dict[str, Any]) -> List[str]:
    return list(source_schema["tables"].keys())


def table_column_order(source_schema: Dict[str, Any], table: str) -> List[str]:
    return list(source_schema["tables"][table]["columns"].keys())


def resolve_expected_tables(spec: Any, source_schema: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Rules:
      expected_rdb.tables: []              -> all tables, all columns
      expected_rdb.tables.table_name: []   -> all columns in that table
      expected_rdb.tables.table_name: [...] -> selected columns
    """
    resolved: Dict[str, List[str]] = {}

    if spec == []:
        for table in all_source_tables(source_schema):
            resolved[table] = table_column_order(source_schema, table)
        return resolved

    if isinstance(spec, list):
        for table in spec:
            check_table(source_schema, table)
            resolved[table] = table_column_order(source_schema, table)
        return resolved

    if isinstance(spec, dict):
        for table, cols in spec.items():
            check_table(source_schema, table)

            if cols == [] or cols == "*" or cols is None:
                resolved[table] = table_column_order(source_schema, table)
            else:
                for col in cols:
                    check_column(source_schema, table, col)
                resolved[table] = list(cols)

        return resolved

    raise ValueError("expected_rdb.tables must be [] or a mapping.")


def make_schema_subset(
    source_schema: Dict[str, Any],
    table_cols: Dict[str, List[str]],
    database_suffix: str = "",
) -> Dict[str, Any]:
    schema = {
        "database": source_schema.get("database", "database") + database_suffix,
        # "dialect": source_schema.get("dialect", "postgresql"),
        # "version": source_schema.get("version", "v1"),
        "tables": {},
    }

    for table, cols in table_cols.items():
        source_table = source_schema["tables"][table]
        schema["tables"][table] = {
            "columns": {
                col: copy.deepcopy(source_table["columns"][col])
                for col in cols
            },
            "column_order": list(cols),
        }

    return schema


def make_single_table_schema(
    source_schema: Dict[str, Any],
    source_table: str,
    incoming_table: str,
    columns: List[str],
) -> Dict[str, Any]:
    source_table_schema = source_schema["tables"][source_table]

    return {
        "database": "incoming",
        # "dialect": source_schema.get("dialect", "postgresql"),
        # "version": source_schema.get("version", "v1"),
        "tables": {
            incoming_table: {
                "columns": {
                    col: copy.deepcopy(source_table_schema["columns"][col])
                    for col in columns
                },
                "column_order": list(columns),
            }
        },
    }


def check_table(source_schema: Dict[str, Any], table: str) -> None:
    if table not in source_schema["tables"]:
        raise ValueError(f"Unknown table: {table}")


def check_column(source_schema: Dict[str, Any], table: str, column: str) -> None:
    if column not in source_schema["tables"][table]["columns"]:
        raise ValueError(f"Unknown column: {table}.{column}")


# -----------------------------
# Constraint filtering
# -----------------------------

def table_exists(schema: Dict[str, Any], table: str) -> bool:
    return table in schema["tables"]


def columns_exist(schema: Dict[str, Any], table: str, columns: List[str]) -> bool:
    if not table_exists(schema, table):
        return False

    existing_cols = schema["tables"][table]["columns"]
    return all(col in existing_cols for col in columns)


def filter_constraints(
    source_constraints: Dict[str, Any],
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    src = source_constraints.get("constraints", {})

    out: Dict[str, Any] = {
        "database": schema.get("database", source_constraints.get("database", "database")),
        "constraints": {
            "primary_keys": {},
            "foreign_keys": {},
            "unique_constraints": {},
            "check_constraints": {},
            "indexes": {},
            "inferred_constraints": {},
        },
    }

    # primary keys
    for table, columns in src.get("primary_keys", {}).items():
        if columns_exist(schema, table, columns):
            out["constraints"]["primary_keys"][table] = copy.deepcopy(columns)

    # foreign keys
    for table, fks in src.get("foreign_keys", {}).items():
        for fk in fks:
            if (
                columns_exist(schema, table, fk["columns"])
                and columns_exist(schema, fk["referenced_table"], fk["referenced_columns"])
            ):
                out["constraints"]["foreign_keys"].setdefault(table, []).append(
                    copy.deepcopy(fk)
                )

    # unique constraints
    for table, unique_groups in src.get("unique_constraints", {}).items():
        for columns in unique_groups:
            if columns_exist(schema, table, columns):
                out["constraints"]["unique_constraints"].setdefault(table, []).append(
                    copy.deepcopy(columns)
                )

    # indexes
    for table, index_groups in src.get("indexes", {}).items():
        for columns in index_groups:
            if columns_exist(schema, table, columns):
                out["constraints"]["indexes"].setdefault(table, []).append(
                    copy.deepcopy(columns)
                )

    # check constraints
    for table, expressions in src.get("check_constraints", {}).items():
        if table_exists(schema, table):
            out["constraints"]["check_constraints"][table] = copy.deepcopy(expressions)

    # inferred constraints
    for table, inferred_items in src.get("inferred_constraints", {}).items():
        if table_exists(schema, table):
            out["constraints"]["inferred_constraints"][table] = copy.deepcopy(inferred_items)

    return out


def fks_for_table_to_current_rdb(
    source_constraints: Dict[str, Any],
    source_table: str,
    current_schema: Dict[str, Any],
) -> List[Dict[str, Any]]:
    fks = []

    table_fks = (
        source_constraints
        .get("constraints", {})
        .get("foreign_keys", {})
        .get(source_table, [])
    )

    for fk in table_fks:
        if table_exists(current_schema, fk["referenced_table"]):
            fks.append({
                "table": source_table,
                "columns": fk["columns"],
                "referenced_table": fk["referenced_table"],
                "referenced_columns": fk["referenced_columns"],
            })

    return fks


# -----------------------------
# Profile filtering
# -----------------------------

def load_source_profiles(source_dir: Path) -> Dict[str, Any]:
    profile_path = source_dir / "profiles.json"

    if not profile_path.exists():
        return {
            "database": "unknown",
            # "profile_version": "v1",
            "tables": {},
        }

    return read_json(profile_path)


def filter_profiles_by_schema(
    source_profiles: Dict[str, Any],
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Keep only profiles for tables/columns that exist in schema.
    Used for existing/expected RDB profile splitting.
    """
    source_tables = source_profiles.get("tables", {})

    out: Dict[str, Any] = {
        "database": schema.get("database", source_profiles.get("database", "database")),
        # "profile_version": source_profiles.get("profile_version", "v1"),
        "tables": {},
    }

    for table, table_schema in schema["tables"].items():
        if table not in source_tables:
            continue

        table_profile = copy.deepcopy(source_tables[table])
        keep_columns = set(table_schema.get("column_order", []))

        table_profile["columns"] = {
            col: profile
            for col, profile in table_profile.get("columns", {}).items()
            if col in keep_columns
        }

        if "table" in table_profile:
            table_profile["table"]["name"] = table
            table_profile["table"]["column_count"] = len(keep_columns)

        out["tables"][table] = table_profile

    return out


def make_incoming_profile_for_step(
    source_profiles: Dict[str, Any],
    source_table: str,
    incoming_table: str,
    columns: List[str],
) -> Dict[str, Any]:
    """
    Build one-table profile for a step.
    Source profile key is source_table, but output table name should be incoming_table.
    """
    source_tables = source_profiles.get("tables", {})

    out: Dict[str, Any] = {
        "database": "incoming",
        # "profile_version": source_profiles.get("profile_version", "v1"),
        "tables": {},
    }

    if source_table not in source_tables:
        return out

    table_profile = copy.deepcopy(source_tables[source_table])
    keep_columns = set(columns)

    table_profile["columns"] = {
        col: profile
        for col, profile in table_profile.get("columns", {}).items()
        if col in keep_columns
    }

    if "table" in table_profile:
        table_profile["table"]["name"] = incoming_table
        table_profile["table"]["column_count"] = len(columns)

    out["tables"][incoming_table] = table_profile

    return out


# -----------------------------
# RDB write
# -----------------------------

def write_rdb(
    out_dir: Path,
    schema: Dict[str, Any],
    constraints: Dict[str, Any],
    table_rows: Dict[str, List[Dict[str, Any]]],
    profiles: Dict[str, Any] | None = None,
) -> None:
    write_json(out_dir / "schema.json", schema)
    write_json(out_dir / "constraints.json", constraints)

    if profiles is not None:
        write_json(out_dir / "profiles.json", profiles)

    tables_dir = out_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    for table, table_schema in schema["tables"].items():
        columns = table_schema["column_order"]
        write_csv(tables_dir / f"{table}.csv", table_rows.get(table, []), columns)


def write_run_config(
    output_dir: Path,
    steps: List[Dict[str, Any]],
    sample_num: int,
) -> None:
    """
    Generate config.yaml for running the benchmark pipeline.

    Output:
      output_dir/config.yaml
    """
    run_config = {
        "existing_rdb": {
            "path": str(output_dir / "existing"),
            "sample_num": sample_num,
        },
        "steps": [],
    }

    for idx, step in enumerate(steps, start=1):
        step_name = stable_step_name(
            raw_name=step.get("name"),
            idx=idx,
            incoming_table=step["incoming_table"],
        )

        safe_step_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", step_name).strip("_")

        run_config["steps"].append({
            "task_id": safe_step_name,
            "path": str(output_dir / "steps" / safe_step_name),
            "sample_num": sample_num,
        })

    config_path = output_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(run_config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

# -----------------------------
# Benchmark construction
# -----------------------------

def load_source(source_dir: Path) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, List[Dict[str, str]]]]:
    schema = read_json(source_dir / "schema.json")
    constraints = read_json(source_dir / "constraints.json")

    rows = {}
    for table in schema["tables"]:
        rows[table] = read_csv(source_dir / "tables" / f"{table}.csv")

    return schema, constraints, rows


def build_expected(
    cfg: Dict[str, Any],
    source_schema: Dict[str, Any],
    source_constraints: Dict[str, Any],
    source_rows: Dict[str, List[Dict[str, str]]],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, List[Dict[str, Any]]], Dict[str, List[str]]]:
    expected_cfg = cfg["expected_rdb"]
    seed = int(cfg["info"].get("seed", 42))

    table_cols = resolve_expected_tables(expected_cfg["tables"], source_schema)
    schema = make_schema_subset(source_schema, table_cols)
    constraints = filter_constraints(source_constraints, schema)

    row_policy = expected_cfg.get("row_policy", {"mode": "all"})
    rows = {}

    for table, columns in table_cols.items():
        selected = select_rows(source_rows[table], row_policy, seed)
        rows[table] = project_rows(selected, columns)

    return schema, constraints, rows, table_cols


def build_existing(
    expected_schema: Dict[str, Any],
    source_constraints: Dict[str, Any],
    expected_rows: Dict[str, List[Dict[str, Any]]],
    steps: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    schema = copy.deepcopy(expected_schema)
    rows = copy.deepcopy(expected_rows)

    for step in steps:
        operation = step["operation"]
        source_table = step["source_table"]

        if operation == "remove_table":
            schema["tables"].pop(source_table, None)
            rows.pop(source_table, None)

        elif operation == "remove_columns":
            del_cols = step.get("delate_columns", step.get("delete_columns", []))

            if source_table not in schema["tables"]:
                raise ValueError(f"Cannot remove columns from missing table: {source_table}")

            for col in del_cols:
                schema["tables"][source_table]["columns"].pop(col, None)

            schema["tables"][source_table]["column_order"] = [
                col for col in schema["tables"][source_table]["column_order"]
                if col not in del_cols
            ]

            for row in rows[source_table]:
                for col in del_cols:
                    row.pop(col, None)

        elif operation == "project_columns":
            # No change to existing schema/rows/constraints.
            # This operation only creates an incoming projected table.
            pass

        else:
            raise ValueError(f"Unsupported step operation: {operation}")

    constraints = filter_constraints(source_constraints, schema)
    return schema, constraints, rows


def incoming_columns_for_step(
    step: Dict[str, Any],
    expected_table_cols: Dict[str, List[str]],
) -> List[str]:
    source_table = step["source_table"]
    incoming_cols = step.get("incoming_columns", "*")

    if incoming_cols != "*":
        return list(incoming_cols)

    if step["operation"] == "remove_table":
        return list(expected_table_cols[source_table])

    if step["operation"] == "remove_columns":
        keys = step.get("keys", [])
        del_cols = step.get("delate_columns", step.get("delete_columns", []))
        return unique_keep_order(list(keys) + list(del_cols))
    
    if step["operation"] == "project_columns":
        column_mapping = normalize_column_mapping(step, expected_table_cols)
        return list(column_mapping.values())

    raise ValueError(f"Unsupported step operation: {step['operation']}")


def write_step(
    step_dir: Path,
    step: Dict[str, Any],
    idx: int,
    seed: int,
    source_schema: Dict[str, Any],
    source_constraints: Dict[str, Any],
    source_profiles: Dict[str, Any],
    expected_rows: Dict[str, List[Dict[str, Any]]],
    expected_table_cols: Dict[str, List[str]],
    current_schema: Dict[str, Any],
) -> Dict[str, Any]:
    source_table = step["source_table"]
    incoming_table = step["incoming_table"]
    operation = step["operation"]

    columns = incoming_columns_for_step(step, expected_table_cols)

    for col in columns:
        check_column(source_schema, source_table, col)

    row_policy = step.get("incoming_row_policy", {"mode": "all"})
    base_rows = expected_rows[source_table]
    selected_rows = select_rows(base_rows, row_policy, seed + idx)

    if operation == "project_columns":
        column_mapping = normalize_column_mapping(step, expected_table_cols)

        for source_col in column_mapping.keys():
            check_column(source_schema, source_table, source_col)

        columns = list(column_mapping.values())

        incoming_rows = project_rows_with_mapping(
            rows=selected_rows,
            column_mapping=column_mapping,
        )

        incoming_schema = make_single_table_schema_with_mapping(
            source_schema=source_schema,
            source_table=source_table,
            incoming_table=incoming_table,
            column_mapping=column_mapping,
        )

        incoming_profiles = make_incoming_profile_for_step_with_mapping(
            source_profiles=source_profiles,
            source_table=source_table,
            incoming_table=incoming_table,
            column_mapping=column_mapping,
        )

    else:
        columns = incoming_columns_for_step(step, expected_table_cols)

        for col in columns:
            check_column(source_schema, source_table, col)

        incoming_rows = project_rows(selected_rows, columns)

        incoming_schema = make_single_table_schema(
            source_schema=source_schema,
            source_table=source_table,
            incoming_table=incoming_table,
            columns=columns,
        )

        incoming_profiles = make_incoming_profile_for_step(
            source_profiles=source_profiles,
            source_table=source_table,
            incoming_table=incoming_table,
            columns=columns,
        )

    if operation == "remove_columns":
        decision = {
            "operation": "extend_existing_table",
            "incoming_table": incoming_table,
            "target_table": source_table,
            "keys": step.get("keys", []),
            "add_columns": step.get("delete_columns", []),
            "create_new_table": False,
        }

    elif operation == "remove_table":
        expected_fks = fks_for_table_to_current_rdb(
            source_constraints=source_constraints,
            source_table=source_table,
            current_schema=current_schema,
        )

        decision_operation = (
            "create_relationship_table"
            if len(expected_fks) >= 2
            else "create_new_table"
        )

        decision = {
            "operation": decision_operation,
            "incoming_table": incoming_table,
            "target_table": source_table,
            "create_new_table": True,
            "expected_foreign_keys": expected_fks,
        }

    elif operation == "project_columns":
        source_to_incoming = normalize_column_mapping(step, expected_table_cols)
        incoming_to_target = {
            incoming_col: source_col
            for source_col, incoming_col in source_to_incoming.items()
        }
        
        decision = {
            "operation": "map_existing_table",
            "incoming_table": incoming_table,
            "target_table": source_table,
            "source_to_incoming_columns": source_to_incoming,
            "incoming_to_target_columns": incoming_to_target,
            "keys": step.get("keys", []),
            "create_new_table": False,
            "schema_change": False,
        }

    else:
        raise ValueError(f"Unsupported step operation: {operation}")

    write_csv(step_dir / "table.csv", incoming_rows, columns)
    write_json(step_dir / "schema.json", incoming_schema)
    write_json(step_dir / "profiles.json", incoming_profiles)
    write_json(step_dir / "expected_decision.json", decision)

    return decision


def apply_step_to_current_expected_state(
    current_schema: Dict[str, Any],
    expected_schema: Dict[str, Any],
    step: Dict[str, Any],
) -> Dict[str, Any]:
    current_schema = copy.deepcopy(current_schema)
    operation = step["operation"]
    source_table = step["source_table"]

    if operation == "remove_table":
        current_schema["tables"][source_table] = copy.deepcopy(
            expected_schema["tables"][source_table]
        )

    elif operation == "remove_columns":
        del_cols = step.get("delate_columns", step.get("delete_columns", []))

        for col in del_cols:
            current_schema["tables"][source_table]["columns"][col] = copy.deepcopy(
                expected_schema["tables"][source_table]["columns"][col]
            )

        current_schema["tables"][source_table]["column_order"] = [
            col for col in expected_schema["tables"][source_table]["column_order"]
            if col in current_schema["tables"][source_table]["columns"]
        ]

    elif operation == "project_columns":
        pass

    return current_schema


def build_benchmark(yaml_path: Path) -> None:
    cfg = read_yaml(yaml_path)

    seed = int(cfg["info"].get("seed", 42))
    source_dir = Path(cfg["info"]["source_dir"])
    output_dir = Path(cfg["info"]["output_dir"])
    sample_num = int(cfg["info"].get("sample_num", 0))

    source_schema, source_constraints, source_rows = load_source(source_dir)
    source_profiles = load_source_profiles(source_dir)

    expected_schema, expected_constraints, expected_rows, expected_table_cols = build_expected(
        cfg=cfg,
        source_schema=source_schema,
        source_constraints=source_constraints,
        source_rows=source_rows,
    )

    existing_schema, existing_constraints, existing_rows = build_existing(
        expected_schema=expected_schema,
        source_constraints=source_constraints,
        expected_rows=expected_rows,
        steps=cfg.get("steps", []),
    )

    if output_dir.exists():
        shutil.rmtree(output_dir)

    expected_profiles = filter_profiles_by_schema(
        source_profiles=source_profiles,
        schema=expected_schema,
    )

    existing_profiles = filter_profiles_by_schema(
        source_profiles=source_profiles,
        schema=existing_schema,
    )

    write_rdb(
        output_dir / "existing",
        existing_schema,
        existing_constraints,
        existing_rows,
        existing_profiles,
    )

    write_rdb(
        output_dir / "expected",
        expected_schema,
        expected_constraints,
        expected_rows,
        expected_profiles,
    )

    steps_dir = output_dir / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)

    current_schema = copy.deepcopy(existing_schema)

    for idx, step in enumerate(cfg.get("steps", []), start=1):
        step_name = stable_step_name(
            raw_name=step.get("name"),
            idx=idx,
            incoming_table=step["incoming_table"],
        )

        safe_step_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", step_name).strip("_")
        step_dir = steps_dir / safe_step_name
        step_dir.mkdir(parents=True, exist_ok=True)

        write_step(
            step_dir=step_dir,
            step=step,
            idx=idx,
            seed=seed,
            source_schema=source_schema,
            source_constraints=source_constraints,
            source_profiles=source_profiles,
            expected_rows=expected_rows,
            expected_table_cols=expected_table_cols,
            current_schema=current_schema,
        )

        current_schema = apply_step_to_current_expected_state(
            current_schema=current_schema,
            expected_schema=expected_schema,
            step=step,
        )

        write_run_config(
            output_dir=output_dir,
            steps=cfg.get("steps", []),
            sample_num=sample_num,
        )

    print(f"Generated benchmark: {output_dir}")
    print(f"existing: {output_dir / 'existing'}")
    print(f"steps:    {output_dir / 'steps'}")
    print(f"expected: {output_dir / 'expected'}")
    print(f"config:   {output_dir / 'config.yaml'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build RDB schema-evolution benchmark from one YAML spec."
    )
    parser.add_argument("yaml_path", type=Path, help="Path to benchmark YAML file")
    args = parser.parse_args()

    build_benchmark(args.yaml_path)


if __name__ == "__main__":
    main()