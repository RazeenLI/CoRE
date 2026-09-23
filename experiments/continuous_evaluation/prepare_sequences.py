from __future__ import annotations

import argparse
import copy
import csv
import json
import random
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SEED = 42
SEQUENCE_LENGTH = 10
SPIDER_DATABASES = (
    "cre_Drama_Workshop_Groups",
    "sakila_1",
    "assets_maintenance",
    "hospital_1",
    "department_store",
)


from data.form_benchmark import (  # noqa: E402
    build_proposal,
    filter_constraints,
    filter_profiles_by_schema,
    get_pk,
    make_incoming_profile_for_step_with_mapping,
    make_schema_subset,
    make_single_table_schema_with_mapping,
    project_rows,
    project_rows_with_mapping,
    read_json,
    table_column_order,
    write_incoming,
    write_json,
    write_rdb,
)


def load_source(source_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, list[dict[str, str]]]]:
    schema = read_json(source_dir / "schema.json")
    constraints = read_json(source_dir / "constraints.json")
    profiles = read_json(source_dir / "profiles.json")
    rows = {}
    for table in schema.get("tables", {}):
        path = source_dir / "tables" / f"{table}.csv"
        sampled = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                sampled.append(dict(row))
                if len(sampled) >= 6:
                    break
        rows[table] = sampled
    return schema, constraints, profiles, rows


def choose_plan(
    schema: dict[str, Any],
    constraints: dict[str, Any],
    rows: dict[str, list[dict[str, str]]],
    rng: random.Random,
) -> tuple[list[str], list[dict[str, Any]]]:
    available = [table for table in schema["tables"] if rows.get(table)]
    rng.shuffle(available)
    extend_candidates = [
        table for table in available
        if get_pk(constraints, table)
        and len([c for c in table_column_order(schema, table) if c not in set(get_pk(constraints, table))]) >= 1
        and len(table_column_order(schema, table)) >= 3
    ]
    if len(extend_candidates) < 4:
        raise ValueError("Source does not contain four usable Extend tables.")
    extend_tables = extend_candidates[:4]

    remaining = [table for table in available if table not in extend_tables]
    if len(remaining) < 6:
        raise ValueError("Source does not contain enough distinct sequence tables.")
    create_tables = []
    foreign_keys = constraints.get("constraints", {}).get("foreign_keys", {})
    for table in remaining:
        conflicts = False
        for chosen in create_tables:
            outgoing = foreign_keys.get(table, [])
            chosen_outgoing = foreign_keys.get(chosen, [])
            if any(fk.get("referenced_table") == chosen for fk in outgoing):
                conflicts = True
            if any(fk.get("referenced_table") == table for fk in chosen_outgoing):
                conflicts = True
        if not conflicts:
            create_tables.append(table)
        if len(create_tables) == 3:
            break
    if len(create_tables) < 3:
        raise ValueError("Could not choose three dependency-independent Create tables.")

    insert_candidates = [
        table for table in remaining
        if table not in create_tables and len(table_column_order(schema, table)) >= 2
    ]
    if len(insert_candidates) < 3:
        insert_candidates = [table for table in extend_tables if len(table_column_order(schema, table)) >= 2]
    insert_tables = insert_candidates[:3]
    required = list(dict.fromkeys(extend_tables + create_tables + insert_tables))

    neighbors = []
    for table, fks in foreign_keys.items():
        for fk in fks:
            referenced = fk.get("referenced_table")
            if table in required and referenced in schema["tables"]:
                neighbors.append(referenced)
            if referenced in required and table in schema["tables"]:
                neighbors.append(table)
    context = list(dict.fromkeys(required + neighbors + available))[:15]
    for table in required:
        if table not in context:
            context.append(table)

    plan = []
    for table in extend_tables:
        pk = get_pk(constraints, table)
        hidden = next(c for c in table_column_order(schema, table) if c not in set(pk))
        plan.append({"decision": "extend_table", "table": table, "hidden_column": hidden})
    plan.extend({"decision": "create_table", "table": table} for table in create_tables)
    plan.extend({"decision": "insert_table", "table": table} for table in insert_tables)
    rng.shuffle(plan)
    return context, plan


def initial_state(
    source_schema: dict[str, Any],
    source_constraints: dict[str, Any],
    source_profiles: dict[str, Any],
    source_rows: dict[str, list[dict[str, str]]],
    context: list[str],
    plan: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, list[dict[str, Any]]]]:
    create_tables = {step["table"] for step in plan if step["decision"] == "create_table"}
    hidden = {
        step["table"]: step["hidden_column"]
        for step in plan if step["decision"] == "extend_table"
    }
    table_columns = {}
    for table in context:
        if table in create_tables:
            continue
        columns = table_column_order(source_schema, table)
        if table in hidden:
            columns = [column for column in columns if column != hidden[table]]
        table_columns[table] = columns
    schema = make_schema_subset(source_schema, table_columns)
    constraints = filter_constraints(source_constraints, schema)
    profiles = filter_profiles_by_schema(source_profiles, schema)
    rows = {
        table: project_rows(source_rows.get(table, [])[:3], columns)
        for table, columns in table_columns.items()
    }
    return schema, constraints, profiles, rows


