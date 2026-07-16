#!/usr/bin/env python3

import argparse
import copy
import csv
import json
import random
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple, Set


try:
    import yaml
except ImportError as e:
    raise SystemExit("Missing dependency: pip install pyyaml") from e

"""
python data/form_benchmark.py data/Chinook/configs/small.yaml
python data/form_benchmark.py data/Chinook/configs/medium.yaml
python data/form_benchmark.py data/Chinook/configs/large.yaml
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
# Benchmark construction: config-driven local cases
# -----------------------------

def load_source_from_config(cfg: Dict[str, Any]) -> Tuple[
    Dict[str, Any],
    Dict[str, Any],
    Dict[str, Any],
    Dict[str, List[Dict[str, str]]],
]:
    """Load full parsed RDB from the new benchmark config."""
    source_cfg = Path(cfg["benchmark"]["source_path"])
    schema = read_json(source_cfg / "schema.json")
    constraints = read_json(source_cfg / "constraints.json")
    profiles = read_json(source_cfg / "profiles.json")

    tables_dir = source_cfg / "tables"
    rows: Dict[str, List[Dict[str, str]]] = {}

    for table in schema["tables"]:
        rows[table] = read_csv(tables_dir / f"{table}.csv")

    return schema, constraints, profiles, rows


def resolve_output_dir(cfg: Dict[str, Any]) -> Path:
    """
    Resolve benchmark output directory.

    Preferred YAML:
        output_dir: data/Chinook/benchmarks/Chinook_small

    Backward-compatible YAML:
        benchmark:
          output_dir: data/Chinook/benchmarks/Chinook_small
    """
    if "output_dir" in cfg:
        return Path(cfg["output_dir"])

    benchmark_cfg = cfg.get("benchmark", {})
    if "output_dir" in benchmark_cfg:
        return Path(benchmark_cfg["output_dir"])

    raise KeyError("Missing output_dir. Use top-level output_dir or benchmark.output_dir.")


def resolve_sample_num(cfg: Dict[str, Any]) -> int:
    """
    Resolve sample_num for generated run config.yaml.

    Preferred YAML:
        sample_num: 3

    Backward-compatible YAML:
        benchmark:
          sample_num: 3
    """

    return int(cfg.get("benchmark", {}).get("sample_num", 3))


def get_pk(source_constraints: Dict[str, Any], table: str) -> List[str]:
    return list(
        source_constraints
        .get("constraints", {})
        .get("primary_keys", {})
        .get(table, [])
    )


def outgoing_fks(source_constraints: Dict[str, Any], table: str) -> List[Dict[str, Any]]:
    return list(
        source_constraints
        .get("constraints", {})
        .get("foreign_keys", {})
        .get(table, [])
    )


def incoming_fks(source_constraints: Dict[str, Any], table: str) -> List[Dict[str, Any]]:
    out = []
    all_fks = source_constraints.get("constraints", {}).get("foreign_keys", {})

    for src_table, fks in all_fks.items():
        for fk in fks:
            if fk.get("referenced_table") == table:
                item = copy.deepcopy(fk)
                item["table"] = src_table
                out.append(item)

    return out


def fk_neighbor_tables(source_constraints: Dict[str, Any], table: str) -> Set[str]:
    neighbors: Set[str] = set()

    for fk in outgoing_fks(source_constraints, table):
        ref_table = fk.get("referenced_table")
        if ref_table:
            neighbors.add(ref_table)

    for fk in incoming_fks(source_constraints, table):
        src_table = fk.get("table")
        if src_table:
            neighbors.add(src_table)

    neighbors.discard(table)
    return neighbors


def build_fk_graph(
    source_schema: Dict[str, Any],
    source_constraints: Dict[str, Any],
) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = {table: set() for table in source_schema["tables"]}

    all_fks = source_constraints.get("constraints", {}).get("foreign_keys", {})
    for src_table, fks in all_fks.items():
        if src_table not in graph:
            continue

        for fk in fks:
            dst_table = fk.get("referenced_table")
            if dst_table not in graph:
                continue
            graph[src_table].add(dst_table)
            graph[dst_table].add(src_table)

    return graph


def graph_distances(graph: Dict[str, Set[str]], seed: str, max_depth: int) -> Dict[str, int]:
    distances = {seed: 0}
    frontier = [seed]

    while frontier:
        current = frontier.pop(0)
        current_depth = distances[current]

        if current_depth >= max_depth:
            continue

        for neighbor in sorted(graph.get(current, set())):
            if neighbor in distances:
                continue
            distances[neighbor] = current_depth + 1
            frontier.append(neighbor)

    return distances


def has_sample_rows(source_rows: Dict[str, List[Dict[str, str]]], table: str) -> bool:
    return bool(source_rows.get(table))


def is_pure_association_table(
    source_schema: Dict[str, Any],
    source_constraints: Dict[str, Any],
    table: str,
) -> bool:
    """A conservative heuristic used only when the config asks to exclude association-like tables."""
    fks = outgoing_fks(source_constraints, table)
    if len(fks) < 2:
        return False

    columns = set(table_column_order(source_schema, table))
    fk_columns = set()
    for fk in fks:
        fk_columns.update(fk.get("columns", []))

    pk_columns = set(get_pk(source_constraints, table))
    structural_columns = fk_columns | pk_columns
    non_structural_columns = columns - structural_columns

    return len(non_structural_columns) <= 1


def passes_common_table_filters(
    table: str,
    cfg: Dict[str, Any],
    source_schema: Dict[str, Any],
    source_rows: Dict[str, List[Dict[str, str]]],
) -> bool:
    filters = cfg.get("after_context", {}).get("seed_table_filters", {})

    if table in set(filters.get("exclude_tables", [])):
        return False

    if filters.get("require_sample_rows", True) and not has_sample_rows(source_rows, table):
        return False

    min_total_columns = int(filters.get("min_total_columns", 1))
    if len(table_column_order(source_schema, table)) < min_total_columns:
        return False

    return True


def source_candidates_for_decision(
    decision: str,
    after_tables: List[str],
    cfg: Dict[str, Any],
    source_schema: Dict[str, Any],
    source_constraints: Dict[str, Any],
    source_rows: Dict[str, List[Dict[str, str]]],
) -> List[str]:
    rules = cfg["case_rules"][decision]
    filters = rules.get("source_table_filters", {})
    candidates = []

    for table in after_tables:
        if not passes_common_table_filters(table, cfg, source_schema, source_rows):
            continue

        columns = table_column_order(source_schema, table)
        pk = get_pk(source_constraints, table)
        non_key_cols = [col for col in columns if col not in set(pk)]

        if filters.get("require_primary_key", False) and not pk:
            continue

        if decision == "extend_table":
            min_hideable = int(filters.get("min_hideable_non_key_columns", 1))
            if len(non_key_cols) < min_hideable:
                continue
            if filters.get("exclude_pure_association_tables", False):
                if is_pure_association_table(source_schema, source_constraints, table):
                    continue

        elif decision == "create_table":
            min_columns = int(filters.get("min_columns", 1))
            if len(columns) < min_columns:
                continue
            if filters.get("require_fk_connection_to_remaining_after", False):
                remaining = set(after_tables) - {table}
                fk_neighbors = fk_neighbor_tables(source_constraints, table)
                if not (fk_neighbors & remaining):
                    continue

        elif decision == "insert_table":
            min_projectable = int(filters.get("min_projectable_columns", 1))
            if len(columns) < min_projectable:
                continue

        else:
            raise ValueError(f"Unsupported decision: {decision}")

        candidates.append(table)

    return candidates


def sample_after_tables(
    cfg: Dict[str, Any],
    rng: random.Random,
    source_schema: Dict[str, Any],
    source_constraints: Dict[str, Any],
    source_rows: Dict[str, List[Dict[str, str]]],
    graph: Dict[str, Set[str]],
) -> List[str]:
    size_cfg = cfg["size"]["after_table_count"]
    min_tables = int(size_cfg["min"])
    max_tables = int(size_cfg["max"])
    target_count = rng.randint(min_tables, max_tables)

    max_depth = int(cfg.get("after_context", {}).get("max_fk_depth", 2))
    seed_candidates = [
        table for table in all_source_tables(source_schema)
        if passes_common_table_filters(table, cfg, source_schema, source_rows)
    ]

    if not seed_candidates:
        raise ValueError("No valid seed tables for after-context generation.")

    rng.shuffle(seed_candidates)

    for seed_table in seed_candidates:
        distances = graph_distances(graph, seed_table, max_depth)
        reachable = sorted(distances.keys(), key=lambda t: (distances[t], t))

        if len(reachable) < min_tables:
            continue

        selected = [seed_table]
        remaining = [table for table in reachable if table != seed_table]
        rng.shuffle(remaining)

        for table in remaining:
            if len(selected) >= target_count:
                break
            selected.append(table)

        if len(selected) < min_tables:
            continue

        # Optional distractor: a connected table in the same FK neighborhood that is not already selected.
        distractor_cfg = cfg.get("after_context", {}).get("distractor_table_count", {})
        if cfg.get("after_context", {}).get("allow_distractor_tables", False):
            max_distractors = int(distractor_cfg.get("max", 0))
            min_distractors = int(distractor_cfg.get("min", 0))
            if max_distractors > 0 and len(selected) < max_tables:
                n_distractors = rng.randint(min_distractors, max_distractors)
                extra_pool = [table for table in reachable if table not in set(selected)]
                rng.shuffle(extra_pool)
                for table in extra_pool[:n_distractors]:
                    if len(selected) >= max_tables:
                        break
                    selected.append(table)

        return unique_keep_order(selected[:max_tables])

    raise ValueError(
        "Cannot sample a connected local after-RDB under the configured size constraints."
    )


def random_column_subset(
    columns: List[str],
    min_n: int,
    max_n: int,
    rng: random.Random,
) -> List[str]:
    if not columns:
        return []

    max_n = min(max_n, len(columns))
    min_n = min(min_n, max_n)
    n = rng.randint(min_n, max_n)
    selected = rng.sample(columns, n)
    return [col for col in columns if col in set(selected)]


def sample_rows_count(
    rows: List[Dict[str, str]],
    cfg: Dict[str, Any],
    rng: random.Random,
) -> List[Dict[str, str]]:
    row_cfg = cfg["size"].get("sample_row_count", {})
    min_rows = int(row_cfg.get("min", 0))
    max_rows = int(row_cfg.get("max", len(rows)))

    if not rows:
        return []

    n = rng.randint(min_rows, max_rows)
    n = min(n, len(rows))

    if n <= 0:
        return []

    indices = sorted(rng.sample(range(len(rows)), n))
    return copy.deepcopy([rows[i] for i in indices])


def subset_rows_for_schema(
    source_rows: Dict[str, List[Dict[str, str]]],
    schema: Dict[str, Any],
    cfg: Dict[str, Any],
    rng: random.Random,
) -> Dict[str, List[Dict[str, Any]]]:
    out = {}
    for table, table_schema in schema["tables"].items():
        columns = table_schema["column_order"]
        selected_rows = sample_rows_count(source_rows.get(table, []), cfg, rng)
        out[table] = project_rows(selected_rows, columns)
    return out


def remove_columns_from_schema_and_rows(
    schema: Dict[str, Any],
    rows: Dict[str, List[Dict[str, Any]]],
    table: str,
    columns: List[str],
) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    schema = copy.deepcopy(schema)
    rows = copy.deepcopy(rows)

    for col in columns:
        schema["tables"][table]["columns"].pop(col, None)

    schema["tables"][table]["column_order"] = [
        col for col in schema["tables"][table]["column_order"]
        if col not in set(columns)
    ]

    for row in rows.get(table, []):
        for col in columns:
            row.pop(col, None)

    return schema, rows


def remove_table_from_schema_and_rows(
    schema: Dict[str, Any],
    rows: Dict[str, List[Dict[str, Any]]],
    table: str,
) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    schema = copy.deepcopy(schema)
    rows = copy.deepcopy(rows)
    schema["tables"].pop(table, None)
    rows.pop(table, None)
    return schema, rows


def get_alias_candidates(obj: Dict[str, Any]) -> List[str]:
    keys = ["aliases", "alias", "alternative_names", "name_aliases", "semantic_aliases"]

    for key in keys:
        value = obj.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(x) for x in value if str(x)]

    return []


def choose_table_alias(
    source_profiles: Dict[str, Any],
    table: str,
    rng: random.Random,
) -> str:
    table_profile = source_profiles.get("tables", {}).get(table, {})
    candidates = []

    if isinstance(table_profile.get("table"), dict):
        candidates.extend(get_alias_candidates(table_profile["table"]))

    candidates.extend(get_alias_candidates(table_profile))
    candidates = [x for x in unique_keep_order(candidates) if x != table]

    if candidates:
        return rng.choice(candidates)

    return f"{to_snake_case(table)}_incoming"


def choose_column_alias(
    source_profiles: Dict[str, Any],
    table: str,
    column: str,
    rng: random.Random,
) -> str:
    col_profile = (
        source_profiles
        .get("tables", {})
        .get(table, {})
        .get("columns", {})
        .get(column, {})
    )
    candidates = [x for x in get_alias_candidates(col_profile) if x != column]

    if candidates:
        return rng.choice(candidates)

    return f"{to_snake_case(column)}_alias"


def to_snake_case(name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s)
    return s.strip("_").lower()


def maybe_apply_perturbation(
    cfg: Dict[str, Any],
    rng: random.Random,
    source_profiles: Dict[str, Any],
    source_table: str,
    incoming_table: str,
    source_columns: List[str],
) -> Tuple[str, Dict[str, str], List[str]]:
    """
    Return:
      incoming_table_name,
      source_col -> incoming_col mapping,
      perturbation tags
    """
    mapping = {col: col for col in source_columns}
    tags: List[str] = []

    pert_cfg = cfg.get("perturbation", {})
    if not pert_cfg.get("enabled", False):
        return incoming_table, mapping, tags

    clean_ratio = float(pert_cfg.get("clean_ratio", 1.0))
    if rng.random() < clean_ratio:
        return incoming_table, mapping, tags

    apply_to = pert_cfg.get("apply_to", {})
    probs = pert_cfg.get("probabilities", {})
    use_aliases = bool(pert_cfg.get("use_profile_aliases", True))

    if apply_to.get("incoming_table_name", False):
        if rng.random() < float(probs.get("table_name_rename", 0.0)):
            incoming_table = choose_table_alias(source_profiles, source_table, rng) if use_aliases else f"{incoming_table}_alias"
            tags.append("table_name_rename")

    if apply_to.get("incoming_column_names", False):
        if rng.random() < float(probs.get("column_name_rename", 0.0)):
            new_mapping = {}
            for source_col in source_columns:
                if use_aliases:
                    new_mapping[source_col] = choose_column_alias(source_profiles, source_table, source_col, rng)
                else:
                    new_mapping[source_col] = f"{source_col}_alias"
            mapping = make_unique_mapping_values(new_mapping)
            tags.append("column_name_rename")

    if apply_to.get("incoming_column_names", False):
        if rng.random() < float(probs.get("low_name_overlap", 0.0)):
            # Apply aliases to all columns if possible. This is stricter than ordinary column rename.
            new_mapping = {}
            for source_col in source_columns:
                new_mapping[source_col] = choose_column_alias(source_profiles, source_table, source_col, rng)
            mapping = make_unique_mapping_values(new_mapping)
            tags.append("low_name_overlap")

    if apply_to.get("incoming_column_order", False):
        if rng.random() < float(probs.get("column_order_shuffle", 0.0)):
            tags.append("column_order_shuffle")

    return incoming_table, mapping, unique_keep_order(tags)


def make_unique_mapping_values(mapping: Dict[str, str]) -> Dict[str, str]:
    used: Dict[str, int] = {}
    out = {}

    for source_col, incoming_col in mapping.items():
        base = incoming_col
        if base not in used:
            used[base] = 1
            out[source_col] = base
        else:
            used[base] += 1
            out[source_col] = f"{base}_{used[base]}"

    return out


def maybe_shuffle_mapping_order(
    mapping: Dict[str, str],
    perturbation_tags: List[str],
    rng: random.Random,
) -> Dict[str, str]:
    if "column_order_shuffle" not in perturbation_tags:
        return mapping

    items = list(mapping.items())
    rng.shuffle(items)
    return dict(items)


def pk_fact(source_constraints: Dict[str, Any], table: str) -> List[Dict[str, Any]]:
    pk = get_pk(source_constraints, table)
    if not pk:
        return []
    return [{"table": table, "columns": pk}]


def fks_involving_created_table(
    source_constraints: Dict[str, Any],
    created_table: str,
    before_schema: Dict[str, Any],
) -> List[Dict[str, Any]]:
    fks = []

    # created table -> existing table
    for fk in outgoing_fks(source_constraints, created_table):
        if table_exists(before_schema, fk.get("referenced_table", "")):
            fks.append({
                "source_table": created_table,
                "source_columns": copy.deepcopy(fk.get("columns", [])),
                "target_table": fk.get("referenced_table"),
                "target_columns": copy.deepcopy(fk.get("referenced_columns", [])),
            })

    # existing table -> created table
    for fk in incoming_fks(source_constraints, created_table):
        src_table = fk.get("table")
        if table_exists(before_schema, src_table):
            fks.append({
                "source_table": src_table,
                "source_columns": copy.deepcopy(fk.get("columns", [])),
                "target_table": created_table,
                "target_columns": copy.deepcopy(fk.get("referenced_columns", [])),
            })

    return fks


def build_proposal(
    decision: str,
    incoming_table: str,
    source_table: str,
    before_schema: Dict[str, Any],
    after_schema: Dict[str, Any],
    source_constraints: Dict[str, Any],
    source_to_incoming: Dict[str, str],
    hidden_columns: List[str] | None = None,
) -> Dict[str, Any]:
    hidden_columns = hidden_columns or []

    column_placements = {
        incoming_col: f"{source_table}.{source_col}"
        for source_col, incoming_col in source_to_incoming.items()
    }

    if decision == "extend_table":
        affected_tables = [source_table]
        protected_tables = [t for t in before_schema["tables"] if t != source_table]
        return {
            "decision": "extend_table",
            "incoming_table": incoming_table,
            "target_table": source_table,
            "created_table": None,
            "added_columns": {source_table: list(hidden_columns)},
            "column_placements": column_placements,
            "proposed_primary_keys": [],
            "proposed_foreign_keys": [],
            "affected_tables": affected_tables,
            "protected_tables": protected_tables,
        }

    if decision == "create_table":
        return {
            "decision": "create_table",
            "incoming_table": incoming_table,
            "target_table": None,
            "created_table": source_table,
            "added_columns": {},
            "column_placements": column_placements,
            "proposed_primary_keys": pk_fact(source_constraints, source_table),
            "proposed_foreign_keys": fks_involving_created_table(
                source_constraints=source_constraints,
                created_table=source_table,
                before_schema=before_schema,
            ),
            "affected_tables": [source_table],
            "protected_tables": list(before_schema["tables"].keys()),
        }

    if decision == "insert_table":
        return {
            "decision": "insert_table",
            "incoming_table": incoming_table,
            "target_table": source_table,
            "created_table": None,
            "added_columns": {},
            "column_placements": column_placements,
            "proposed_primary_keys": [],
            "proposed_foreign_keys": [],
            "affected_tables": [],
            "protected_tables": list(before_schema["tables"].keys()),
        }

    raise ValueError(f"Unsupported decision: {decision}")


def write_incoming(
    incoming_dir: Path,
    incoming_schema: Dict[str, Any],
    incoming_profile: Dict[str, Any],
    incoming_rows: List[Dict[str, Any]],
    incoming_columns: List[str],
) -> None:
    write_json(incoming_dir / "schema.json", incoming_schema)
    write_json(incoming_dir / "profile.json", incoming_profile)
    write_csv(incoming_dir / "table.csv", incoming_rows, incoming_columns)


def generate_case(
    case_dir: Path,
    case_index: int,
    decision: str,
    cfg: Dict[str, Any],
    rng: random.Random,
    source_schema: Dict[str, Any],
    source_constraints: Dict[str, Any],
    source_profiles: Dict[str, Any],
    source_rows: Dict[str, List[Dict[str, str]]],
    graph: Dict[str, Set[str]],
) -> None:
    max_attempts = 500

    for _attempt in range(max_attempts):
        after_tables = sample_after_tables(
            cfg=cfg,
            rng=rng,
            source_schema=source_schema,
            source_constraints=source_constraints,
            source_rows=source_rows,
            graph=graph,
        )

        source_candidates = source_candidates_for_decision(
            decision=decision,
            after_tables=after_tables,
            cfg=cfg,
            source_schema=source_schema,
            source_constraints=source_constraints,
            source_rows=source_rows,
        )

        if not source_candidates:
            continue

        source_table = rng.choice(source_candidates)
        after_table_cols = {table: table_column_order(source_schema, table) for table in after_tables}
        after_schema = make_schema_subset(source_schema, after_table_cols)
        after_constraints = filter_constraints(source_constraints, after_schema)
        after_rows = subset_rows_for_schema(source_rows, after_schema, cfg, rng)
        after_profiles = filter_profiles_by_schema(source_profiles, after_schema)

        if decision == "extend_table":
            pk = get_pk(source_constraints, source_table)
            all_cols = table_column_order(source_schema, source_table)
            non_key_cols = [col for col in all_cols if col not in set(pk)]
            hidden_rule = cfg["case_rules"]["extend_table"]["hidden_columns"]
            min_remaining = int(
                cfg["case_rules"]["extend_table"]
                .get("source_table_filters", {})
                .get("min_remaining_columns_after_hide", 2)
            )

            max_hide_by_remaining = max(0, len(all_cols) - min_remaining)

            max_hide = min(
                int(hidden_rule.get("max", 1)),
                max_hide_by_remaining,
                len(non_key_cols),
            )

            min_hide = int(hidden_rule.get("min", 1))

            if max_hide < min_hide:
                continue

            hidden_columns = random_column_subset(
                non_key_cols,
                min_hide,
                max_hide,
                rng,
            )

            source_columns = unique_keep_order(pk + hidden_columns)
            incoming_table = source_table

            before_schema, before_rows = remove_columns_from_schema_and_rows(
                after_schema,
                after_rows,
                source_table,
                hidden_columns,
            )

        elif decision == "create_table":
            hidden_columns = []
            source_columns = table_column_order(source_schema, source_table)
            incoming_table = source_table
            before_schema, before_rows = remove_table_from_schema_and_rows(
                after_schema,
                after_rows,
                source_table,
            )

        elif decision == "insert_table":
            pk = get_pk(source_constraints, source_table)
            all_cols = table_column_order(source_schema, source_table)
            non_key_cols = [col for col in all_cols if col not in set(pk)]
            projection_rule = cfg["case_rules"]["insert_table"]["incoming"].get("projection_columns", {})
            min_cols = int(projection_rule.get("min", 3))
            max_cols = int(projection_rule.get("max", 8))
            remaining_needed_min = max(0, min_cols - len(pk))
            remaining_max = max(0, max_cols - len(pk))
            projected_non_key_cols = random_column_subset(
                non_key_cols,
                remaining_needed_min,
                remaining_max,
                rng,
            )
            source_columns = unique_keep_order(pk + projected_non_key_cols)
            hidden_columns = []
            incoming_table = source_table
            before_schema = copy.deepcopy(after_schema)
            before_rows = copy.deepcopy(after_rows)

        else:
            raise ValueError(f"Unsupported decision: {decision}")

        if not source_columns:
            continue

        before_constraints = filter_constraints(source_constraints, before_schema)
        before_profiles = filter_profiles_by_schema(source_profiles, before_schema)

        incoming_table, source_to_incoming, tags = maybe_apply_perturbation(
            cfg=cfg,
            rng=rng,
            source_profiles=source_profiles,
            source_table=source_table,
            incoming_table=incoming_table,
            source_columns=source_columns,
        )
        source_to_incoming = maybe_shuffle_mapping_order(source_to_incoming, tags, rng)
        incoming_columns = list(source_to_incoming.values())

        base_rows = sample_rows_count(source_rows[source_table], cfg, rng)
        incoming_rows = project_rows_with_mapping(base_rows, source_to_incoming)
        incoming_schema = make_single_table_schema_with_mapping(
            source_schema=source_schema,
            source_table=source_table,
            incoming_table=incoming_table,
            column_mapping=source_to_incoming,
        )
        incoming_profile = make_incoming_profile_for_step_with_mapping(
            source_profiles=source_profiles,
            source_table=source_table,
            incoming_table=incoming_table,
            column_mapping=source_to_incoming,
        )

        proposal = build_proposal(
            decision=decision,
            incoming_table=incoming_table,
            source_table=source_table,
            before_schema=before_schema,
            after_schema=after_schema,
            source_constraints=source_constraints,
            source_to_incoming=source_to_incoming,
            hidden_columns=hidden_columns,
        )
        if tags:
            proposal["perturbations"] = tags

        if case_dir.exists():
            shutil.rmtree(case_dir)
        case_dir.mkdir(parents=True, exist_ok=True)

        write_rdb(
            case_dir / "existing",
            before_schema,
            before_constraints,
            before_rows,
            before_profiles,
        )
        write_incoming(
            case_dir / "incoming",
            incoming_schema,
            incoming_profile,
            incoming_rows,
            incoming_columns,
        )
        write_rdb(
            case_dir / "expected",
            after_schema,
            after_constraints,
            after_rows,
            after_profiles,
        )
        write_json(case_dir / "expected" / "proposal.json", proposal)
        return

    raise RuntimeError(
        f"Failed to generate case {case_index} for decision={decision} after {max_attempts} attempts."
    )


def copy_benchmark_config(yaml_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(yaml_path, output_dir / "benchmark_config.yaml")


def write_case_run_config(case_dir: Path, sample_num: int) -> None:
    """
    Generate the runtime config consumed by the pipeline for one benchmark case.

    Output:
        case_dir/config.yaml

    Layout used by the config:
        existing_rdb.path -> case_dir/existing
        steps[0].path     -> case_dir/incoming
    """
    proposal_path = case_dir / "expected" / "proposal.json"
    proposal = read_json(proposal_path) if proposal_path.exists() else {}

    incoming_table = proposal.get("incoming_table", "incoming")
    task_id = f"step_001_{to_snake_case(str(incoming_table))}"

    run_config = {
        "existing_rdb": {
            "path": str(case_dir / "existing"),
            "sample_num": sample_num,
        },
        "steps": [
            {
                "task_id": task_id,
                "path": str(case_dir / "incoming"),
                "sample_num": sample_num,
            }
        ],
    }

    config_path = case_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(run_config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def build_benchmark(yaml_path: Path) -> None:
    cfg = read_yaml(yaml_path)

    benchmark_cfg = cfg.get("benchmark", {})
    seed = int(benchmark_cfg.get("random_seed", cfg.get("random_seed", 42)))
    sample_num = resolve_sample_num(cfg)
    rng = random.Random(seed)
    output_dir = resolve_output_dir(cfg)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Keep a copy of the generation config for reproducibility.
    # The pipeline runtime config is generated separately as case_XXXX/config.yaml.
    copy_benchmark_config(yaml_path, output_dir)

    source_schema, source_constraints, source_profiles, source_rows = load_source_from_config(cfg)
    graph = build_fk_graph(source_schema, source_constraints)

    case_index = 1
    for decision in ["extend_table", "create_table", "insert_table"]:
        count = int(cfg.get("case_counts", {}).get(decision, 0))
        for _ in range(count):
            case_dir = output_dir / f"case_{case_index:04d}"
            generate_case(
                case_dir=case_dir,
                case_index=case_index,
                decision=decision,
                cfg=cfg,
                rng=rng,
                source_schema=source_schema,
                source_constraints=source_constraints,
                source_profiles=source_profiles,
                source_rows=source_rows,
                graph=graph,
            )
            write_case_run_config(case_dir=case_dir, sample_num=sample_num)
            case_index += 1

    print(f"Generated benchmark: {output_dir}")
    print(f"cases: {case_index - 1}")
    print(f"generation config copy: {output_dir / 'benchmark_config.yaml'}")
    print("runtime config: each case has its own config.yaml")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build local RDB schema-evolution benchmark cases from the new YAML config."
    )
    parser.add_argument("yaml_path", type=Path, help="Path to benchmark YAML file")
    args = parser.parse_args()

    build_benchmark(args.yaml_path)


if __name__ == "__main__":
    main()