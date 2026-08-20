from __future__ import annotations

from collections import defaultdict
from typing import Any

import torch

from model.agents.base_agent import BaseAgent
from model.utils.io import terminal_message
from model.utils.structure import get_column_values

from baselines.magneto.model.prompts import reranker_prompt


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"


class MagnetoMatcher(BaseAgent):
    """MPNet candidate retrieval followed by one Qwen reranking call."""

    def __init__(
        self,
        llm_client: Any,
        *,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
        retrieval_top_k: int = 20,
        embedding_model: Any | None = None,
    ) -> None:
        super().__init__(llm_client=llm_client, prompt_builder=reranker_prompt)
        if retrieval_top_k < 1:
            raise ValueError("retrieval_top_k must be at least 1.")
        self.retrieval_top_k = retrieval_top_k
        self.embedding_model_name = embedding_model_name
        self.embedding_model = embedding_model or load_embedding_model(
            embedding_model_name
        )

    def __call__(
        self,
        *,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
        existing_schema: dict[str, Any],
        existing_values: dict[str, list[dict[str, Any]]],
        existing_profiles: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Profiles are intentionally not used by the retriever. Magneto encodes
        # headers and values; using Standard's LLM-generated profiles here would
        # give this baseline additional information.
        del existing_profiles
        incoming_name, incoming_table = self._extract_single_table(incoming_schema)
        retrieved = retrieve_column_candidates(
            embedding_model=self.embedding_model,
            incoming_table_name=incoming_name,
            incoming_table=incoming_table,
            incoming_values=incoming_values,
            existing_schema=existing_schema,
            existing_values=existing_values,
            top_k=self.retrieval_top_k,
        )
        terminal_message(
            "info",
            f"Magneto MPNet retrieved Top-{self.retrieval_top_k} candidates per incoming column.",
            "\t",
        )

        prompt_input = {
            "incoming_table": {
                "name": incoming_name,
                "columns": {
                    name: {
                        "type": schema.get("type"),
                        "sample_values": get_column_values(
                            rows=incoming_values,
                            column_name=name,
                        ),
                    }
                    for name, schema in incoming_table.get("columns", {}).items()
                },
            },
            "retrieved_column_candidates": retrieved,
        }
        raw = self._generate_json(self.prompt_builder(prompt_input))
        result = normalize_reranker_output(
            raw=raw,
            incoming_columns=list(incoming_table.get("columns", {})),
            retrieved=retrieved,
        )
        result["retrieval"] = {
            "embedding_model": self.embedding_model_name,
            "top_k_per_source_column": self.retrieval_top_k,
            "column_candidates": retrieved,
        }
        return result


def load_embedding_model(model_name: str) -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "The Magneto baseline requires sentence-transformers. "
            "Install baselines/magneto/requirements.txt in the active environment."
        ) from exc
    return SentenceTransformer(model_name)