def apply_gold_step(
    step: dict[str, Any],
    schema: dict[str, Any],
    rows: dict[str, list[dict[str, Any]]],
    source_schema: dict[str, Any],
    source_rows: dict[str, list[dict[str, str]]],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    schema = copy.deepcopy(schema)
    rows = copy.deepcopy(rows)
    table = step["table"]
    decision = step["decision"]
    if decision == "create_table":
        schema["tables"][table] = copy.deepcopy(source_schema["tables"][table])
        columns = table_column_order(source_schema, table)
        schema["tables"][table]["column_order"] = columns
        rows[table] = project_rows(source_rows.get(table, [])[:3], columns)
    elif decision == "extend_table":
        column = step["hidden_column"]
        schema["tables"][table]["columns"][column] = copy.deepcopy(
            source_schema["tables"][table]["columns"][column]
        )
        source_order = table_column_order(source_schema, table)
        schema["tables"][table]["column_order"] = [
            name for name in source_order if name in schema["tables"][table]["columns"]
        ]
        for index, row in enumerate(rows.get(table, [])):
            if index < len(source_rows.get(table, [])):
                row[column] = source_rows[table][index].get(column, "")
    elif decision == "insert_table":
        columns = step["source_columns"]
        rows.setdefault(table, []).extend(project_rows(source_rows.get(table, [])[3:6], columns))
    return schema, rows


def incoming_for_step(
    step: dict[str, Any],
    source_schema: dict[str, Any],
    source_constraints: dict[str, Any],
    source_profiles: dict[str, Any],
    source_rows: dict[str, list[dict[str, str]]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    table = step["table"]
    decision = step["decision"]
    all_columns = table_column_order(source_schema, table)
    pk = get_pk(source_constraints, table)
    if decision == "extend_table":
        source_columns = list(dict.fromkeys(pk + [step["hidden_column"]]))
        row_slice = source_rows.get(table, [])[:3]
    elif decision == "insert_table":
        non_key = [column for column in all_columns if column not in set(pk)]
        source_columns = list(dict.fromkeys(pk + non_key[: max(0, 3 - len(pk))]))
        if len(source_columns) < 2:
            source_columns = all_columns[:3]
        step["source_columns"] = source_columns
        row_slice = source_rows.get(table, [])[3:6]
    else:
        source_columns = all_columns
        row_slice = source_rows.get(table, [])[:3]
    mapping = {column: column for column in source_columns}
    incoming_schema = make_single_table_schema_with_mapping(
        source_schema, table, table, mapping
    )
    incoming_profile = make_incoming_profile_for_step_with_mapping(
        source_profiles, table, table, mapping
    )
    incoming_rows = project_rows_with_mapping(row_slice, mapping)
    return incoming_schema, incoming_profile, incoming_rows, mapping


def generate_sequence(source_dir: Path, output_dir: Path, seed: int) -> None:
    source_schema, source_constraints, source_profiles, source_rows = load_source(source_dir)
    rng = random.Random(seed)
    context, plan = choose_plan(source_schema, source_constraints, source_rows, rng)
    schema, constraints, profiles, rows = initial_state(
        source_schema, source_constraints, source_profiles, source_rows, context, plan
    )
    write_rdb(output_dir / "initial", schema, constraints, rows, profiles)
    metadata = {
        "source": str(source_dir),
        "seed": seed,
        "length": SEQUENCE_LENGTH,
        "steps": [],
    }

    for index, step in enumerate(plan, start=1):
        step_dir = output_dir / "steps" / f"step_{index:02d}"
        before_schema = copy.deepcopy(schema)
        before_constraints = filter_constraints(source_constraints, before_schema)
        before_profiles = filter_profiles_by_schema(source_profiles, before_schema)
        write_rdb(step_dir / "oracle_existing", before_schema, before_constraints, rows, before_profiles)
        incoming_schema, incoming_profile, incoming_rows, mapping = incoming_for_step(
            step, source_schema, source_constraints, source_profiles, source_rows
        )
        write_incoming(
            step_dir / "incoming", incoming_schema, incoming_profile,
            incoming_rows, list(mapping.values())
        )
        schema, rows = apply_gold_step(step, schema, rows, source_schema, source_rows)
        constraints = filter_constraints(source_constraints, schema)
        profiles = filter_profiles_by_schema(source_profiles, schema)
        write_rdb(step_dir / "expected", schema, constraints, rows, profiles)
        proposal = build_proposal(
            decision=step["decision"],
            incoming_table=step["table"],
            source_table=step["table"],
            before_schema=before_schema,
            after_schema=schema,
            source_constraints=source_constraints,
            source_to_incoming=mapping,
            hidden_columns=[step["hidden_column"]] if step["decision"] == "extend_table" else [],
        )
        write_json(step_dir / "expected" / "proposal.json", proposal)
        metadata["steps"].append({
            "step": index,
            "decision": step["decision"],
            "table": step["table"],
            "path": str(step_dir),
        })
    write_json(output_dir / "sequence.json", metadata)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = ROOT / "data" / "continuous_benchmark"
    jobs = []
    for index, database in enumerate(SPIDER_DATABASES, start=1):
        jobs.append(("Spider", index, ROOT / "data" / "Spider" / "parsed" / database, SEED + index))
    for index in range(1, 6):
        jobs.append(("TPCDS", index, ROOT / "data" / "TPCDS" / "parsed", SEED + 100 + index))

    for dataset, index, source, seed in jobs:
        output = root / dataset / f"sequence_{index:03d}"
        if output.exists():
            if not args.overwrite:
                raise FileExistsError(f"{output} exists; pass --overwrite to replace it.")
            shutil.rmtree(output)
        generate_sequence(source, output, seed)
        print(f"generated {output}")


if __name__ == "__main__":
    main()
