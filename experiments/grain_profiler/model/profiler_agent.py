from __future__ import annotations

from typing import Any

from model.agents.base_agent import BaseAgent
from model.core.prompts import PromptBuilder
from model.utils.io import terminal_message
from model.utils.structure import get_column_values

from experiments.grain_profiler.model.profile_compression import compact_profile
from experiments.grain_profiler.model.prompts import grain_profiler_prompt


class GrainProfilerAgent(BaseAgent):
    """Produce only row-grain evidence instead of a verbose semantic profile."""

    def __init__(
        self,
        llm_client: Any,
        prompt_builder: PromptBuilder = grain_profiler_prompt,
    ) -> None:
        super().__init__(llm_client=llm_client, prompt_builder=prompt_builder)

    def __call__(
        self,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
    ) -> dict[str, Any]:
        table_name, table_schema = self._extract_single_table(incoming_schema)
        columns = {
            column_name: {
                "schema": column_schema,
                "sample_values": get_column_values(
                    incoming_values,
                    column_name,
                ),
            }
            for column_name, column_schema in table_schema.get("columns", {}).items()
        }
        llm_input = {
            "table_name": table_name,
            "columns": columns,
        }

        terminal_message(
            "info",
            f"Grain profiling incoming table '{table_name}'.",
            "\t",
        )
        raw_result = self._generate_json(self.prompt_builder(llm_input))
        result = compact_profile(raw_result, table_name=table_name)
        _ensure_all_columns(result, table_schema)
        terminal_message(
            "success",
            f"GrainProfilerAgent completed for table '{table_name}'.",
            "\t",
        )
        return result


def _ensure_all_columns(
    result: dict[str, Any],
    table_schema: dict[str, Any],
) -> None:
    """Keep the output total even if the LLM omits a column."""

    expected_columns = table_schema.get("columns", {})
    result_columns = result.setdefault("columns", {})
    for column_name in expected_columns:
        result_columns.setdefault(
            column_name,
            {
                "semantic_type": "unknown",
                "business_concept": column_name,
                "grain_role": "unknown",
            },
        )
    for column_name in list(result_columns):
        if column_name not in expected_columns:
            del result_columns[column_name]
