from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from model.core.embedding_retrieval import (
    DEFAULT_EMBEDDING_MODEL,
    load_embedding_model,
    retrieve_column_candidates,
)
from model.utils.io import load_rdb, load_table


DEFAULT_K_VALUES = (1, 3, 5, 10, 20)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate embedding retrieval before integrating it into a model.",
    )
    parser.add_argument(
        "--cases-root",
        required=True,
        help="Benchmark split, for example data/Chinook/benchmarks/large.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=[DEFAULT_EMBEDDING_MODEL],
        help="One or more SentenceTransformer model names.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="JSON file used to save summaries and per-case evidence.",
    )
    parser.add_argument(
        "--k",
        nargs="+",
        type=int,
        default=list(DEFAULT_K_VALUES),
        help="Retrieval cutoffs to evaluate.",
    )
    parser.add_argument(
        "--cases",
        nargs="*",
        help="Optional case names. By default every case is evaluated.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    k_values = sorted(set(args.k))
    if not k_values or k_values[0] < 1:
        raise ValueError("Every k value must be at least 1.")

    cases = discover_cases(Path(args.cases_root), args.cases)
    result = {
        "cases_root": str(Path(args.cases_root)),
        "k_values": k_values,
        "case_count": len(cases),
        "models": [
            evaluate_model(model_name, cases, k_values)
            for model_name in args.models
        ],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print_summary(result)
    print(f"Saved embedding evaluation to {output_path}")


def discover_cases(
    cases_root: Path,
    requested_cases: list[str] | None,
) -> list[Path]:
    names = requested_cases or [path.name for path in sorted(cases_root.glob("case*"))]
    cases = []
    for name in names:
        case_path = cases_root / name
        required = [case_path / "config.yaml", case_path / "expected" / "proposal.json"]
        if not case_path.is_dir() or not all(path.is_file() for path in required):
            raise FileNotFoundError(f"Incomplete benchmark case: {case_path}")
        cases.append(case_path)
    if not cases:
        raise ValueError(f"No benchmark cases found under {cases_root}.")
    return cases


def evaluate_model(
    model_name: str,
    cases: list[Path],
    k_values: list[int],
) -> dict[str, Any]:
    embedding_model = load_embedding_model(model_name)
    started = time.perf_counter()
    case_results = [
        evaluate_case(
            case_path,
            embedding_model=embedding_model,
            retrieval_top_k=max(k_values),
            k_values=k_values,
        )
        for case_path in cases
    ]
    elapsed = time.perf_counter() - started
    return {
        "model": model_name,
        "summary": aggregate_results(case_results, k_values, elapsed),
        "cases": case_results,
    }


def evaluate_case(
    case_path: Path,
    *,
    embedding_model: Any,
    retrieval_top_k: int,
    k_values: list[int],
) -> dict[str, Any]:
    config = _load_yaml(case_path / "config.yaml")
    existing_config = config["existing_rdb"]
    step = config["steps"][0]
    existing_rdb = load_rdb(
        rdb_path=existing_config["path"],
        sample_num=existing_config["sample_num"],
    )
    incoming = load_table(
        table_path=step["path"],
        sample_num=step.get("sample_num", 0),
    )
    incoming_name, incoming_schema = _single_table(incoming["schema"])

    started = time.perf_counter()
    retrieved = retrieve_column_candidates(
        embedding_model=embedding_model,
        incoming_table_name=incoming_name,
        incoming_table=incoming_schema,
        incoming_values=incoming["sample_values"],
        existing_schema=existing_rdb["schema"],
        existing_values=existing_rdb["sample_values"],
        top_k=retrieval_top_k,
    )
    elapsed = time.perf_counter() - started

    expected = _load_json(case_path / "expected" / "proposal.json")
    expected_target = expected.get("target_table")
    table_ranking = rank_tables(retrieved)
    table_rank = _rank_of(table_ranking, expected_target)
    table_eligible = expected_target in existing_rdb["schema"].get("tables", {})

    column_results = []
    for source_column, placement in expected.get("column_placements", {}).items():
        expected_table, expected_column = parse_placement(placement)
        target_columns = (
            existing_rdb["schema"]
            .get("tables", {})
            .get(expected_table, {})
            .get("columns", {})
        )
        if expected_column not in target_columns:
            continue
        candidates = retrieved.get(source_column, [])
        exact_targets = [
            (item["target_table"], item["target_column"])
            for item in candidates
        ]
        rank = _rank_of(exact_targets, (expected_table, expected_column))
        column_results.append(
            {
                "source_column": source_column,
                "expected": f"{expected_table}.{expected_column}",
                "rank": rank,
                "hits": {str(k): rank is not None and rank <= k for k in k_values},
                "top_candidates": candidates[: min(5, len(candidates))],
            }
        )

    return {
        "case": case_path.name,
        "elapsed_seconds": round(elapsed, 6),
        "expected_target_table": expected_target,
        "table_eligible": table_eligible,
        "table_rank": table_rank if table_eligible else None,
        "table_hits": {
            str(k): table_eligible and table_rank is not None and table_rank <= k
            for k in k_values
        },
        "table_ranking": table_ranking[: min(10, len(table_ranking))],
        "eligible_column_count": len(column_results),
        "columns": column_results,
    }


def rank_tables(
    retrieved: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """Match Standard selector aggregation: mean best score over source columns."""

    source_count = max(len(retrieved), 1)
    scores_by_table: dict[str, dict[str, float]] = {}
    for source_column, candidates in retrieved.items():
        for candidate in candidates:
            table_name = candidate["target_table"]
            table_scores = scores_by_table.setdefault(table_name, {})
            table_scores[source_column] = max(
                table_scores.get(source_column, float("-inf")),
                float(candidate["retrieval_score"]),
            )
    scored_tables = [
        (
            sum(source_scores.values()) / source_count,
            table_name,
        )
        for table_name, source_scores in scores_by_table.items()
    ]
    scored_tables.sort(key=lambda item: (-item[0], item[1]))
    return [table_name for _, table_name in scored_tables]


def aggregate_results(
    cases: list[dict[str, Any]],
    k_values: list[int],
    elapsed: float,
) -> dict[str, Any]:
    eligible_tables = [case for case in cases if case["table_eligible"]]
    columns = [column for case in cases for column in case["columns"]]
    table_ranks = [case["table_rank"] for case in eligible_tables]
    column_ranks = [column["rank"] for column in columns]
    return {
        "elapsed_seconds": round(elapsed, 6),
        "mean_case_seconds": round(mean(case["elapsed_seconds"] for case in cases), 6),
        "eligible_table_cases": len(eligible_tables),
        "eligible_columns": len(columns),
        "table_hit_at_k": {
            str(k): _hit_rate(table_ranks, k)
            for k in k_values
        },
        "table_mrr": _mrr(table_ranks),
        "column_hit_at_k": {
            str(k): _hit_rate(column_ranks, k)
            for k in k_values
        },
        "column_mrr": _mrr(column_ranks),
    }


def parse_placement(placement: Any) -> tuple[str, str]:
    if isinstance(placement, str):
        table_name, separator, column_name = placement.partition(".")
        if separator:
            return table_name, column_name
    if isinstance(placement, dict):
        return str(placement.get("target_table", "")), str(
            placement.get("target_column", "")
        )
    return "", ""


def _hit_rate(ranks: list[int | None], k: int) -> float | None:
    if not ranks:
        return None
    return round(sum(rank is not None and rank <= k for rank in ranks) / len(ranks), 6)


def _mrr(ranks: list[int | None]) -> float | None:
    if not ranks:
        return None
    return round(sum(1.0 / rank for rank in ranks if rank is not None) / len(ranks), 6)


def _rank_of(items: list[Any], target: Any) -> int | None:
    try:
        return items.index(target) + 1
    except ValueError:
        return None


def _single_table(schema: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    tables = schema.get("tables", {})
    if len(tables) != 1:
        raise ValueError(f"Expected one incoming table, got {len(tables)}.")
    name = next(iter(tables))
    return name, tables[name]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def print_summary(result: dict[str, Any]) -> None:
    for item in result["models"]:
        summary = item["summary"]
        print(f"Model: {item['model']}")
        print(f"  Table Hit@K:  {summary['table_hit_at_k']}")
        print(f"  Table MRR:    {summary['table_mrr']}")
        print(f"  Column Hit@K: {summary['column_hit_at_k']}")
        print(f"  Column MRR:   {summary['column_mrr']}")
        print(f"  Time:         {summary['elapsed_seconds']} seconds")


if __name__ == "__main__":
    main()
