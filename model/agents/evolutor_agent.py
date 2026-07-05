from __future__ import annotations

import json
from typing import Any

from model.agents.base_agent import BaseAgent
from model.core.prompts import PromptBuilder, evolutor_prompt
from model.core.schemas import (
    MatcherResult,
    EvolutorResult,
    EvolutionDecision,
    ColumnPlacement,
    ConstraintSignal,
)
from model.utils.io import terminal_message, save_json
from model.utils.structure import get_column_values


class EvolutorAgent(BaseAgent):
    """
    Infer schema evolution signals for one incoming table.

    Evolutor does not build the final proposal.
    It only decides:
    - table-level evolution direction
    - source column placement
    - constraint signals

    ProposalBuilder converts EvolutionResult into concrete schema,
    constraint, and mapping proposals.
    """

    def __init__(
        self,
        llm_client: Any | None = None,
        prompt_builder: PromptBuilder = evolutor_prompt,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder

    def __call__(
        self,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
        incoming_profile: dict[str, Any],
        matcher_result: MatcherResult,
        existing_schema: dict[str, Any],
        existing_profiles: dict[str, Any],
        existing_values: dict[str, list[dict[str, Any]]],
        existing_constraints: dict[str, Any],
    ) -> EvolutorResult:
        table_name, table_schema = self._extract_single_table(incoming_schema)

        selected_tables = select_context_tables(
            matcher_result=matcher_result,
            incoming_profile=incoming_profile,
            existing_schema=existing_schema,
            existing_constraints=existing_constraints,
        )

        terminal_message("info", f"Evolving incoming table '{table_name}' with context tables: {selected_tables}.","\t")

        llm_input = build_llm_input(
            incoming_table_name=table_name,
            incoming_table_schema=table_schema,
            incoming_values=incoming_values,
            incoming_profile=incoming_profile,
            matcher_result=matcher_result,
            selected_tables=selected_tables,
            existing_schema=existing_schema,
            existing_profiles=existing_profiles,
            existing_values=existing_values,
            existing_constraints=existing_constraints,
        )

        # save_json(llm_input, f"evolutor_input.json")

        prompt = self.prompt_builder(llm_input)
        llm_output = self._generate_json(prompt)

        evolution_result = apply_llm_output(llm_output)

        terminal_message(
            "success", f"EvolutorAgent completed for table '{table_name}' with decision: {evolution_result['decision']['decision_type']}.", "\t")

        return evolution_result

def build_llm_input(
    incoming_table_name: str,
    incoming_table_schema: dict[str, Any],
    incoming_values: list[dict[str, Any]],
    incoming_profile: dict[str, Any],
    matcher_result: MatcherResult,
    selected_tables: list[str],
    existing_schema: dict[str, Any],
    existing_profiles: dict[str, Any],
    existing_values: dict[str, list[dict[str, Any]]],
    existing_constraints: dict[str, Any],
) -> dict[str, Any]:
    return {
        "incoming_table": build_table_context(
            table_name=incoming_table_name,
            table_schema=incoming_table_schema,
            rows=incoming_values,
            profile=incoming_profile,
        ),
        "candidate_tables": build_candidate_tables_context(
            selected_tables=selected_tables,
            matcher_result=matcher_result,
            existing_schema=existing_schema,
            existing_profiles=existing_profiles,
            existing_values=existing_values,
            existing_constraints=existing_constraints,
        ),
    }


def build_table_context(
    table_name: str,
    table_schema: dict[str, Any],
    rows: list[dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    columns: dict[str, Any] = {}

    for column_name, column_schema in table_schema["columns"].items():
        columns[column_name] = {
            "schema": column_schema,
            "sample_values": get_column_values(
                rows=rows,
                column_name=column_name,
            ),
            "profile": profile["columns"][column_name],
        }

    return {
        "name": table_name,
        "profile": profile["table"],
        "columns": columns,
    }


def build_candidate_tables_context(
    selected_tables: list[str],
    matcher_result: MatcherResult,
    existing_schema: dict[str, Any],
    existing_profiles: dict[str, Any],
    existing_values: dict[str, list[dict[str, Any]]],
    existing_constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    profiles_by_table = get_profiles_by_table(existing_profiles)
    matcher_by_table = get_matcher_result_by_table(matcher_result)

    candidate_tables: list[dict[str, Any]] = []

    for table_name in selected_tables:
        table_context = build_table_context(
            table_name=table_name,
            table_schema=existing_schema["tables"][table_name],
            rows=existing_values.get(table_name, []),
            profile=profiles_by_table[table_name],
        )

        table_match = matcher_by_table.get(table_name)

        candidate_tables.append(
            {
                **table_context,
                "primary_key": get_primary_key(
                    table_name=table_name,
                    existing_constraints=existing_constraints,
                ),
                "matcher": (
                    summarize_table_match(table_match)
                    if table_match is not None
                    else empty_matcher_summary(table_name)
                ),
            }
        )

    return candidate_tables


def select_context_tables(
    matcher_result: MatcherResult,
    incoming_profile: dict[str, Any],
    existing_schema: dict[str, Any],
    existing_constraints: dict[str, Any],
    table_threshold: float = 0.40,
    column_threshold: float = 0.80,
    max_context_tables: int = 8,
) -> list[str]:
    table_scores: dict[str, float] = {}

    important_columns = collect_important_source_columns(
        matcher_result=matcher_result,
        incoming_profile=incoming_profile,
    )

    for table_match in matcher_result["table_matches"]:
        target_table = table_match["target_table"]

        if table_match["confidence"] >= table_threshold:
            table_scores[target_table] = max(
                table_scores.get(target_table, 0.0),
                100.0 + table_match["confidence"],
            )

        strong_column_confidence = get_max_strong_important_column_confidence(
            table_match=table_match,
            important_columns=important_columns,
            threshold=column_threshold,
        )

        if strong_column_confidence > 0:
            table_scores[target_table] = max(
                table_scores.get(target_table, 0.0),
                90.0 + strong_column_confidence,
            )

    for table_name in find_tables_by_source_id_columns(
        incoming_profile=incoming_profile,
        existing_schema=existing_schema,
    ):
        table_scores[table_name] = max(
            table_scores.get(table_name, 0.0),
            80.0,
        )

    if not table_scores:
        for table_match in matcher_result["table_matches"][:3]:
            table_scores[table_match["target_table"]] = (
                10.0 + table_match["confidence"]
            )

    for table_name in get_one_hop_constraint_neighbors(
        selected_tables=set(table_scores.keys()),
        existing_constraints=existing_constraints,
    ):
        table_scores[table_name] = max(
            table_scores.get(table_name, 0.0),
            50.0,
        )

    existing_table_order = {
        table_name: index
        for index, table_name in enumerate(existing_schema["tables"].keys())
    }

    selected_tables = sorted(
        table_scores.keys(),
        key=lambda table_name: (
            table_scores[table_name],
            -existing_table_order[table_name],
        ),
        reverse=True,
    )

    return selected_tables[:max_context_tables]


def collect_important_source_columns(
    matcher_result: MatcherResult,
    incoming_profile: dict[str, Any],
) -> set[str]:
    important_columns: set[str] = set()

    for table_match in matcher_result["table_matches"]:
        important_columns.update(table_match["unmatched_source_columns"])
        important_columns.update(table_match["ambiguous_source_columns"])

    for column_name, column_profile in incoming_profile["columns"].items():
        semantic_type = column_profile.get("semantic_type", "")
        business_concept = column_profile.get("business_concept", "")

        if column_name.endswith("_id"):
            important_columns.add(column_name)

        if semantic_type in {"identifier", "id", "foreign_key"}:
            important_columns.add(column_name)

        if "identifier" in business_concept.lower():
            important_columns.add(column_name)

    return important_columns


def get_max_strong_important_column_confidence(
    table_match: dict[str, Any],
    important_columns: set[str],
    threshold: float,
) -> float:
    max_confidence = 0.0

    for source_column in important_columns:
        for candidate in table_match["column_matches"].get(source_column, []):
            confidence = candidate["confidence"]

            if confidence >= threshold:
                max_confidence = max(max_confidence, confidence)

    return max_confidence


def find_tables_by_source_id_columns(
    incoming_profile: dict[str, Any],
    existing_schema: dict[str, Any],
) -> set[str]:
    selected_tables: set[str] = set()

    for source_column in incoming_profile["columns"].keys():
        if not source_column.endswith("_id"):
            continue

        for table_name, table_schema in existing_schema["tables"].items():
            if source_column in table_schema["columns"]:
                selected_tables.add(table_name)

    return selected_tables


def get_one_hop_constraint_neighbors(
    selected_tables: set[str],
    existing_constraints: dict[str, Any],
) -> set[str]:
    neighbors: set[str] = set()
    foreign_keys = existing_constraints["constraints"]["foreign_keys"]

    for source_table, table_foreign_keys in foreign_keys.items():
        for foreign_key in table_foreign_keys:
            referenced_table = foreign_key["referenced_table"]

            if source_table in selected_tables:
                neighbors.add(referenced_table)

            if referenced_table in selected_tables:
                neighbors.add(source_table)

    return neighbors


def get_primary_key(
    table_name: str,
    existing_constraints: dict[str, Any],
) -> list[str]:
    return existing_constraints["constraints"]["primary_keys"].get(table_name, [])


def get_matcher_result_by_table(
    matcher_result: MatcherResult,
) -> dict[str, dict[str, Any]]:
    return {
        table_match["target_table"]: table_match
        for table_match in matcher_result["table_matches"]
    }


def summarize_table_match(
    table_match: dict[str, Any],
    strong_threshold: float = 0.80,
) -> dict[str, Any]:
    strong_column_matches: list[dict[str, Any]] = []
    weak_column_matches: list[dict[str, Any]] = []

    for source_column, candidates in table_match["column_matches"].items():
        for candidate in candidates:
            item = {
                "source_column": source_column,
                "target_column": candidate["target_column"],
                "confidence": candidate["confidence"],
                "reason": candidate["reason"],
            }

            if candidate["confidence"] >= strong_threshold:
                strong_column_matches.append(item)
            else:
                weak_column_matches.append(item)

    return {
        "target_table": table_match["target_table"],
        "table_confidence": table_match["confidence"],
        "match_status": table_match["match_status"],
        "strong_column_matches": strong_column_matches,
        "weak_column_matches": weak_column_matches,
        "unmatched_source_columns": table_match["unmatched_source_columns"],
        "ambiguous_source_columns": table_match["ambiguous_source_columns"],
        "reason": table_match["reason"],
    }


def empty_matcher_summary(table_name: str) -> dict[str, Any]:
    return {
        "target_table": table_name,
        "table_confidence": 0.0,
        "match_status": "not_matched_by_matcher",
        "strong_column_matches": [],
        "weak_column_matches": [],
        "unmatched_source_columns": [],
        "ambiguous_source_columns": [],
        "reason": "Included as a one-hop constraint neighbor.",
    }


def apply_llm_output(
    llm_output: dict[str, Any],
) -> EvolutorResult:
    return {
        "decision": normalize_decision(llm_output["decision"]),
        "column_placements": normalize_column_placements(
            llm_output["column_placements"]
        ),
        "reason": llm_output["reason"],
    }


def normalize_decision(
    raw_decision: dict[str, Any],
) -> EvolutionDecision:
    return {
        "decision_type": raw_decision["decision_type"],
        "target_table": raw_decision["target_table"],
        "related_tables": raw_decision["related_tables"],
        "reason": raw_decision["reason"],
    }


def normalize_column_placements(
    raw_column_placements: dict[str, Any],
) -> dict[str, ColumnPlacement]:
    column_placements: dict[str, ColumnPlacement] = {}

    for source_column, raw_placement in raw_column_placements.items():
        column_placements[source_column] = {
            "source_column": raw_placement["source_column"],
            "target_table": raw_placement["target_table"],
            "target_column": raw_placement["target_column"],
            "reason": raw_placement["reason"],
        }

    return column_placements


def get_profiles_by_table(existing_profiles: dict[str, Any]) -> dict[str, Any]:
    tables = existing_profiles.get("tables")

    if isinstance(tables, dict):
        return tables

    return existing_profiles