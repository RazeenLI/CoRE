from __future__ import annotations

from pathlib import Path
from typing import Any

from baselines.traditional.model.matcher import TraditionalMatcher
from baselines.traditional.model.rules import OperationThresholds, build_rule_result
from model.core.decision import build_decision
from model.core.state import Agents, TaskState, TaskStatus, TaskStep
from model.proposal.applier import apply_proposal
from model.proposal.builder import build_proposal
from model.proposal.updater import apply_update_plan_to_existing_parts


class Orchestrator:
    """Shared non-LLM controller for JL and COMA baselines."""

    def __init__(
        self,
        *,
        matcher: TraditionalMatcher,
        matcher_name: str,
        save_path: str | Path,
        config: dict[str, Any],
    ) -> None:
        self.matcher = matcher
        self.matcher_name = matcher_name
        self.thresholds = OperationThresholds(
            column_match_confidence=config.get("column_match_confidence", 0.70),
            insert_table_confidence=config.get("insert_table_confidence", 0.70),
            extend_table_confidence=config.get("extend_table_confidence", 0.35),
            insert_coverage=config.get("insert_coverage", 1.00),
        )
        self.decision = build_decision(config.get("decision_auto", True))
        self.save_path = Path(save_path)

    def run_task(
        self,
        *,
        task_id: str,
        existing_rdb: dict[str, Any],
        incoming_table: dict[str, Any],
    ) -> tuple[TaskState, dict[str, Any] | None]:
        state = TaskState(id=task_id, existing_rdb=existing_rdb, incoming_table=incoming_table)
        task_started_at = state.start_timer()
        with state.measure_step(TaskStep.MATCHING):
            match_result = self.matcher(
                incoming_schema=state.incoming_schema,
                incoming_values=state.incoming_values,
                existing_schema=state.existing_schema,
                existing_values=state.existing_values,
                existing_profiles=state.existing_profiles,
            )
        state.save_result(TaskStep.MATCHING, match_result, f"{self.matcher_name} matching completed.")

        with state.measure_step(TaskStep.EVOLVING):
            rule_result = build_rule_result(
                matcher_name=self.matcher_name,
                incoming_schema=state.incoming_schema,
                existing_schema=state.existing_schema,
                existing_constraints=state.constraints,
                matching_result=match_result,
                thresholds=self.thresholds,
            )
        state.save_result(TaskStep.EVOLVING, rule_result, "Rule-based operation decision completed.")

        with state.measure_step(TaskStep.BUILDING_PROPOSAL):
            proposal = build_proposal(
                incoming_schema=state.incoming_schema,
                incoming_values=state.incoming_values,
                existing_schema=state.existing_schema,
                existing_values=state.existing_values,
                existing_constraints=state.constraints,
                result={"source": Agents.EVOLUTOR, "payload": rule_result},
            )
        state.save_result(TaskStep.BUILDING_PROPOSAL, proposal, "Rule-based proposal completed.")
        with state.measure_step(TaskStep.BUILDING_PREVIEW):
            preview = apply_proposal(
                incoming_schema=state.incoming_schema,
                existing_schema=state.existing_schema,
                existing_constraints=state.constraints,
                proposal=proposal,
            )
        state.save_result(TaskStep.BUILDING_PREVIEW, preview, "Proposal preview completed.")

        with state.measure_step(TaskStep.AWAITING_DECISION):
            decision_result = self.decision(
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
        state.save_result(TaskStep.AWAITING_DECISION, decision_result, "Baseline decision completed.")
        if not decision_result["approved"]:
            state.update_status(TaskStep.ERROR, TaskStatus.FAILED, "Baseline proposal was rejected.")
            state.finish_end_to_end(task_started_at)
            return state, proposal

        with state.measure_step(TaskStep.APPLYING_DECISION):
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
            proposal=proposal,
            update_plan=preview,
          )
        state.set_routing(
            next_step=TaskStep.COMPLETED,
            reason=f"{self.matcher_name} baseline result applied.",
            source_step=TaskStep.APPLYING_DECISION,
        )
        state.update_status(
            TaskStep.COMPLETED,
            TaskStatus.SUCCEEDED,
            f"{self.matcher_name} baseline completed successfully.",
        )
        state.finish_end_to_end(task_started_at)
        return state, proposal
