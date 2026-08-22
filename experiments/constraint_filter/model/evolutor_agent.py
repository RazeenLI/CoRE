from __future__ import annotations

from typing import Any

from model.agents.evolutor_agent import EvolutorAgent
from model.utils.io import terminal_message

from experiments.constraint_filter.model.constraint_filter import (
    filter_constraints_to_tables,
)


class ConstraintFilteredEvolutorAgent(EvolutorAgent):
    """Standard Evolutor receiving constraints only for selected tables."""

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
        selection_result: dict[str, Any],
        validation_feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing_table_names = set(existing_schema.get("tables", {}))
        selected_tables = [
            table_name
            for table_name in selection_result.get("selected_tables", [])
            if table_name in existing_table_names
        ]
        filtered_constraints = filter_constraints_to_tables(
            existing_constraints,
            selected_tables,
        )

        terminal_message(
            "info",
            "Constraint filter retained the subgraph induced by "
            f"{selected_tables}.",
            "\t",
        )

        return super().__call__(
            incoming_schema=incoming_schema,
            incoming_values=incoming_values,
            incoming_profile=incoming_profile,
            existing_schema=existing_schema,
            existing_values=existing_values,
            existing_profiles=existing_profiles,
            existing_constraints=filtered_constraints,
            selection_result=selection_result,
            validation_feedback=validation_feedback,
        )
