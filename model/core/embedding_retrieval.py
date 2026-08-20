from __future__ import annotations

from collections import defaultdict
from typing import Any

import torch
from model.utils.structure import get_column_values


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"

def load_embedding_model(model_name: str) -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "MPNet retrieval requires sentence-transformers. "
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