from __future__ import annotations

from pathlib import Path
from typing import Any

from model.agents.evolutor_agent import EvolutorAgent
from model.agents.profiler_agent import ProfilerAgent
from model.agents.selector_agent import CandidateSelectorAgent
from model.core.orchestrator import Orchestrator
from model.core.state import TaskState, TaskStep
from model.proposal.applier import apply_proposal


class NoValidatorOrchestrator(Orchestrator):
    """Standard orchestrator that accepts the first proposal without validation."""

    def __init__(
        self,
        *,
        profiler_agent: ProfilerAgent,
        selector_agent: CandidateSelectorAgent,
        evolutor_agent: EvolutorAgent,
        save_path: str | Path,
        config: dict[str, Any],
    ) -> None:
        super().__init__(
            profiler_agent=profiler_agent,
            selector_agent=selector_agent,
            evolutor_agent=evolutor_agent,
            validator_agent=None,  # type: ignore[arg-type]
            save_path=save_path,
            config=config,
        )

    def _build_preview(self, task_state: TaskState) -> None:
        preview_result = apply_proposal(
            incoming_schema=task_state.incoming_schema,
            existing_schema=task_state.existing_schema,
            existing_constraints=task_state.constraints,
            proposal=task_state.proposal_result,
        )
        task_state.save_result(
            step=TaskStep.BUILDING_PREVIEW,
            result=preview_result,
            message="Proposal preview built without Validator.",
        )
        task_state.set_routing(
            next_step=TaskStep.AWAITING_DECISION,
            reason="No-Validator ablation skips validation.",
            source_step=TaskStep.BUILDING_PREVIEW,
        )
