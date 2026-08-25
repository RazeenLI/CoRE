from __future__ import annotations

from pathlib import Path
from typing import Any

from model.agents.profiler_agent import ProfilerAgent
from model.agents.validator_agent import ValidatorAgent
from model.core.decision import build_decision
from model.core.state import Agents, TaskState, TaskStatus, TaskStep
from model.proposal.applier import apply_proposal
from model.proposal.builder import build_proposal
from model.proposal.updater import apply_update_plan_to_existing_parts

from baselines.no_selector.model.evolutor_agent import EvolutorAgent

class Orchestrator:
    """Independent Profiler -> Evolutor -> Validator workflow."""

    def __init__(
        self,
        *,
        profiler_agent: ProfilerAgent,
        evolutor_agent: EvolutorAgent,
        validator_agent: ValidatorAgent,
        save_path: str | Path,
        config: dict[str, Any],
    ) -> None:
        self.profiler = profiler_agent
        self.evolutor = evolutor_agent
        self.validator = validator_agent
        self.decision = build_decision(config.get("decision_auto", False))
        self.max_validator_runs = config.get("max_validator_runs", 3)
        self.max_decision_runs = config.get("max_decision_runs", 3)
        self.save_path = Path(save_path)

    def run_task(
        self,
        *,
        task_id: str,
        existing_rdb: dict[str, Any],
        incoming_table: dict[str, Any],
    ) -> tuple[TaskState, dict[str, Any] | None]:
        state = TaskState(
            id=task_id,
            existing_rdb=existing_rdb,
            incoming_table=incoming_table,
        )
        state.set_routing(
            TaskStep.PROFILING,
            "Start No-Matcher task.",
            TaskStep.INITIALIZED,
        )

        with state.measure_end_to_end():
          while state.status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
            step = state.routing["next_step"]
            with state.measure_step(step):
              if step == TaskStep.PROFILING:
                self._run_profiler(state)
              elif step == TaskStep.EVOLVING:
                self._run_evolutor(state)
              elif step == TaskStep.BUILDING_PROPOSAL:
                self._build_proposal(state)
              elif step == TaskStep.BUILDING_PREVIEW:
                self._build_preview(state)
              elif step == TaskStep.VALIDATING:
                self._run_validator(state)
              elif step == TaskStep.AWAITING_DECISION:
                self._finalize_decision(state)
              elif step == TaskStep.APPLYING_DECISION:
                self._apply_decision(state)
              elif step == TaskStep.COMPLETED:
                state.update_status(
                    TaskStep.COMPLETED,
                    TaskStatus.SUCCEEDED,
                    "No-Matcher task completed.",
                )
              else:
                state.update_status(
                    TaskStep.ERROR,
                    TaskStatus.FAILED,
                    f"Unsupported No-Matcher step: {step}",
                )
        return state, state.proposal_result

    def _run_profiler(self, state: TaskState) -> None:
        result = self.profiler(
            incoming_schema=state.incoming_schema,
            incoming_values=state.incoming_values,
        )
        state.save_result(TaskStep.PROFILING, result, "Profiler completed.")
        state.set_routing(TaskStep.EVOLVING, "Profiler completed.", TaskStep.PROFILING)

    def _validation_feedback(self, state: TaskState) -> dict[str, Any] | None:
        if state.routing.get("source_step") != TaskStep.VALIDATING:
            return None
        result = state.validation_result
        if result is None:
            return None
        return {
            "issues": result.get("issues", []),
            "summary": result.get("summary", ""),
        }

    def _run_evolutor(self, state: TaskState) -> None:
        result = self.evolutor(
            incoming_schema=state.incoming_schema,
            incoming_values=state.incoming_values,
            incoming_profile=state.profile_result,
            existing_schema=state.existing_schema,
            existing_values=state.existing_values,
            existing_profiles=state.existing_profiles,
            existing_constraints=state.constraints,
            validation_feedback=self._validation_feedback(state),
        )
        state.save_result(TaskStep.EVOLVING, result, "Evolutor completed.")
        state.set_routing(TaskStep.BUILDING_PROPOSAL, "Evolutor completed.", TaskStep.EVOLVING)

    def _build_proposal(self, state: TaskState) -> None:
        result = build_proposal(
            incoming_schema=state.incoming_schema,
            incoming_values=state.incoming_values,
            existing_schema=state.existing_schema,
            existing_values=state.existing_values,
            existing_constraints=state.constraints,
            result={"source": Agents.EVOLUTOR, "payload": state.evolutor_result},
        )
        state.save_result(TaskStep.BUILDING_PROPOSAL, result, "Proposal built.")
        state.set_routing(TaskStep.BUILDING_PREVIEW, "Proposal built.", TaskStep.BUILDING_PROPOSAL)

    def _build_preview(self, state: TaskState) -> None:
        result = apply_proposal(
            incoming_schema=state.incoming_schema,
            existing_schema=state.existing_schema,
            existing_constraints=state.constraints,
            proposal=state.proposal_result,
        )
        state.save_result(TaskStep.BUILDING_PREVIEW, result, "Preview built.")
        state.set_routing(TaskStep.VALIDATING, "Preview built.", TaskStep.BUILDING_PREVIEW)

    def _run_validator(self, state: TaskState) -> None:
        if len(state.results[TaskStep.VALIDATING]) >= self.max_validator_runs:
            state.update_status(
                TaskStep.ERROR,
                TaskStatus.FAILED,
                "Validator retry limit exceeded.",
            )
            return
        result = self.validator(
            proposal=state.proposal_result,
            before=state.preview_result["before"],
            after=state.preview_result["after"],
        )
        state.save_result(TaskStep.VALIDATING, result, "Validator completed.")
        next_step = (
            TaskStep.AWAITING_DECISION
            if result["route"] == "decision"
            else TaskStep.EVOLVING
            if result["route"] in {"matcher", "evolutor"}
            else TaskStep.ERROR
        )
        state.set_routing(
            next_step,
            result.get("summary", "Validator routing."),
            TaskStep.VALIDATING,
        )

    def _finalize_decision(self, state: TaskState) -> None:
        if len(state.results[TaskStep.AWAITING_DECISION]) >= self.max_decision_runs:
            state.update_status(
                TaskStep.ERROR,
                TaskStatus.FAILED,
                "Decision retry limit exceeded.",
            )
            return
        result = self.decision(
            task_id=state.id,
            incoming_schema=state.incoming_schema,
            incoming_values=state.incoming_values,
            existing_schema=state.existing_schema,
            constraints=state.constraints,
            existing_values=state.existing_values,
            existing_profiles=state.existing_profiles,
            results=state.results,
            trace=state.trace,
            save_path=self.save_path / "visualization",
        )
        state.save_result(TaskStep.AWAITING_DECISION, result, "Decision completed.")
        state.set_routing(
            TaskStep.APPLYING_DECISION if result["approved"] else TaskStep.EVOLVING,
            result.get("summary", "Decision routing."),
            TaskStep.AWAITING_DECISION,
        )

    def _apply_decision(self, state: TaskState) -> None:
        (
            state.existing_schema,
            state.constraints,
            state.existing_profiles,
            state.existing_values,
        ) = apply_update_plan_to_existing_parts(
            schema=state.existing_schema,
            constraints=state.constraints,
            profiles=state.existing_profiles,
            sample_values=state.existing_values,
            incoming_values=state.incoming_values,
            proposal=state.proposal_result,
            update_plan=state.preview_result,
        )
        state.set_routing(
            TaskStep.COMPLETED,
            "Approved No-Matcher update applied.",
            TaskStep.APPLYING_DECISION,
        )
