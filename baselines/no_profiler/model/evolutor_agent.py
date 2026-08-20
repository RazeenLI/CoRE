from __future__ import annotations
from typing import Any
from model.agents.evolutor_agent import (
    apply_llm_output,
    build_existing_tables_context,
    build_table_context,
)
from model.agents.base_agent import BaseAgent
from model.core.prompts import PromptBuilder
from model.utils.io import terminal_message
from baselines.no_profiler.model.prompts import evolutor_prompt

class EvolutorAgent(BaseAgent):
    """Make the final relationship and evolution decision without a matcher."""
    def __init__(
        self,
        llm_client: Any,
        prompt_builder: PromptBuilder = evolutor_prompt,
    ) -> None:
        super().__init__(llm_client=llm_client, prompt_builder=prompt_builder)
    def __call__(
        self,
        *,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
        existing_schema: dict[str, Any],
        existing_values: dict[str, list[dict[str, Any]]],
        existing_profiles: dict[str, Any] | None,
        existing_constraints: dict[str, Any],
        selection_result: dict[str, Any],
        validation_feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        table_name, table_schema = self._extract_single_table(incoming_schema)
        selected_tables = _selected_table_names(
            selection_result=selection_result,
            existing_schema=existing_schema,
        )
        selected_schema = {
            **existing_schema,
            "tables": {
                name: existing_schema["tables"][name]
                for name in selected_tables
            },
        }
        llm_input: dict[str, Any] = {
            "incoming_table": build_table_context(
                table_name=table_name,
                table_schema=table_schema,
                rows=incoming_values,
                profile=None,
            ),
            "existing_rdb": {
                "database": existing_schema.get("database"),
                "dialect": existing_schema.get("dialect"),
                "version": existing_schema.get("version"),
                "tables": build_existing_tables_context(
                    existing_schema=selected_schema,
                    existing_profiles=None,
                    existing_values=existing_values,
                ),
                "constraints": existing_constraints.get(
                    "constraints",
                    existing_constraints,
                ),
            },
        }
        llm_input["candidate_selection"] = selection_result
        if validation_feedback is not None:
            llm_input["validation_feedback"] = validation_feedback
        terminal_message(
            "info",
            f"Selector-no-profiler evolving incoming table '{table_name}' against candidates: {selected_tables}.",
            "\t",
        )
        result = apply_llm_output(
            self._generate_json(self.prompt_builder(llm_input))
        )
        terminal_message(
            "success",
            f"Selector-no-profiler Evolutor completed with decision: {result['decision']['decision_type']}.",
            "\t",
        )
        return result
def _selected_table_names(
    *,
    selection_result: dict[str, Any],
    existing_schema: dict[str, Any],
) -> list[str]:
    selected = selection_result.get("selected_tables", [])
    return [name for name in selected if name in existing_schema.get("tables", {})]
