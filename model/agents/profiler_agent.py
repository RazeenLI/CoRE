from __future__ import annotations

import json
import re
from typing import Any

from model.core.schemas import ColumnProfile, SourceProfile, TableProfile
from model.core.prompts import PromptBuilder, profiler_prompt


class ProfilerAgent:
    """
    Build a SourceProfile for one incoming table.

    Input:
        incoming_schema:
            schema.json content for one incoming table.

        incoming_values:
            sampled rows for that incoming table.

    Output:
        SourceProfile

    This agent does not:
        - read files
        - store task state
        - update existing RDB
        - match against existing RDB
        - make schema evolution decisions
    """

    def __init__(
        self,
        llm_client: Any | None = None, # none for ablation
        prompt_builder: PromptBuilder = profiler_prompt,
        # use_llm: bool = True,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        # self.use_llm = use_llm

    def __call__(
        self,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
    ) -> SourceProfile:
        table_name, table_schema = self._extract_single_table(incoming_schema) # not necessary

        columns_schema: dict[str, Any] = table_schema.get("columns", {})
        column_order: list[str] = table_schema.get(
            "column_order",
            list(columns_schema.keys()),
        )

        table_profile: TableProfile = {
            "name": table_name,
            "column_count": len(column_order),
            "summary": "",
            "entity": "unknown",
            "role": "unknown",
            "aliases": [],
        }

        column_profiles: dict[str, ColumnProfile] = {}

        for column_name in column_order:
            column_schema = columns_schema.get(column_name, {})
            sample_values = get_column_values(
                rows=incoming_values,
                column_name=column_name,
            )

            column_profile: ColumnProfile = {
                "name": column_name,
                "dtype": column_schema.get("type", "unknown"),
                "value_patterns": infer_value_patterns(sample_values),
                "meaning": "",
                "semantic_type": "unknown",
                "business_concept": "unknown",
                "aliases": [],
            }

            column_profiles[column_name] = column_profile

        source_profile: SourceProfile = {
            "table": table_profile,
            "columns": column_profiles,
        }

        # if self.use_llm and self.llm_client is not None:
        if self.llm_client is not None:
            # ready for prompt
            llm_input = build_llm_input(
                table_name=table_name,
                table_schema=table_schema,
                incoming_values=incoming_values,
                source_profile=source_profile,
            )

            prompt = self.prompt_builder(llm_input)
            llm_output = self._generate_json(prompt)

            apply_llm_output(
                source_profile=source_profile,
                llm_output=llm_output,
            )

        return source_profile

    def _extract_single_table(
        self,
        incoming_schema: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        tables = incoming_schema.get("tables", {})

        if not tables:
            raise ValueError("incoming_schema must contain at least one table.")

        if len(tables) > 1:
            raise ValueError(
                "ProfilerAgent currently expects one incoming table per task."
            )

        table_name = next(iter(tables))
        table_schema = tables[table_name]

        return table_name, table_schema

    def _generate_json(self, prompt: str) -> dict[str, Any]:
        """
        Expected llm_client interface:

            llm_client.generate_json(prompt: str) -> dict[str, Any]

        If your client returns a JSON string instead of a dict, this method
        also accepts that and parses it.
        """
        result = self.llm_client.generate_json(prompt)

        if isinstance(result, dict):
            return result

        if isinstance(result, str):
            return json.loads(result)

        raise TypeError("llm_client.generate_json(prompt) must return dict or JSON str.")
    
def get_column_values(
    rows: list[dict[str, Any]],
    column_name: str,
) -> list[Any]:
    return [row.get(column_name) for row in rows]


def build_llm_input(
    table_name: str,
    table_schema: dict[str, Any],
    incoming_values: list[dict[str, Any]],
    source_profile: SourceProfile,
) -> dict[str, Any]:
    columns_schema = table_schema.get("columns", {})

    columns_input: dict[str, Any] = {}

    for column_name, column_profile in source_profile["columns"].items():
        columns_input[column_name] = {
            "schema": columns_schema.get(column_name, {}),
            "dtype": column_profile.get("dtype", "unknown"),
            "value_patterns": column_profile.get("value_patterns", []),
            "sample_values": get_column_values(
                rows=incoming_values,
                column_name=column_name,
            ),
        }

    return {
        "table_name": table_name,
        "columns": columns_input,
    }


def apply_llm_output(
    source_profile: SourceProfile,
    llm_output: dict[str, Any],
) -> None:
    """
    Mutates source_profile in place.

    The base SourceProfile already contains:
        - table.name
        - table.column_count
        - columns.<col>.name
        - columns.<col>.inferred_dtype
        - columns.<col>.value_patterns

    This function only fills LLM-generated fields.
    """
    table_output = llm_output.get("table", {})

    source_profile["table"]["summary"] = table_output.get("summary", "")
    source_profile["table"]["entity"] = table_output.get("entity", "unknown")
    source_profile["table"]["role"] = table_output.get("role", "unknown")
    source_profile["table"]["aliases"] = table_output.get("aliases", [])

    column_outputs = llm_output.get("columns", {})

    for column_name, column_profile in source_profile["columns"].items():
        column_output = column_outputs.get(column_name, {})

        column_profile["meaning"] = column_output.get("meaning", "")
        column_profile["semantic_type"] = column_output.get(
            "semantic_type",
            "unknown",
        )
        column_profile["business_concept"] = column_output.get(
            "business_concept",
            "unknown",
        )
        column_profile["aliases"] = column_output.get("aliases", [])



def infer_value_patterns(sample_values: list[Any]) -> list[str]:
    non_null_values = remove_null_like_values(sample_values)

    if not non_null_values:
        return []

    patterns: list[str] = []

    if all(is_email_like(value) for value in non_null_values):
        patterns.append("email_like")

    if all(is_timestamp_like(value) for value in non_null_values):
        patterns.append("timestamp_like")
    elif all(is_date_like(value) for value in non_null_values):
        patterns.append("date_like")

    if all(is_bool_like(value) for value in non_null_values):
        patterns.append("boolean_like")

    if all(is_int_like(value) for value in non_null_values):
        patterns.append("integer_like")
    elif all(is_float_like(value) for value in non_null_values):
        patterns.append("number_like")

    if all(is_short_code_like(value) for value in non_null_values):
        patterns.append("short_code_like")

    return patterns


def remove_null_like_values(values: list[Any]) -> list[Any]:
    return [
        value
        for value in values
        if value is not None and value != ""
    ]


def is_int_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False

    if isinstance(value, int):
        return True

    if isinstance(value, str):
        return re.fullmatch(r"[+-]?\d+", value.strip()) is not None

    return False


def is_float_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False

    if isinstance(value, (int, float)):
        return True

    if isinstance(value, str):
        return re.fullmatch(
            r"[+-]?(\d+(\.\d*)?|\.\d+)",
            value.strip(),
        ) is not None

    return False


def is_bool_like(value: Any) -> bool:
    if isinstance(value, bool):
        return True

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "false",
            "yes",
            "no",
            "0",
            "1",
        }

    return False


def is_email_like(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    return re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        value.strip(),
    ) is not None


def is_date_like(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    return re.fullmatch(
        r"\d{4}-\d{2}-\d{2}",
        value.strip(),
    ) is not None


def is_timestamp_like(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    return re.fullmatch(
        r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?",
        value.strip(),
    ) is not None


def is_short_code_like(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    value = value.strip()

    return (
        1 <= len(value) <= 10
        and re.fullmatch(r"[A-Za-z0-9_-]+", value) is not None
    )