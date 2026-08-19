from __future__ import annotations

from typing import Any

from baselines.oneshot.model.agent import (
    apply_llm_output,
    build_existing_tables_context,
    build_table_context,
)
from model.agents.base_agent import BaseAgent
from model.core.prompts import PromptBuilder
from model.utils.io import terminal_message

from experiments.no_matcher.model.prompts import evolutor_prompt


class EvolutorAgent(BaseAgent):
    """One-shot-style Evolutor with incoming profile and validator feedback."""

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
        incoming_profile: dict[str, Any] | None,
        existing_schema: dict[str, Any],
        existing_values: dict[str, list[dict[str, Any]]],
        existing_profiles: dict[str, Any] | None,
        existing_constraints: dict[str, Any],
        validation_feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        table_name, table_schema = self._extract_single_table(incoming_schema)
        llm_input: dict[str, Any] = {
            "incoming_table": build_table_context(
                table_name=table_name,
                table_schema=table_schema,
                rows=incoming_values,
                profile=incoming_profile,
            ),
            "existing_rdb": {
                "database": existing_schema.get("database"),
                "dialect": existing_schema.get("dialect"),
                "version": existing_schema.get("version"),
                "tables": build_existing_tables_context(
                    existing_schema=existing_schema,
                    existing_profiles=existing_profiles,
                    existing_values=existing_values,
                ),
                "constraints": existing_constraints.get(
                    "constraints", existing_constraints
                ),
            },
        }
        if validation_feedback is not None:
            llm_input["validation_feedback"] = validation_feedback

        terminal_message(
            "info",
            f"No-Matcher evolving incoming table '{table_name}' against all existing tables.",
            "\t",
        )
        result = apply_llm_output(
            self._generate_json(self.prompt_builder(llm_input))
        )
        terminal_message(
            "success",
            f"No-Matcher Evolutor completed with decision: {result['decision']['decision_type']}.",
            "\t",
        )
        return result