def retrieve_column_candidates(
    *,
    embedding_model: Any,
    incoming_table_name: str,
    incoming_table: dict[str, Any],
    incoming_values: list[dict[str, Any]],
    existing_schema: dict[str, Any],
    existing_values: dict[str, list[dict[str, Any]]],
    top_k: int,
) -> dict[str, list[dict[str, Any]]]:
    """Retrieve target columns with normalized MPNet cosine similarity."""

    source_items = [
        {
            "source_column": column_name,
            "text": serialize_column(
                table_name=incoming_table_name,
                column_name=column_name,
                column_schema=column_schema,
                values=get_column_values(incoming_values, column_name),
            ),
        }
        for column_name, column_schema in incoming_table.get("columns", {}).items()
    ]
    target_items = []
    for table_name, table_schema in existing_schema.get("tables", {}).items():
        rows = existing_values.get(table_name, [])
        for column_name, column_schema in table_schema.get("columns", {}).items():
            target_items.append(
                {
                    "target_table": table_name,
                    "target_column": column_name,
                    "target_type": column_schema.get("type"),
                    "text": serialize_column(
                        table_name=table_name,
                        column_name=column_name,
                        column_schema=column_schema,
                        values=get_column_values(rows, column_name),
                    ),
                }
            )

    if not source_items or not target_items:
        return {item["source_column"]: [] for item in source_items}

    source_embeddings = embedding_model.encode(
        [item["text"] for item in source_items],
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    target_embeddings = embedding_model.encode(
        [item["text"] for item in target_items],
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    similarities = torch.as_tensor(source_embeddings) @ torch.as_tensor(
        target_embeddings
    ).T

    result: dict[str, list[dict[str, Any]]] = {}
    candidate_count = min(top_k, len(target_items))
    for source_index, source_item in enumerate(source_items):
        scores, indices = torch.topk(similarities[source_index], candidate_count)
        candidates = []
        for score, target_index in zip(scores.tolist(), indices.tolist()):
            target = target_items[target_index]
            candidates.append(
                {
                    "target_table": target["target_table"],
                    "target_column": target["target_column"],
                    "target_type": target["target_type"],
                    "retrieval_score": round(float(score), 6),
                }
            )
        result[source_item["source_column"]] = candidates
    return result


def serialize_column(
    *,
    table_name: str,
    column_name: str,
    column_schema: dict[str, Any],
    values: list[Any],
) -> str:
    """Serialize header and sampled values for the Magneto encoder."""

    rendered_values = ", ".join(str(value) for value in values if value is not None)
    return (
        f"Table: {table_name}. Column: {column_name}. "
        f"Type: {column_schema.get('type', 'unknown')}. Values: {rendered_values}."
    )


def normalize_reranker_output(
    *,
    raw: dict[str, Any],
    incoming_columns: list[str],
    retrieved: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Validate retrieved pairs, then aggregate column matches by table."""

    allowed = {
        source: {
            (candidate["target_table"], candidate["target_column"]): candidate
            for candidate in candidates
        }
        for source, candidates in retrieved.items()
    }
    raw_matches = raw.get("column_matches", {})
    if not isinstance(raw_matches, dict):
        raw_matches = {}
    accepted_by_source: dict[str, list[dict[str, Any]]] = {}

    for source_column in incoming_columns:
        candidates = []
        seen: set[tuple[str, str]] = set()
        raw_candidates = raw_matches.get(source_column, [])
        if not isinstance(raw_candidates, list):
            raw_candidates = []
        for item in raw_candidates:
            if not isinstance(item, dict):
                continue
            key = (item.get("target_table"), item.get("target_column"))
            if key not in allowed.get(source_column, {}) or key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "target_table": key[0],
                    "target_column": key[1],
                    "confidence": clamp01(item.get("confidence", 0.0)),
                    "retrieval_score": allowed[source_column][key]["retrieval_score"],
                }
            )
        candidates.sort(key=lambda item: -item["confidence"])
        unique_table_candidates = []
        seen_tables: set[str] = set()
        for candidate in candidates:
            target_table = candidate["target_table"]
            if target_table in seen_tables:
                continue
            seen_tables.add(target_table)
            unique_table_candidates.append(candidate)
            if len(unique_table_candidates) == 10:
                break
        accepted_by_source[source_column] = unique_table_candidates

    tables = {
        item["target_table"]
        for candidates in retrieved.values()
        for item in candidates
    }
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    table_retrieval_scores: dict[str, list[float]] = defaultdict(list)
    for table_name in tables:
        for source_column in incoming_columns:
            table_candidates = [
                {
                    "target_column": item["target_column"],
                    "confidence": item["confidence"],
                    "reason": "Qwen reranking of an MPNet-retrieved candidate.",
                }
                for item in accepted_by_source[source_column]
                if item["target_table"] == table_name
            ]
            grouped[table_name][source_column] = table_candidates
            retrieval_candidates = [
                item["retrieval_score"]
                for item in retrieved.get(source_column, [])
                if item["target_table"] == table_name
            ]
            if retrieval_candidates:
                table_retrieval_scores[table_name].append(max(retrieval_candidates))

    table_matches = []
    denominator = max(len(incoming_columns), 1)
    for table_name, column_matches in grouped.items():
        best_scores = [
            candidates[0]["confidence"] if candidates else 0.0
            for candidates in column_matches.values()
        ]
        confidence = sum(best_scores) / denominator
        retrieval_score = (
            sum(table_retrieval_scores[table_name]) / denominator
            if table_retrieval_scores[table_name]
            else 0.0
        )
        table_matches.append(
            {
                "target_table": table_name,
                "confidence": confidence,
                "column_matches": column_matches,
                "unmatched_source_columns": [
                    source for source, candidates in column_matches.items() if not candidates
                ],
                "retrieval_score": retrieval_score,
            }
        )
    table_matches.sort(
        key=lambda item: (
            -item["confidence"],
            -item["retrieval_score"],
            item["target_table"],
        )
    )
    return {"table_matches": table_matches}

def clamp01(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0

    if number < 0.0:
        return 0.0

    if number > 1.0:
        return 1.0

    return number