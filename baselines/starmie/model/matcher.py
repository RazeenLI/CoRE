from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from baselines.discovery.model.common import (
    cosine_similarity,
    extract_single_table,
    matches_from_scores,
)
from model.utils.io import terminal_message


class StarmieMatcher:
    """Load a frozen model produced by the official Starmie implementation."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.upstream_path = resolve_required_path(
            config.get("upstream_path"),
            environment_name="STARMIE_ROOT",
            description="official Starmie checkout",
        )
        self.checkpoint_path = resolve_required_path(
            config.get("checkpoint_path"),
            environment_name="STARMIE_CHECKPOINT",
            description="VizNet-trained Starmie checkpoint",
        )
        self.assignment_threshold = float(config.get("assignment_threshold", 0.70))
        self.batch_size = int(config.get("batch_size", 128))
        self.device = str(config.get("device", "cuda"))
        self._backend: tuple[Any, Any] | None = None

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
        table_specs = [("incoming", source_columns, incoming_values)]
        for table_name, table_schema in existing_schema.get("tables", {}).items():
            table_specs.append((
                table_name,
                list(table_schema.get("columns", {})),
                existing_values.get(table_name, []),
            ))
        vectors = self._encode_tables(table_specs)
        source_vectors = vectors["incoming"]

        table_matches = []
        for target_table, target_schema in existing_schema.get("tables", {}).items():
            target_columns = list(target_schema.get("columns", {}))
            target_vectors = vectors[target_table]
            scores = []
            for source_index in range(len(source_columns)):
                row = []
                for target_index in range(len(target_columns)):
                    score = cosine_similarity(
                        source_vectors[source_index], target_vectors[target_index]
                    )
                    row.append(score if score >= self.assignment_threshold else 0.0)
                scores.append(row)
            table_matches.append(matches_from_scores(
                target_table=target_table,
                source_columns=source_columns,
                target_columns=target_columns,
                incoming_table=incoming_table,
                target_schema=target_schema,
                scores=scores,
                assignment_threshold=self.assignment_threshold,
                reason="Starmie contextual column-embedding similarity.",
            ))
        table_matches.sort(key=lambda item: (-item["confidence"], item["target_table"]))
        terminal_message(
            "success",
            f"Starmie encoded '{incoming_name}' with the frozen external checkpoint "
            f"and matched it against {len(table_matches)} existing tables.",
            "\t",
        )
        return {
            "matcher": "starmie",
            "checkpoint": str(self.checkpoint_path),
            "pretraining_scope": "external_viznet",
            "table_matches": table_matches,
        }

    def _load_backend(self) -> tuple[Any, Any]:
        if self._backend is not None:
            return self._backend
        if str(self.upstream_path) not in sys.path:
            sys.path.insert(0, str(self.upstream_path))
        try:
            import torch
            from sdd.dataset import PretrainTableDataset
            from sdd.model import BarlowTwinsSimCLR
        except ImportError as exc:
            raise ImportError(
                "Starmie dependencies or official modules are unavailable. Follow "
                "baselines/starmie/README.md and keep the official checkout external."
            ) from exc

        requested_device = torch.device(self.device)
        if requested_device.type == "cuda" and not torch.cuda.is_available():
            requested_device = torch.device("cpu")
        checkpoint = torch.load(
            self.checkpoint_path,
            map_location=requested_device,
            weights_only=False,
        )
        hp = checkpoint["hp"]
        model = BarlowTwinsSimCLR(hp, device=str(requested_device), lm=hp.lm)
        model.load_state_dict(checkpoint["model"])
        model = model.to(requested_device)
        model.eval()
        self._backend = (model, PretrainTableDataset)
        return self._backend

    def _encode_tables(
        self, table_specs: list[tuple[str, list[str], list[dict[str, Any]]]]
    ) -> dict[str, Any]:
        import pandas as pd

        model, dataset_class = self._load_backend()
        frames = [pd.DataFrame(rows, columns=columns) for _, columns, rows in table_specs]
        with tempfile.TemporaryDirectory(prefix="airdb_starmie_") as empty_table_dir:
            dataset = dataset_class.from_hp(empty_table_dir, model.hp)
            encoded = encode_with_official_model(
                frames, model=model, dataset=dataset, batch_size=self.batch_size
            )
        result = {}
        for (table_name, columns, _), column_vectors in zip(table_specs, encoded):
            if len(column_vectors) != len(columns):
                raise RuntimeError(
                    f"Starmie returned {len(column_vectors)} vectors for "
                    f"{table_name} with {len(columns)} columns."
                )
            result[table_name] = column_vectors
        return result


def resolve_required_path(
    configured_value: Any,
    *,
    environment_name: str,
    description: str,
) -> Path:
    raw_value = os.environ.get(environment_name) or configured_value
    if not raw_value:
        raise ValueError(
            f"Missing {description}. Set {environment_name} or its agent-config field."
        )
    path = Path(os.path.expandvars(os.path.expanduser(str(raw_value)))).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Configured {description} does not exist: {path}")
    return path


def encode_with_official_model(
    frames: list[Any], *, model: Any, dataset: Any, batch_size: int
) -> list[list[Any]]:
    """Batch official Starmie tokenization and contextual model inference."""

    import torch

    results: list[list[Any]] = []
    for offset in range(0, len(frames), batch_size):
        current_frames = frames[offset:offset + batch_size]
        batch = []
        for frame in current_frames:
            tokens, _ = dataset._tokenize(frame)
            batch.append((tokens, tokens, []))
        token_ids, _, _ = dataset.pad(batch)
        with torch.no_grad():
            column_vectors = model.inference(token_ids)
        pointer = 0
        for row in token_ids:
            current = []
            for token_id in row:
                if int(token_id) == dataset.tokenizer.cls_token_id:
                    current.append(column_vectors[pointer].detach().cpu().numpy())
                    pointer += 1
            results.append(current)
    return results
