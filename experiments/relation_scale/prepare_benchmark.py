from __future__ import annotations

import argparse
import copy
import csv
import json
import random
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATASETS = ("Chinook", "Spider")
LEVELS: tuple[str | int, ...] = ("original", 25, 50, 100)
PER_OPERATION = 10
SEED = 42
OPERATIONS = ("insert_table", "extend_table", "create_table")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_rows(path: Path, limit: int = 3) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append(dict(row))
            if len(rows) >= limit:
                break
        return rows


def write_rows(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, restval="")
        writer.writeheader()
        writer.writerows(rows)


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return value or "table"


def source_database(case_dir: Path) -> str:
    metadata = case_dir / "case_metadata.json"
    if metadata.exists():
        return str(read_json(metadata).get("source_database", ""))
    return str(read_json(case_dir / "existing" / "schema.json").get("database", ""))


def select_base_cases(dataset: str) -> list[Path]:
    rng = random.Random(f"{SEED}:{dataset}")
    grouped: dict[str, list[Path]] = defaultdict(list)
    root = ROOT / "data" / dataset / "benchmarks"
    for split in ("small", "medium", "large"):
        for proposal_path in (root / split).glob("case_*/expected/proposal.json"):
            decision = read_json(proposal_path).get("decision")
            if decision in OPERATIONS:
                grouped[decision].append(proposal_path.parents[1])

    selected = []
    for operation in OPERATIONS:
        candidates = sorted(grouped[operation])
        rng.shuffle(candidates)
        if len(candidates) < PER_OPERATION:
            raise ValueError(f"Not enough {dataset} {operation} cases.")
        selected.extend(candidates[:PER_OPERATION])
    rng.shuffle(selected)
    return selected


def build_donor_pool() -> list[dict[str, Any]]:
    donors = []
    parsed_root = ROOT / "data" / "Spider" / "parsed"
    for database_dir in sorted(parsed_root.iterdir()):
        if not (database_dir / "schema.json").exists():
            continue
        schema = read_json(database_dir / "schema.json")
        profiles_path = database_dir / "profiles.json"
        profiles = read_json(profiles_path) if profiles_path.exists() else {"tables": {}}
        for table_name, table_schema in schema.get("tables", {}).items():
            csv_path = database_dir / "tables" / f"{table_name}.csv"
            if not csv_path.exists():
                continue
            donors.append({
                "database": database_dir.name,
                "table": table_name,
                "schema": table_schema,
                "profile": profiles.get("tables", {}).get(table_name),
                "rows": read_rows(csv_path),
            })
    if len(donors) < max(level for level in LEVELS if isinstance(level, int)):
        raise ValueError("Spider donor pool is too small.")
    return donors


def rename_donor(donor: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    name = f"d_{safe_name(donor['database'])}__{safe_name(donor['table'])}"
    copied = copy.deepcopy(donor)
    profile = copied.get("profile")
    if isinstance(profile, dict) and isinstance(profile.get("table"), dict):
        profile["table"]["name"] = name
    return name, copied


def add_distractors(case_dir: Path, donors: list[dict[str, Any]], target_count: int) -> list[str]:
    existing_schema = read_json(case_dir / "existing" / "schema.json")
    expected_schema = read_json(case_dir / "expected" / "schema.json")
    existing_profiles = read_json(case_dir / "existing" / "profiles.json")
    expected_profiles = read_json(case_dir / "expected" / "profiles.json")
    needed = max(0, target_count - len(existing_schema.get("tables", {})))
    added = []

    for donor in donors:
        if len(added) >= needed:
            break
        name, copied = rename_donor(donor)
        if name in existing_schema["tables"] or name in added:
            continue
        schema = copied["schema"]
        existing_schema["tables"][name] = copy.deepcopy(schema)
        expected_schema["tables"][name] = copy.deepcopy(schema)
        if copied.get("profile") is not None:
            existing_profiles.setdefault("tables", {})[name] = copy.deepcopy(copied["profile"])
            expected_profiles.setdefault("tables", {})[name] = copy.deepcopy(copied["profile"])
        columns = schema.get("column_order", list(schema.get("columns", {})))
        write_rows(case_dir / "existing" / "tables" / f"{name}.csv", copied["rows"], columns)
        write_rows(case_dir / "expected" / "tables" / f"{name}.csv", copied["rows"], columns)
        added.append(name)

    if len(added) != needed:
        raise ValueError(f"Could add only {len(added)} of {needed} distractors.")

    write_json(case_dir / "existing" / "schema.json", existing_schema)
    write_json(case_dir / "expected" / "schema.json", expected_schema)
    write_json(case_dir / "existing" / "profiles.json", existing_profiles)
    write_json(case_dir / "expected" / "profiles.json", expected_profiles)
    proposal_path = case_dir / "expected" / "proposal.json"
    proposal = read_json(proposal_path)
    proposal["protected_tables"] = list(dict.fromkeys(
        proposal.get("protected_tables", []) + added
    ))
    write_json(proposal_path, proposal)
    return added


def rewrite_config(case_dir: Path) -> None:
    incoming_schema = read_json(case_dir / "incoming" / "schema.json")
    incoming_name = next(iter(incoming_schema.get("tables", {})), "incoming")
    relative_case_dir = case_dir.relative_to(ROOT)
    config = {
        "existing_rdb": {"path": str(relative_case_dir / "existing"), "sample_num": 3},
        "steps": [{
            "task_id": f"step_001_{safe_name(incoming_name)}",
            "path": str(relative_case_dir / "incoming"),
            "sample_num": 3,
        }],
    }
    (case_dir / "config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    donor_pool = build_donor_pool()
    manifest = {"seed": SEED, "levels": list(LEVELS), "datasets": {}}

    for dataset in DATASETS:
        base_cases = select_base_cases(dataset)
        manifest["datasets"][dataset] = []
        for index, source_case in enumerate(base_cases, start=1):
            source_db = source_database(source_case)
            rng = random.Random(f"{SEED}:{dataset}:{source_case.parent.name}:{source_case.name}")
            eligible = [d for d in donor_pool if d["database"] != source_db]
            rng.shuffle(eligible)
            manifest_entry = {
                "generated_case": f"case_{index:04d}",
                "source_size": source_case.parent.name,
                "source_case": source_case.name,
                "source_database": source_db,
                "decision": read_json(source_case / "expected" / "proposal.json")["decision"],
            }
            manifest["datasets"][dataset].append(manifest_entry)

            for level in LEVELS:
                split = f"scale_{level}"
                destination = ROOT / "data" / dataset / "benchmarks" / split / f"case_{index:04d}"
                if destination.exists():
                    if not args.overwrite:
                        raise FileExistsError(
                            f"{destination} exists; pass --overwrite to replace generated splits."
                        )
                    shutil.rmtree(destination)
                shutil.copytree(source_case, destination)
                if isinstance(level, int):
                    add_distractors(destination, eligible, level)
                rewrite_config(destination)

    write_json(HERE / "benchmark_manifest.json", manifest)
    print(f"manifest: {HERE / 'benchmark_manifest.json'}")
    print("generated: 2 datasets x 4 scales x 30 cases")


if __name__ == "__main__":
    main()
