from __future__ import annotations

from pathlib import Path
from typing import Any

from baselines.oneshot.model.agent import EvolutorAgent
from model.core.decision import build_decision
from model.core.state import Agents, TaskState, TaskStatus, TaskStep
from model.proposal.applier import apply_proposal
from model.proposal.builder import build_proposal
from model.proposal.updater import apply_update_plan_to_existing_parts
from model.utils.io import terminal_message


class Orchestrator:
    """Controller for one one-shot incoming-table task."""

    def __init__(
        self,
        evolutor_agent: EvolutorAgent,
        save_path: str | Path,
        config: dict[str, Any],
    ) -> None:
        self.evolutor = evolutor_agent
        self.decision = build_decision(
            config.get("decision_auto", False)
        )
        self.max_decision_runs = config.get("max_decision_runs", 3)
        self.config = config
        self.save_path = Path(save_path)

    def run_task(
        self,
        task_id: str,
        existing_rdb: dict[str, Any],
        incoming_table: dict[str, Any],
    ) -> tuple[TaskState, dict[str, Any] | None]:
        task_state = self._create_state(
            task_id=task_id,
            existing_rdb=existing_rdb,
            incoming_table=incoming_table,
        )

        while task_state.status not in {
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
        }:
            next_step = task_state.routing["next_step"]

            if next_step == TaskStep.EVOLVING:
                self._run_evolutor(task_state)

            elif next_step == TaskStep.BUILDING_PROPOSAL:
                self._build_proposal(task_state)

            elif next_step == TaskStep.BUILDING_PREVIEW:
                self._build_preview(task_state)

            elif next_step == TaskStep.AWAITING_DECISION:
                self._finalize_decision(task_state)

            elif next_step == TaskStep.APPLYING_DECISION:
                self._apply_final_decision(task_state)

            elif next_step == TaskStep.COMPLETED:
                task_state.update_status(
                    current_step=TaskStep.COMPLETED,
                    status=TaskStatus.SUCCEEDED,
                    message="One-shot task completed successfully.",
                )
                break

            elif next_step == TaskStep.ERROR:
                task_state.update_status(
                    current_step=TaskStep.ERROR,
                    status=TaskStatus.FAILED,
                    message="One-shot task failed.",
                )
                break

            else:
                task_state.set_routing(
                    next_step=TaskStep.ERROR,
                    reason=f"Unknown next_step: {next_step}",
                    source_step=task_state.current_step,
                )

        return task_state, task_state.proposal_result

    def _create_state(
        self,
        task_id: str,
        existing_rdb: dict[str, Any],
        incoming_table: dict[str, Any],
    ) -> TaskState:
        task_state = TaskState(
            id=task_id,
            existing_rdb=existing_rdb,
            incoming_table=incoming_table,
        )
        task_state.set_routing(
            next_step=TaskStep.EVOLVING,
            reason="Start new one-shot integration task.",
            source_step=TaskStep.INITIALIZED,
        )
        return task_state

    def _run_evolutor(self, task_state: TaskState) -> None:
        evolutor_result = self.evolutor(
            incoming_schema=task_state.incoming_schema,
            incoming_values=task_state.incoming_values,
            existing_schema=task_state.existing_schema,
            existing_values=task_state.existing_values,
            existing_profiles=task_state.existing_profiles,
            existing_constraints=task_state.constraints,
        )

        task_state.save_result(
            step=TaskStep.EVOLVING,
            result=evolutor_result,
            message="One-shot Evolutor completed successfully.",
        )
        task_state.set_routing(
            next_step=TaskStep.BUILDING_PROPOSAL,
            reason="One-shot Evolutor completed successfully.",
            source_step=TaskStep.EVOLVING,
        )

    def _build_proposal(self, task_state: TaskState) -> None:
        proposal_result = build_proposal(
            incoming_schema=task_state.incoming_schema,
            incoming_values=task_state.incoming_values,
            existing_schema=task_state.existing_schema,
            existing_values=task_state.existing_values,
            existing_constraints=task_state.constraints,
            result={
                "source": Agents.EVOLUTOR,
                "payload": task_state.evolutor_result,
            },
        )

        task_state.save_result(
            step=TaskStep.BUILDING_PROPOSAL,
            result=proposal_result,
            message="One-shot proposal was built successfully.",
        )
        task_state.set_routing(
            next_step=TaskStep.BUILDING_PREVIEW,
            reason="One-shot proposal was built successfully.",
            source_step=TaskStep.BUILDING_PROPOSAL,
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
            message="One-shot proposal preview was generated successfully.",
        )
        task_state.set_routing(
            next_step=TaskStep.AWAITING_DECISION,
            reason="One-shot proposal preview was generated successfully.",
            source_step=TaskStep.BUILDING_PREVIEW,
        )

    def _finalize_decision(self, task_state: TaskState) -> None:
        decision_run_count = len(
            task_state.results[TaskStep.AWAITING_DECISION]
        )

        if decision_run_count >= self.max_decision_runs:
            terminal_message("error", "Decision exceeded the maximum retry limit.", "\t")
            task_state.save_result(
                step=TaskStep.AWAITING_DECISION,
                result={
                    "approved": False,
                    "summary": "Decision exceeded the maximum retry limit.",
                },
                message="Decision exceeded the maximum retry limit.",
            )
            task_state.set_routing(
                next_step=TaskStep.ERROR,
                reason="Decision exceeded the maximum retry limit.",
                source_step=TaskStep.AWAITING_DECISION,
            )
            return

        decision_result = self.decision(
            task_id=task_state.id,
            incoming_schema=task_state.incoming_schema,
            incoming_values=task_state.incoming_values,
            existing_schema=task_state.existing_schema,
            constraints=task_state.constraints,
            existing_values=task_state.existing_values,
            existing_profiles=task_state.existing_profiles,
            results=task_state.results,
            trace=task_state.trace,
            save_path=self.save_path / "visualization",
        )

        task_state.save_result(
            step=TaskStep.AWAITING_DECISION,
            result=decision_result,
            message=(
                "Decision was approved."
                if decision_result["approved"]
                else "Decision was rejected."
            ),
        )

        if decision_result["approved"]:
            task_state.set_routing(
                next_step=TaskStep.APPLYING_DECISION,
                reason="Decision was approved.",
                source_step=TaskStep.AWAITING_DECISION,
            )
        else:
            task_state.set_routing(
                next_step=TaskStep.EVOLVING,
                reason=decision_result.get(
                    "summary",
                    "Decision was rejected; rerun the one-shot Evolutor.",
                ),
                source_step=TaskStep.AWAITING_DECISION,
            )

    def _apply_final_decision(self, task_state: TaskState) -> None:
        task_state.update_status(
            current_step=TaskStep.APPLYING_DECISION,
            status=TaskStatus.RUNNING,
            message="Applying approved one-shot decision.",
        )

        (
            updated_schema,
            updated_constraints,
            updated_profiles,
            updated_values,
        ) = apply_update_plan_to_existing_parts(
            schema=task_state.existing_schema,
            constraints=task_state.constraints,
            profiles=task_state.existing_profiles,
            sample_values=task_state.existing_values,
            incoming_values=task_state.incoming_values,
            proposal=task_state.proposal_result,
            update_plan=task_state.preview_result,
        )

        task_state.existing_schema = updated_schema
        task_state.constraints = updated_constraints
        task_state.existing_profiles = updated_profiles
        task_state.existing_values = updated_values

        task_state.set_routing(
            next_step=TaskStep.COMPLETED,
            reason="Approved one-shot update was applied.",
            source_step=TaskStep.APPLYING_DECISION,
        )
