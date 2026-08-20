from __future__ import annotations

from typing import Any

from model.agents.base_agent import BaseAgent

from model.core.prompts import PromptBuilder

from model.utils.io import terminal_message

from model.agents.evolutor_agent import (
    apply_llm_output,
    build_existing_tables_context,
    build_table_context,
)

from baselines.oneshot.model.prompts import evolutor_prompt


class EvolutorAgent(BaseAgent):
    """
    Perform one-shot relational schema integration for one incoming table.

    The agent receives:
    - the complete incoming-table context
    - the complete existing RDB context

    It performs table matching, column placement, and schema-evolution
    reasoning in a single LLM call. It does not depend on MatcherAgent.

    ProposalBuilder converts the returned EvolutorResult into concrete
    schema, constraint, and mapping proposals.
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
        existing_schema: dict[str, Any],
        existing_values: dict[str, list[dict[str, Any]]],
        existing_constraints: dict[str, Any],
        incoming_profile: dict[str, Any] | None = None,
        existing_profiles: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        table_name, table_schema = self._extract_single_table(incoming_schema)

        existing_table_count = len(existing_schema.get("tables", {}))
        terminal_message("info", f"One-shot evolving incoming table '{table_name}' against all {existing_table_count} existing tables.", "\t")

        llm_input = build_llm_input(
            incoming_table_name=table_name,
            incoming_table_schema=table_schema,
            incoming_values=incoming_values,
            incoming_profile=incoming_profile,
            existing_schema=existing_schema,
            existing_profiles=existing_profiles,
            existing_values=existing_values,
            existing_constraints=existing_constraints,
        )

        prompt = self.prompt_builder(llm_input)
        llm_output = self._generate_json(prompt)
        evolution_result = apply_llm_output(llm_output)

        terminal_message("success", f"EvolutorAgent completed for table '{table_name}' with decision: {evolution_result['decision']['decision_type']}.", "\t")

        return evolution_result


def build_llm_input(
    incoming_table_name: str,
    incoming_table_schema: dict[str, Any],
    incoming_values: list[dict[str, Any]],
    incoming_profile: dict[str, Any] | None,
    existing_schema: dict[str, Any],
    existing_profiles: dict[str, Any] | None,
    existing_values: dict[str, list[dict[str, Any]]],
    existing_constraints: dict[str, Any],
) -> dict[str, Any]:
    """Build the complete one-shot context without matcher preselection."""

    return {
        "incoming_table": build_table_context(
            table_name=incoming_table_name,
            table_schema=incoming_table_schema,
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
                "constraints",
                existing_constraints,
            ),
        },
    }

