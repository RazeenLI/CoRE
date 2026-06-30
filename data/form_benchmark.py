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
    return list(source_schema["tables"][table]["column_order"])


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
        "dialect": source_schema.get("dialect", "postgresql"),
        "version": source_schema.get("version", "v1"),
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
        "dialect": source_schema.get("dialect", "postgresql"),
        "version": source_schema.get("version", "v1"),
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
    out = {
        "database": schema.get("database", source_constraints.get("database", "database")),
        "dialect": source_constraints.get("dialect", "postgresql"),
        "version": source_constraints.get("version", "v1"),
        "constraints": {
            "primary_keys": [],
            "foreign_keys": [],
            "unique_constraints": [],
            "check_constraints": [],
            "indexes": [],
            "inferred_constraints": [],
        },
    }

    for pk in src.get("primary_keys", []):
        if columns_exist(schema, pk["table"], pk["columns"]):
            out["constraints"]["primary_keys"].append(copy.deepcopy(pk))

    for uq in src.get("unique_constraints", []):
        if columns_exist(schema, uq["table"], uq["columns"]):
            out["constraints"]["unique_constraints"].append(copy.deepcopy(uq))

    for ck in src.get("check_constraints", []):
        if table_exists(schema, ck["table"]):
            out["constraints"]["check_constraints"].append(copy.deepcopy(ck))

    for idx in src.get("indexes", []):
        if columns_exist(schema, idx["table"], idx["columns"]):
            out["constraints"]["indexes"].append(copy.deepcopy(idx))

    for fk in src.get("foreign_keys", []):
        if (
            columns_exist(schema, fk["table"], fk["columns"])
            and columns_exist(schema, fk["referenced_table"], fk["referenced_columns"])
        ):
            out["constraints"]["foreign_keys"].append(copy.deepcopy(fk))

    return out


def fks_for_table_to_current_rdb(
    source_constraints: Dict[str, Any],
    source_table: str,
    current_schema: Dict[str, Any],
) -> List[Dict[str, Any]]:
    fks = []

    for fk in source_constraints.get("constraints", {}).get("foreign_keys", []):
        if fk["table"] != source_table:
            continue

        if table_exists(current_schema, fk["referenced_table"]):
            fks.append({
                "table": fk["table"],
                "columns": fk["columns"],
                "referenced_table": fk["referenced_table"],
                "referenced_columns": fk["referenced_columns"],
            })

    return fks


# -----------------------------
# RDB write
# -----------------------------

def write_rdb(
    out_dir: Path,
    schema: Dict[str, Any],
    constraints: Dict[str, Any],
    table_rows: Dict[str, List[Dict[str, Any]]],
) -> None:
    write_json(out_dir / "schema.json", schema)
    write_json(out_dir / "constraints.json", constraints)

    tables_dir = out_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    for table, table_schema in schema["tables"].items():
        columns = table_schema["column_order"]
        write_csv(tables_dir / f"{table}.csv", table_rows.get(table, []), columns)


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

    raise ValueError(f"Unsupported step operation: {step['operation']}")


def write_step(
    step_dir: Path,
    step: Dict[str, Any],
    idx: int,
    seed: int,
    source_schema: Dict[str, Any],
    source_constraints: Dict[str, Any],
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
    incoming_rows = select_rows(base_rows, row_policy, seed + idx)
    incoming_rows = project_rows(incoming_rows, columns)

    incoming_schema = make_single_table_schema(
        source_schema=source_schema,
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

    else:
        raise ValueError(f"Unsupported step operation: {operation}")

    write_csv(step_dir / "table.csv", incoming_rows, columns)
    write_json(step_dir / "schema.json", incoming_schema)
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

    return current_schema


def build_benchmark(yaml_path: Path) -> None:
    cfg = read_yaml(yaml_path)

    seed = int(cfg["info"].get("seed", 42))
    source_dir = Path(cfg["info"]["source_dir"])
    output_dir = Path(cfg["info"]["output_dir"])

    source_schema, source_constraints, source_rows = load_source(source_dir)

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

    write_rdb(output_dir / "existing", existing_schema, existing_constraints, existing_rows)
    write_rdb(output_dir / "expected", expected_schema, expected_constraints, expected_rows)

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
            expected_rows=expected_rows,
            expected_table_cols=expected_table_cols,
            current_schema=current_schema,
        )

        current_schema = apply_step_to_current_expected_state(
            current_schema=current_schema,
            expected_schema=expected_schema,
            step=step,
        )

    print(f"Generated benchmark: {output_dir}")
    print(f"existing: {output_dir / 'existing'}")
    print(f"steps:    {output_dir / 'steps'}")
    print(f"expected: {output_dir / 'expected'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build RDB schema-evolution benchmark from one YAML spec."
    )
    parser.add_argument("yaml_path", type=Path, help="Path to benchmark YAML file")
    args = parser.parse_args()

    build_benchmark(args.yaml_path)


if __name__ == "__main__":
    main()