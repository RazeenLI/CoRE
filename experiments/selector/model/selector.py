from __future__ import annotations

from collections import defaultdict
from typing import Any

from baselines.magneto.model.matcher import (
    DEFAULT_EMBEDDING_MODEL,
    load_embedding_model,
    retrieve_column_candidates,
)
from model.utils.io import terminal_message


class CandidateSelector:
    """Use MPNet to select high-recall context without making a decision."""

    def __init__(
        self,
        *,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
        column_top_k: int = 20,
        table_top_k: int = 5,
        embedding_model: Any | None = None,
    ) -> None:
        if column_top_k < 1 or table_top_k < 1:
            raise ValueError("Selector top-k values must be at least 1.")
        self.embedding_model_name = embedding_model_name
        self.column_top_k = column_top_k
        self.table_top_k = table_top_k
        # Load lazily so the shared pipeline places Qwen before MPNet, matching
        # the already-tested Magneto device initialization order.
        self.embedding_model = embedding_model

    def __call__(
        self,
        *,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
        existing_schema: dict[str, Any],
        existing_values: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        incoming_name, incoming_table = _extract_single_table(incoming_schema)
        if self.embedding_model is None:
            self.embedding_model = load_embedding_model(self.embedding_model_name)
        retrieved = retrieve_column_candidates(
            embedding_model=self.embedding_model,
            incoming_table_name=incoming_name,
            incoming_table=incoming_table,
            incoming_values=incoming_values,
            existing_schema=existing_schema,
            existing_values=existing_values,
            top_k=self.column_top_k,
        )
        table_matches = _aggregate_table_candidates(retrieved)
        selected_table_matches = table_matches[: self.table_top_k]
        selected_tables = [
            item["target_table"]
            for item in selected_table_matches
        ]
        selected_candidates = _compact_column_candidates(selected_table_matches)
        terminal_message(
            "info",
            f"MPNet selector retained {len(selected_tables)} table candidates: {selected_tables}.",
            "\t",
        )
        return {
            "selector": "sentence_transformer",
            "embedding_model": self.embedding_model_name,
            "column_top_k": self.column_top_k,
            "table_top_k": self.table_top_k,
            "selected_tables": selected_tables,
            "column_candidates": selected_candidates,
            "table_matches": selected_table_matches,
        }


def _extract_single_table(
    incoming_schema: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    tables = incoming_schema.get("tables", {})
    if len(tables) != 1:
        raise ValueError(f"Exactly one incoming table is required, got {len(tables)}.")
    name = next(iter(tables))
    return name, tables[name]


def _compact_column_candidates(
    table_matches: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for table_match in table_matches:
        table_name = table_match["target_table"]
        for source_column, candidates in table_match["column_matches"].items():
            if not candidates:
                continue
            candidate = candidates[0]
            result[source_column].append(
                {
                    "target_table": table_name,
                    "target_column": candidate["target_column"],
                    "retrieval_score": candidate["confidence"],
                }
            )
    return dict(result)


def _aggregate_table_candidates(
    retrieved: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    by_table: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for source_column, candidates in retrieved.items():
        for candidate in candidates:
            by_table[candidate["target_table"]][source_column].append(candidate)

    denominator = max(len(retrieved), 1)
    results = []
    for table_name, source_candidates in by_table.items():
        column_matches: dict[str, list[dict[str, Any]]] = {}
        best_scores = []
        for source_column in retrieved:
            candidates = sorted(
                source_candidates.get(source_column, []),
                key=lambda item: -item["retrieval_score"],
            )
            best = candidates[:1]
            column_matches[source_column] = [
                {
                    "target_column": item["target_column"],
                    "confidence": item["retrieval_score"],
                    "reason": "MPNet retrieval evidence; not a final match.",
                }
                for item in best
            ]
            best_scores.append(best[0]["retrieval_score"] if best else 0.0)
        results.append(
            {
                "target_table": table_name,
                "confidence": sum(best_scores) / denominator,
                "column_matches": column_matches,
                "unmatched_source_columns": [
                    source for source, candidates in column_matches.items() if not candidates
                ],
                "reason": "Candidate-table score aggregated from MPNet column retrieval.",
            }
        )
    results.sort(key=lambda item: (-item["confidence"], item["target_table"]))
    return results
