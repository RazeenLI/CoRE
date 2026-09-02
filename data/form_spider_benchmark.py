#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import csv
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from data.form_benchmark import (
        all_source_tables,
        build_fk_graph,
        generate_case,
        load_source_from_config,
        read_json,
        read_yaml,
        source_candidates_for_decision,
        write_case_run_config,
    )
except ModuleNotFoundError:  # Direct execution: python data/form_spider_benchmark.py
    from form_benchmark import (
        all_source_tables,
        build_fk_graph,
        generate_case,
        load_source_from_config,
        read_json,
        read_yaml,
        source_candidates_for_decision,
        write_case_run_config,
    )


DECISIONS = ("extend_table", "create_table", "insert_table")


def load_first_rows(parsed_dir: Path, tables: list[str]) -> dict[str, list[dict[str, str]]]:
    rows: dict[str, list[dict[str, str]]] = {}
    for table in tables:
        path = parsed_dir / "tables" / f"{table}.csv"
        with path.open("r", newline="", encoding="utf-8") as file:
            row = next(csv.DictReader(file), None)
        rows[table] = [dict(row)] if row is not None else []
    return rows


def inspect_eligibility(cfg: dict[str, Any]) -> dict[str, Any]:
    parsed_root = Path(cfg["benchmark"]["source_root"])
    min_tables = int(cfg["size"]["after_table_count"]["min"])
    records: list[dict[str, Any]] = []
    missing_profiles: list[str] = []

    parsed_dirs = sorted(path.parent for path in parsed_root.glob("*/schema.json"))
    for parsed_dir in parsed_dirs:
        profiles_path = parsed_dir / "profiles.json"
        if not profiles_path.is_file():
            missing_profiles.append(parsed_dir.name)
            continue
        schema = read_json(parsed_dir / "schema.json")
        constraints = read_json(parsed_dir / "constraints.json")
        profiles = read_json(profiles_path)
        tables = all_source_tables(schema)
        rows = load_first_rows(parsed_dir, tables)
        candidates = {decision: [] for decision in DECISIONS}
        if len(tables) >= min_tables:
            for decision in DECISIONS:
                candidates[decision] = source_candidates_for_decision(
                    decision=decision,
                    after_tables=tables,
                    cfg=cfg,
                    source_schema=schema,
                    source_constraints=constraints,
                    source_rows=rows,
                )
        records.append(
            {
                "source_database": schema.get("database", parsed_dir.name),
                "parsed_dir": str(parsed_dir),
                "table_count": len(tables),
                "profile_table_count": len(profiles.get("tables", {})),
                "candidates": candidates,
                "candidate_counts": {
                    decision: len(candidates[decision]) for decision in DECISIONS
                },
            }
        )

    eligible_counts = {
        decision: sum(record["candidate_counts"][decision] > 0 for record in records)
        for decision in DECISIONS
    }
    candidate_counts = {
        decision: sum(record["candidate_counts"][decision] for record in records)
        for decision in DECISIONS
    }
    return {
        "size_level": cfg["benchmark"]["size_level"],
        "after_table_count": cfg["size"]["after_table_count"],
        "parsed_database_count": len(parsed_dirs),
        "complete_profile_database_count": len(parsed_dirs) - len(missing_profiles),
        "missing_profiles": missing_profiles,
        "eligible_database_counts": eligible_counts,
        "candidate_table_counts": candidate_counts,
        "databases": records,
    }


def allocate_cases(
    cfg: dict[str, Any],
    inventory: dict[str, Any],
) -> list[dict[str, Any]]:
    cap = int(cfg["benchmark"]["max_cases_per_database"])
    usage: dict[str, int] = defaultdict(int)
    decision_usage: dict[tuple[str, str], int] = defaultdict(int)
    assignments: list[dict[str, Any]] = []
    records = inventory["databases"]

    for decision in DECISIONS:
        requested = int(cfg["case_counts"].get(decision, 0))
        eligible = [record for record in records if record["candidate_counts"][decision] > 0]
        for _ in range(requested):
            available = [
                record for record in eligible
                if usage[record["source_database"]] < cap
            ]
            if not available:
                raise RuntimeError(
                    f"Cannot allocate {requested} {decision} cases with "
                    f"max_cases_per_database={cap}."
                )
            selected = min(
                available,
                key=lambda record: (
                    decision_usage[(record["source_database"], decision)],
                    usage[record["source_database"]],
                    -record["candidate_counts"][decision],
                    record["source_database"],
                ),
            )
            database = selected["source_database"]
            assignments.append(
                {
                    "decision": decision,
                    "source_database": database,
                    "parsed_dir": selected["parsed_dir"],
                }
            )
            usage[database] += 1
            decision_usage[(database, decision)] += 1

    rng = random.Random(int(cfg["benchmark"].get("random_seed", 42)))
    rng.shuffle(assignments)
    for index, assignment in enumerate(assignments, start=1):
        assignment["case_index"] = index
    return assignments


