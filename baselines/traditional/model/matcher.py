from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from model.utils.io import terminal_message


TraditionalMethod = Literal["jl", "coma"]


@dataclass(frozen=True)
class MatcherConfig:
    assignment_threshold: float = 0.70
    levenshtein_threshold: float = 0.80
    coma_use_schema: bool = True
    coma_use_instances: bool = True
    coma_delta: float = 0.15


class TraditionalMatcher:
    """Adapt Valentine match results to the project's MatcherResult shape."""

    def __init__(
        self,
        method: TraditionalMethod,
        config: MatcherConfig,
        *,
        valentine_api: dict[str, Any] | None = None,
    ) -> None:
        if method not in {"jl", "coma"}:
            raise ValueError(f"Unsupported traditional matcher: {method}")
        self.method = method
        self.config = config
        self.api = valentine_api or load_valentine_api()

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
        source_df = build_dataframe(
            rows=incoming_values,
            columns=source_columns,
            pandas_module=self.api["pandas"],
        )

        table_matches = []
        for target_table, target_schema in existing_schema.get("tables", {}).items():
            target_columns = list(target_schema.get("columns", {}))
            target_df = build_dataframe(
                rows=existing_values.get(target_table, []),
                columns=target_columns,
                pandas_module=self.api["pandas"],
            )
            matcher = self._build_matcher()
            raw_matches = self.api["valentine_match"](
                [source_df, target_df],
                matcher,
                df_names=["incoming", target_table],
            )
            selected = raw_matches.one_to_one_hungarian(
                threshold=self.config.assignment_threshold
            )
            column_matches = normalize_valentine_matches(
                matches=selected,
                source_label="incoming",
                target_label=target_table,
                source_columns=source_columns,
                incoming_table=incoming_table,
                target_schema=target_schema,
            )
            table_matches.append(
                build_table_match(
                    target_table=target_table,
                    source_columns=source_columns,
                    column_matches=column_matches,
                )
            )

        table_matches.sort(
            key=lambda item: (-item["confidence"], item["target_table"])
        )
        terminal_message(
            "success",
            f"{self.method.upper()} matched '{incoming_name}' against "
            f"{len(table_matches)} existing tables.",
            "\t",
        )
        return {
            "matcher": self.method,
            "table_matches": table_matches,
        }

    def _build_matcher(self) -> Any:
        if self.method == "jl":
            return self.api["JaccardDistanceMatcher"](
                distance_fun=self.api["StringDistanceFunction"].Levenshtein,
                threshold_dist=self.config.levenshtein_threshold,
            )
        return self.api["Coma"](
            max_n=0,
            use_instances=self.config.coma_use_instances,
            use_schema=self.config.coma_use_schema,
            delta=self.config.coma_delta,
            threshold=0.0,
        )


def load_valentine_api() -> dict[str, Any]:
    try:
        import pandas as pd
        from valentine import valentine_match
        from valentine.algorithms import Coma, JaccardDistanceMatcher
        from valentine.algorithms.jaccard_distance import StringDistanceFunction
    except ImportError as exc:
        raise ImportError(
            "The JL and COMA baselines require Valentine. Install "
            "baselines/traditional/requirements.txt in the active environment."
        ) from exc
    return {
        "pandas": pd,
        "valentine_match": valentine_match,
        "Coma": Coma,
        "JaccardDistanceMatcher": JaccardDistanceMatcher,
        "StringDistanceFunction": StringDistanceFunction,
    }


def build_dataframe(
    *,
    rows: list[dict[str, Any]],
    columns: list[str],
    pandas_module: Any,
) -> Any:
    """Preserve schema columns even when no sample rows are available."""

    return pandas_module.DataFrame(rows, columns=columns)


def normalize_valentine_matches(
    *,
    matches: Any,
    source_label: str,
    target_label: str,
    source_columns: list[str],
    incoming_table: dict[str, Any],
    target_schema: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    normalized = {column: [] for column in source_columns}
    for pair, raw_score in matches.items():
        if pair.source_table == source_label and pair.target_table == target_label:
            source_column = pair.source_column
            target_column = pair.target_column
        elif pair.target_table == source_label and pair.source_table == target_label:
            source_column = pair.target_column
            target_column = pair.source_column
        else:
            continue
        if source_column not in normalized:
            continue
        if target_column not in target_schema.get("columns", {}):
            continue
        if not types_compatible(
            incoming_table["columns"][source_column].get("type"),
            target_schema["columns"][target_column].get("type"),
        ):
            continue
        normalized[source_column].append(
            {
                "target_column": target_column,
                "confidence": clamp01(raw_score),
                "reason": "Valentine match accepted by type compatibility rules.",
            }
        )
    for candidates in normalized.values():
        candidates.sort(key=lambda item: -item["confidence"])
    return normalized


def build_table_match(
    *,
    target_table: str,
    source_columns: list[str],
    column_matches: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    best_scores = [
        column_matches[column][0]["confidence"] if column_matches[column] else 0.0
        for column in source_columns
    ]
    confidence = sum(best_scores) / len(source_columns) if source_columns else 0.0
    unmatched = [column for column in source_columns if not column_matches[column]]
    return {
        "target_table": target_table,
        "confidence": confidence,
        "match_status": "full_match" if not unmatched else (
            "partial_match" if len(unmatched) < len(source_columns) else "poor_match"
        ),
        "column_matches": column_matches,
        "unmatched_source_columns": unmatched,
        "ambiguous_source_columns": [],
    }


def types_compatible(source_type: Any, target_type: Any) -> bool:
    source = normalize_type(source_type)
    target = normalize_type(target_type)
    if source == "unknown" or target == "unknown":
        return True
    if source == target:
        return True
    compatible_groups = [
        {"integer", "decimal", "float", "number"},
        {"date", "timestamp", "datetime"},
        {"string", "text", "char"},
    ]
    return any(source in group and target in group for group in compatible_groups)


def normalize_type(value: Any) -> str:
    normalized = str(value or "unknown").lower()
    aliases = {
        "int": "integer",
        "bigint": "integer",
        "smallint": "integer",
        "numeric": "decimal",
        "double": "float",
        "real": "float",
        "varchar": "string",
        "character varying": "string",
        "bool": "boolean",
    }
    return aliases.get(normalized, normalized)


def extract_single_table(schema: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    tables = schema.get("tables", {})
    if len(tables) != 1:
        raise ValueError(f"Exactly one incoming table is required, got {len(tables)}.")
    name = next(iter(tables))
    return name, tables[name]


def clamp01(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))
