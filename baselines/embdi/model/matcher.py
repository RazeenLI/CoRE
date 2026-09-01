from __future__ import annotations

import math
import random
import re
from collections import defaultdict
from typing import Any

from baselines.discovery.model.common import (
    cosine_similarity,
    extract_single_table,
    matches_from_scores,
)
from model.utils.io import terminal_message


class EmbDIMatcher:
    """EmbDI graph, random-walk, and Skip-gram schema matcher.

    The original Gensim training backend is replaced by an equivalent
    negative-sampling Skip-gram objective in the project's PyTorch runtime.
    Graph construction and training are repeated for every benchmark case.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.assignment_threshold = float(config.get("assignment_threshold", 0.55))
        self.dimensions = int(config.get("dimensions", 100))
        self.walk_length = int(config.get("walk_length", 20))
        self.walks_per_node = int(config.get("walks_per_node", 10))
        self.window_size = int(config.get("window_size", 3))
        self.epochs = int(config.get("epochs", 5))
        self.negative_samples = int(config.get("negative_samples", 5))
        self.learning_rate = float(config.get("learning_rate", 0.025))
        self.batch_size = int(config.get("batch_size", 2048))
        self.max_training_pairs = int(config.get("max_training_pairs", 200000))
        self.seed = int(config.get("seed", 0))
        self.device = str(config.get("device", "cpu"))

    def __call__(
        self,
        *,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
        existing_schema: dict[str, Any],
        existing_values: dict[str, list[dict[str, Any]]],
        existing_profiles: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del existing_profiles
        incoming_name, incoming_table = extract_single_table(incoming_schema)
        source_columns = list(incoming_table.get("columns", {}))
        tables = [("incoming", source_columns, incoming_values)]
        for table_name, table_schema in existing_schema.get("tables", {}).items():
            tables.append((table_name, list(table_schema.get("columns", {})), existing_values.get(table_name, [])))

        graph, column_nodes = build_embdi_graph(tables)
        vectors = train_graph_embeddings(
            graph=graph,
            dimensions=self.dimensions,
            walk_length=self.walk_length,
            walks_per_node=self.walks_per_node,
            window_size=self.window_size,
            epochs=self.epochs,
            negative_samples=self.negative_samples,
            learning_rate=self.learning_rate,
            batch_size=self.batch_size,
            max_training_pairs=self.max_training_pairs,
            seed=self.seed,
            device=self.device,
        )

        table_matches = []
        for target_table, target_schema in existing_schema.get("tables", {}).items():
            target_columns = list(target_schema.get("columns", {}))
            scores = []
            for source_column in source_columns:
                source_vector = vectors.get(column_nodes[("incoming", source_column)])
                row = []
                for target_column in target_columns:
                    target_vector = vectors.get(column_nodes[(target_table, target_column)])
                    row.append(
                        cosine_similarity(source_vector, target_vector)
                        if source_vector is not None and target_vector is not None else 0.0
                    )
                scores.append(row)
            table_matches.append(matches_from_scores(
                target_table=target_table,
                source_columns=source_columns,
                target_columns=target_columns,
                incoming_table=incoming_table,
                target_schema=target_schema,
                scores=scores,
                assignment_threshold=self.assignment_threshold,
                reason="EmbDI column-node cosine similarity after case-local training.",
            ))
        table_matches.sort(key=lambda item: (-item["confidence"], item["target_table"]))
        terminal_message(
            "success",
            f"EmbDI trained case-local graph embeddings and matched '{incoming_name}' "
            f"against {len(table_matches)} existing tables.",
            "\t",
        )
        return {
            "matcher": "embdi",
            "training_scope": "current_case_existing_rdb_plus_incoming",
            "table_matches": table_matches,
        }


def normalize_cell(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", "_", str(value).strip().lower())
    if not text or text in {"nan", "none", "null", "unknown"}:
        return None
    return text


def build_embdi_graph(
    tables: list[tuple[str, list[str], list[dict[str, Any]]]],
) -> tuple[dict[str, set[str]], dict[tuple[str, str], str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    column_nodes: dict[tuple[str, str], str] = {}
    for table_name, columns, rows in tables:
        for column in columns:
            node = f"cid::{table_name}::{column}"
            column_nodes[(table_name, column)] = node
            graph[node]
        for row_index, row in enumerate(rows):
            row_node = f"rid::{table_name}::{row_index}"
            graph[row_node]
            for column in columns:
                value = normalize_cell(row.get(column))
                if value is None:
                    continue
                value_node = f"tt::{value}"
                column_node = column_nodes[(table_name, column)]
                add_edge(graph, row_node, value_node)
                add_edge(graph, value_node, column_node)
    return dict(graph), column_nodes


def add_edge(graph: dict[str, set[str]], left: str, right: str) -> None:
    graph[left].add(right)
    graph[right].add(left)


def generate_walks(
    graph: dict[str, set[str]], *, walk_length: int, walks_per_node: int, seed: int
) -> list[list[str]]:
    rng = random.Random(seed)
    walks = []
    active_nodes = sorted(node for node, neighbors in graph.items() if neighbors)
    for node in active_nodes:
        for _ in range(walks_per_node):
            walk = [node]
            previous = None
            while len(walk) < walk_length:
                candidates = sorted(graph[walk[-1]])
                if previous is not None and len(candidates) > 1:
                    candidates = [candidate for candidate in candidates if candidate != previous]
                if not candidates:
                    break
                previous, next_node = walk[-1], rng.choice(candidates)
                walk.append(next_node)
            walks.append(walk)
    return walks


def skipgram_pairs(
    walks: list[list[str]], node_to_index: dict[str, int], window_size: int
) -> list[tuple[int, int]]:
    pairs = []
    for walk in walks:
        encoded = [node_to_index[node] for node in walk]
        for center_index, center in enumerate(encoded):
            left = max(0, center_index - window_size)
            right = min(len(encoded), center_index + window_size + 1)
            for context_index in range(left, right):
                if context_index != center_index:
                    pairs.append((center, encoded[context_index]))
    return pairs


def train_graph_embeddings(
    *,
    graph: dict[str, set[str]],
    dimensions: int,
    walk_length: int,
    walks_per_node: int,
    window_size: int,
    epochs: int,
    negative_samples: int,
    learning_rate: float,
    batch_size: int,
    max_training_pairs: int,
    seed: int,
    device: str,
) -> dict[str, Any]:
    try:
        import torch
        import torch.nn.functional as functional
    except ImportError as exc:
        raise ImportError("EmbDI requires PyTorch from the experiment environment.") from exc

    active_nodes = sorted(node for node, neighbors in graph.items() if neighbors)
    if not active_nodes:
        return {}
    node_to_index = {node: index for index, node in enumerate(active_nodes)}
    walks = generate_walks(
        graph,
        walk_length=walk_length,
        walks_per_node=walks_per_node,
        seed=seed,
    )
    pairs = skipgram_pairs(walks, node_to_index, window_size)
    rng = random.Random(seed)
    if len(pairs) > max_training_pairs:
        pairs = rng.sample(pairs, max_training_pairs)
    if not pairs:
        return {}

    torch.manual_seed(seed)
    requested_device = torch.device(device)
    if requested_device.type == "cuda" and not torch.cuda.is_available():
        requested_device = torch.device("cpu")
    vocabulary_size = len(active_nodes)
    input_embeddings = torch.nn.Embedding(vocabulary_size, dimensions).to(requested_device)
    output_embeddings = torch.nn.Embedding(vocabulary_size, dimensions).to(requested_device)
    bound = 0.5 / max(1, dimensions)
    torch.nn.init.uniform_(input_embeddings.weight, -bound, bound)
    torch.nn.init.zeros_(output_embeddings.weight)
    optimizer = torch.optim.SGD(
        list(input_embeddings.parameters()) + list(output_embeddings.parameters()),
        lr=learning_rate,
    )
    degree_weights = torch.tensor(
        [math.pow(max(1, len(graph[node])), 0.75) for node in active_nodes],
        dtype=torch.float32,
        device=requested_device,
    )
    pair_tensor = torch.tensor(pairs, dtype=torch.long)
    generator = torch.Generator().manual_seed(seed)
    for _ in range(epochs):
        order = torch.randperm(len(pair_tensor), generator=generator)
        for offset in range(0, len(pair_tensor), batch_size):
            batch = pair_tensor[order[offset:offset + batch_size]].to(requested_device)
            centers, contexts = batch[:, 0], batch[:, 1]
            center_vectors = input_embeddings(centers)
            context_vectors = output_embeddings(contexts)
            positive = torch.sum(center_vectors * context_vectors, dim=1)
            negatives = torch.multinomial(
                degree_weights,
                num_samples=len(batch) * negative_samples,
                replacement=True,
            ).view(len(batch), negative_samples)
            negative_vectors = output_embeddings(negatives)
            negative = torch.bmm(negative_vectors, center_vectors.unsqueeze(2)).squeeze(2)
            loss = -(functional.logsigmoid(positive) + functional.logsigmoid(-negative).sum(dim=1)).mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    learned = input_embeddings.weight.detach().cpu().numpy()
    return {node: learned[index] for node, index in node_to_index.items()}