def case_signature(case_dir: Path, source_database: str) -> str:
    proposal = read_json(case_dir / "expected" / "proposal.json")
    incoming_schema = read_json(case_dir / "incoming" / "schema.json")
    existing_schema = read_json(case_dir / "existing" / "schema.json")
    signature = {
        "source_database": source_database,
        "decision": proposal.get("decision"),
        "target_table": proposal.get("target_table"),
        "created_table": proposal.get("created_table"),
        "incoming_table": proposal.get("incoming_table"),
        "incoming_schema": incoming_schema.get("tables", {}),
        "existing_tables": sorted(existing_schema.get("tables", {})),
        "perturbations": proposal.get("perturbations", []),
    }
    return json.dumps(signature, sort_keys=True, ensure_ascii=False)


def build_spider_benchmark(config_path: Path, overwrite: bool = False) -> None:
    cfg = read_yaml(config_path)
    output_dir = Path(cfg["benchmark"]["output_dir"])
    inventory = inspect_eligibility(cfg)
    inventory_path = Path(cfg["benchmark"].get(
        "inventory_path",
        f"data/Spider/inventory_{cfg['benchmark']['size_level']}.json",
    ))
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    if inventory["missing_profiles"]:
        raise RuntimeError(
            "Profiling is incomplete. Missing profiles for: "
            + ", ".join(inventory["missing_profiles"])
        )

    assignments = allocate_cases(cfg, inventory)
    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise FileExistsError(f"Output directory is not empty: {output_dir}; use --overwrite")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(config_path, output_dir / "benchmark_config.yaml")
    (output_dir / "allocation.json").write_text(
        json.dumps(assignments, indent=2) + "\n", encoding="utf-8"
    )

    assignments_by_database: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for assignment in assignments:
        assignments_by_database[assignment["source_database"]].append(assignment)

    signatures: set[str] = set()
    sample_num = int(cfg["benchmark"].get("sample_num", 3))
    base_seed = int(cfg["benchmark"].get("random_seed", 42))
    for database_index, database in enumerate(sorted(assignments_by_database), start=1):
        database_cfg = copy.deepcopy(cfg)
        database_cfg["benchmark"]["source_path"] = assignments_by_database[database][0]["parsed_dir"]
        schema, constraints, profiles, rows = load_source_from_config(database_cfg)
        graph = build_fk_graph(schema, constraints)
        for assignment in assignments_by_database[database]:
            case_index = int(assignment["case_index"])
            case_dir = output_dir / f"case_{case_index:04d}"
            for duplicate_attempt in range(20):
                rng = random.Random(base_seed + case_index * 1009 + duplicate_attempt)
                generate_case(
                    case_dir=case_dir,
                    case_index=case_index,
                    decision=assignment["decision"],
                    cfg=database_cfg,
                    rng=rng,
                    source_schema=schema,
                    source_constraints=constraints,
                    source_profiles=profiles,
                    source_rows=rows,
                    graph=graph,
                )
                signature = case_signature(case_dir, database)
                if signature not in signatures:
                    signatures.add(signature)
                    break
            else:
                raise RuntimeError(f"Could not generate a unique case for {database} case_{case_index:04d}")

            write_case_run_config(case_dir, sample_num)
            proposal = read_json(case_dir / "expected" / "proposal.json")
            metadata = {
                "dataset": "Spider",
                "size": cfg["benchmark"]["size_level"],
                "source_database": database,
                "decision": assignment["decision"],
                "source_table": proposal.get("created_table") or proposal.get("target_table"),
            }
            (case_dir / "case_metadata.json").write_text(
                json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
            )
        print(
            f"[{database_index}/{len(assignments_by_database)}] {database}: "
            f"cases={len(assignments_by_database[database])}"
        )

    print(f"Generated Spider benchmark: {output_dir}")
    print(f"cases: {len(assignments)}")
    print(f"inventory: {inventory_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect or build a multi-database Spider benchmark.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.inventory_only:
        cfg = read_yaml(args.config)
        inventory = inspect_eligibility(cfg)
        output_path = Path(cfg["benchmark"].get(
            "inventory_path",
            f"data/Spider/inventory_{cfg['benchmark']['size_level']}.json",
        ))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in inventory.items() if key != "databases"}, indent=2))
        print(f"inventory: {output_path}")
        return

    build_spider_benchmark(args.config, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
