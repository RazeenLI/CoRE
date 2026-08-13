from __future__ import annotations

import json
from typing import Any

from model.agents.base_agent import BaseAgent
from model.core.prompts import PromptBuilder, matcher_prompt
from model.core.schemas import MatcherResult, TableMatch
from model.utils.io import terminal_message
from model.utils.structure import get_column_values


class MatcherAgent(BaseAgent):
    """
    Match one incoming table against every existing table.

    Input:
        incoming_schema:
            should contain exactly one table, with its columns and types.
        incoming_values
            Sample rows for the incoming table.
        incoming_profile
            Profile information for the incoming table.
        existing_schema
            Schema information for all existing tables.
        existing_profiles
            Profile information for all existing tables.
        existing_values  
            Sample rows for all existing tables.

    Output:
        MatcherResult

    Fully LLM-based:
        - no non-LLM prefilter
        - no top-k filtering
        - no batch matching
        - one LLM call per existing table
    """

    def __init__(
        self,
        llm_client: Any | None = None,
        prompt_builder: PromptBuilder = matcher_prompt,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder

    def __call__(
        self,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
        incoming_profile: dict[str, Any],
        existing_schema: dict[str, Any],
        existing_profiles: dict[str, Any],
        existing_values: dict[str, list[dict[str, Any]]],
        validation_feedback: dict[str, Any] | None = None,
    ) -> MatcherResult:
        table_name, table_schema = self._extract_single_table(incoming_schema)

        columns_schema: dict[str, Any] = table_schema.get("columns", {})

        existing_tables = existing_schema.get("tables", {})
        existing_profiles_by_table = get_profiles_by_table(existing_profiles)

        terminal_message("info", f"Matching incoming table '{table_name}' against {len(existing_tables)} existing tables: {list(existing_tables.keys())}.", "\t",)
        
        table_matches: list[TableMatch] = []

        for target_table_name, target_table_schema in existing_tables.items():
            terminal_message("info", f"Matching '{table_name}' [{', '.join(columns_schema.keys())}] with existing table '{target_table_name}' [{', '.join(target_table_schema.get('columns', {}).keys())}].", "\t\t",)

            table_match: TableMatch = {
                "target_table": target_table_name,
                "confidence": 0.0,
                "match_status": "poor_match",
                "column_matches": {},
                "unmatched_source_columns": [],
                "ambiguous_source_columns": [],
                "reason": "",
            }

            llm_input = build_llm_input(
                incoming_table_name=table_name,
                incoming_table_schema=table_schema,
                incoming_values=incoming_values,
                incoming_profile=incoming_profile,
                target_table_name=target_table_name,
                target_table_schema=target_table_schema,
                target_values=existing_values.get(target_table_name, []),
                target_profile=existing_profiles_by_table.get(target_table_name, {}),
                validation_feedback=validation_feedback,
            )
            # print(json.dumps(llm_input, indent=2, ensure_ascii=False))

            prompt = self.prompt_builder(llm_input)
            
            llm_output = self._generate_json(prompt)

            apply_llm_output(
                table_match=table_match,
                llm_output=llm_output,
                source_columns=list(incoming_profile.get("columns", {}).keys()),
                target_columns=list(
                    target_table_schema.get("columns", {}).keys()
                ),
            )

            table_matches.append(table_match)

        matching_result = build_matching_result(table_matches)

        terminal_message("success", f"MatcherAgent completed for table '{table_name}'.", "\t")

        return matching_result
    

def build_llm_input(
    incoming_table_name: str,
    incoming_table_schema: dict[str, Any],
    incoming_values: list[dict[str, Any]],
    incoming_profile: dict[str, Any],
    target_table_name: str,
    target_table_schema: dict[str, Any],
    target_values: list[dict[str, Any]],
    target_profile: dict[str, Any],
    validation_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    llm_input: dict[str, Any] =  {
        "incoming_table": build_table_context(
            table_name=incoming_table_name,
            table_schema=incoming_table_schema,
            rows=incoming_values,
            profile=incoming_profile,
        ),
        "target_table": build_table_context(
            table_name=target_table_name,
            table_schema=target_table_schema,
            rows=target_values,
            profile=target_profile,
        ),
    }

    if validation_feedback is not None:
        llm_input["validation_feedback"] = validation_feedback

    return llm_input


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


# def init_table_match(target_table_name: str) -> TableMatch:
#     return {
#         "target_table": target_table_name,
#         "confidence": 0.0,
#         "match_status": "poor_match",
#         "column_matches": {},
#         "unmatched_source_columns": [],
#         "ambiguous_source_columns": [],
#         "reason": "",
#     }


def apply_llm_output(
    table_match: TableMatch,
    llm_output: dict[str, Any],
    source_columns: list[str],
    target_columns: list[str],
) -> None:
    """
    Mutates table_match in place.

    LLM output should have the same structure as TableMatch except:
        - no unmatched_source_columns
        - no ambiguous_source_columns

    This function:
        - fills table confidence / status / reason
        - normalizes column_matches
        - computes unmatched_source_columns
        - computes ambiguous_source_columns
    """
    table_match["confidence"] = clamp01(llm_output.get("confidence", 0.0))
    table_match["match_status"] = normalize_match_status(
        llm_output.get("match_status", "poor_match")
    )
    table_match["reason"] = llm_output.get("reason", "")

    column_matches = normalize_column_matches(
        raw_column_matches=llm_output.get("column_matches", {}),
        source_columns=source_columns,
        target_columns=target_columns,
    )

    table_match["column_matches"] = column_matches
    table_match["unmatched_source_columns"] = infer_unmatched_source_columns(
        column_matches
    )
    table_match["ambiguous_source_columns"] = infer_ambiguous_source_columns(
        column_matches
    )


def normalize_column_matches(
    raw_column_matches: Any,
    source_columns: list[str],
    target_columns: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(raw_column_matches, dict):
        raw_column_matches = {}

    target_column_set = set(target_columns)
    column_matches: dict[str, list[dict[str, Any]]] = {}

    for source_column in source_columns:
        raw_candidates = raw_column_matches.get(source_column, [])

        if not isinstance(raw_candidates, list):
            raw_candidates = []

        candidates: list[dict[str, Any]] = []

        for raw_candidate in raw_candidates:
            if not isinstance(raw_candidate, dict):
                continue

            target_column = raw_candidate.get("target_column")

            if target_column not in target_column_set:
                continue

            candidates.append(
                {
                    "target_column": target_column,
                    "confidence": clamp01(raw_candidate.get("confidence", 0.0)),
                    "reason": raw_candidate.get("reason", ""),
                }
            )

        candidates.sort(
            key=lambda item: item.get("confidence", 0.0),
            reverse=True,
        )

        column_matches[source_column] = candidates

    return column_matches


def infer_unmatched_source_columns(
    column_matches: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """
    No threshold here.

    A source column is unmatched only if LLM returns no candidate target column.
    """
    return [
        source_column
        for source_column, candidates in column_matches.items()
        if not candidates
    ]


def infer_ambiguous_source_columns(
    column_matches: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """
    No threshold here.

    A source column is ambiguous if LLM returns more than one candidate.
    """
    return [
        source_column
        for source_column, candidates in column_matches.items()
        if len(candidates) > 1
    ]


def build_matching_result(
    table_matches: list[TableMatch],
) -> MatcherResult:
    table_matches = sorted(
        table_matches,
        key=lambda item: item.get("confidence", 0.0),
        reverse=True,
    )

    return {
        "table_matches": table_matches,
    }


def get_profiles_by_table(existing_profiles: dict[str, Any]) -> dict[str, Any]:
    """
    Supports both:

        {"tables": {"Customer": {...}}}

    and:

        {"Customer": {...}}
    """
    tables = existing_profiles.get("tables")

    if isinstance(tables, dict):
        return tables

    return existing_profiles


def normalize_match_status(value: Any) -> str:
    allowed = {
        "full_match",
        "partial_match",
        "ambiguous_match",
        "poor_match",
    }

    value = str(value or "poor_match")

    if value in allowed:
        return value

    return "poor_match"


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