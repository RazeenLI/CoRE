from __future__ import annotations

from typing import Any

from model.agents.evolutor_agent import EvolutorAgent
from model.agents.profiler_agent import ProfilerAgent
from model.agents.selector_agent import CandidateSelectorAgent


class NoValuesProfilerAgent(ProfilerAgent):
    """Run the Standard profiler without exposing incoming cell values."""

    def __call__(
        self,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
    ) -> dict[str, Any]:
        del incoming_values
        return super().__call__(
            incoming_schema=incoming_schema,
            incoming_values=[],
        )


class NoValuesSelectorAgent(CandidateSelectorAgent):
    """Retrieve candidates from table/column names and types only."""

    def __call__(
        self,
        *,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
        existing_schema: dict[str, Any],
        existing_values: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        del incoming_values, existing_values
        return super().__call__(
            incoming_schema=incoming_schema,
            incoming_values=[],
            existing_schema=existing_schema,
            existing_values={},
        )


class NoValuesEvolutorAgent(EvolutorAgent):
    """Run the Standard Evolutor with profiles but without raw cell values."""

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
        del incoming_values, existing_values
        return super().__call__(
            incoming_schema=incoming_schema,
            incoming_values=[],
            incoming_profile=incoming_profile,
            existing_schema=existing_schema,
            existing_values={},
            existing_profiles=existing_profiles,
            existing_constraints=existing_constraints,
            selection_result=selection_result,
            validation_feedback=validation_feedback,
        )
