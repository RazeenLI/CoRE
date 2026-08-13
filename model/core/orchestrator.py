from typing import Any
from pathlib import Path
from model.utils.io import terminal_message, load_json, save_json
from model.core.state import Agents, TaskStep, TaskStatus, TaskState

from model.proposal.builder import build_proposal
from model.proposal.applier import apply_proposal
from model.proposal.updater import apply_update_plan_to_existing_parts

from model.agents.base_agent import BaseAgent
from model.agents.profiler_agent import ProfilerAgent
from model.agents.matcher_agent import MatcherAgent
from model.agents.evolutor_agent import EvolutorAgent
from model.agents.validator_agent import ValidatorAgent
from model.core.decision import build_decision

VALIDATOR_ROUTE_TO_STEP = {
    "decision": TaskStep.AWAITING_DECISION,
    "matcher": TaskStep.MATCHING,
    "evolutor": TaskStep.EVOLVING,
    "error": TaskStep.ERROR,
}

class Orchestrator:
    """
    Run-level controller for the RDB integration pipeline.

    The orchestrator owns the workflow logic:
    - calls agents
    - routes task execution
    - updates TaskState
    - returns task result

    It does not load datasets or implement agent reasoning.
    """

    def __init__(
        self,
        profiler_agent: ProfilerAgent,
        matcher_agent: MatcherAgent,
        evolutor_agent: EvolutorAgent,
        validator_agent: ValidatorAgent,
        save_path: str | Path,
        config,
    ) -> None:
        self.profiler = profiler_agent
        self.matcher = matcher_agent
        self.evolutor = evolutor_agent
        self.validator = validator_agent
        self.decision = build_decision(config.get("decision_auto", False))

        self.threshold = config.get("high_confidence_threshold", 0.8)
        self.max_validator_runs = config.get("max_validator_runs", 3)
        self.max_decision_runs = config.get("max_decision_runs", 3)
        self.config = config
        self.save_path = Path(save_path)


    def run_task(self, task_id, existing_rdb, incoming_table):
        task_state = self._create_state(task_id, existing_rdb, incoming_table)

        while task_state.status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
            next_step = task_state.routing["next_step"]

            if next_step == TaskStep.PROFILING:
                self._run_profiler(task_state)

            elif next_step == TaskStep.MATCHING:
                self._run_matcher(task_state)

            elif next_step == TaskStep.EVOLVING:
                self._run_evolutor(task_state)

            elif next_step == TaskStep.BUILDING_PROPOSAL:
                self._build_mapping_proposal(task_state)

            elif next_step == TaskStep.BUILDING_PREVIEW:
                self._build_preview(task_state)

            elif next_step == TaskStep.VALIDATING:
                self._run_validator(task_state)

            elif next_step == TaskStep.AWAITING_DECISION:
                self._finalize_decision(task_state)

            elif next_step == TaskStep.APPLYING_DECISION:
                self._apply_final_decision(task_state)

            elif next_step == TaskStep.COMPLETED:
                task_state.update_status(
                    current_step=TaskStep.COMPLETED,
                    status=TaskStatus.SUCCEEDED,
                    message="Task completed successfully.",
                )
                break

            elif next_step == TaskStep.ERROR:
                task_state.update_status(
                    current_step=TaskStep.ERROR,
                    status=TaskStatus.FAILED,
                    message="Task failed.",
                )
                break

            else:
                task_state.set_routing(
                    next_step=TaskStep.ERROR,
                    reason=f"Unknown next_step: {next_step}",
                    source_step=task_state.current_step,
                )

        return task_state, task_state.proposal_result

    def _create_state(self, task_id, existing_rdb, incoming_table) -> TaskState:
        task_state = TaskState(
            id=task_id,
            existing_rdb=existing_rdb,
            incoming_table=incoming_table,
        )
        task_state.set_routing(
            next_step=TaskStep.PROFILING,
            reason="Start new task.",
            source_step=TaskStep.INITIALIZED,
        )
        return task_state

    def _run_profiler(self, task_state: TaskState):
        profiler_result = self.profiler(
            incoming_schema=task_state.incoming_schema,
            incoming_values=task_state.incoming_values,
        )
        task_state.save_result(
            step=TaskStep.PROFILING,
            result=profiler_result,
            # status="success",
            message="Profiler completed successfully.",
        )
        task_state.set_routing(
            next_step=TaskStep.MATCHING,
            reason="Profiler completed successfully.",
            source_step=TaskStep.PROFILING,
        )

    def _get_validation_feedback(
        self,
        task_state: TaskState,
    ) -> dict[str, Any] | None:
        if task_state.routing.get("source_step") != TaskStep.VALIDATING:
            return None

        validation_result = task_state.validation_result

        if validation_result is None:
            return None

        return {
            "issues": validation_result.get("issues", []),
            "summary": validation_result.get("summary", ""),
        }

    def _run_matcher(self, task_state: TaskState):
        matcher_result = self.matcher(
            incoming_schema=task_state.incoming_schema,
            incoming_values=task_state.incoming_values,
            incoming_profile=task_state.profile_result,
            existing_schema=task_state.existing_schema,
            existing_values=task_state.existing_values,
            existing_profiles=task_state.existing_profiles,
            validation_feedback=self._get_validation_feedback(task_state),
        )
        task_state.save_result(
            step=TaskStep.MATCHING,
            result=matcher_result,
            # status="success",
            message="Matcher completed successfully.",
        )

        confidence = matcher_result["table_matches"][0].get("confidence", 0.0)

        selected_match = matcher_result["table_matches"][0]
        confidence = selected_match["confidence"]

        has_empty_column_candidates = any(
            not candidates
            for candidates in selected_match.get("column_matches", {}).values()
        )

        if confidence >= self.threshold and not has_empty_column_candidates:
            task_state.set_routing(
                next_step=TaskStep.BUILDING_PROPOSAL,
                reason=f"Matcher confidence {confidence} >= threshold {self.threshold}.",
                source_step=TaskStep.MATCHING,
            )
        else:
            task_state.set_routing(
                next_step=TaskStep.EVOLVING,
                reason=f"Matcher confidence {confidence} < threshold {self.threshold}.",
                source_step=TaskStep.MATCHING,
            )

    def _run_evolutor(self, task_state: TaskState):
        evolutor_result = self.evolutor(
            incoming_schema=task_state.incoming_schema,
            incoming_values=task_state.incoming_values,
            incoming_profile=task_state.profile_result,
            matcher_result=task_state.match_result,
            existing_schema=task_state.existing_schema,
            existing_values=task_state.existing_values,
            existing_profiles=task_state.existing_profiles,
            existing_constraints=task_state.constraints,
            validation_feedback=self._get_validation_feedback(task_state),
        )
        task_state.save_result(
            step=TaskStep.EVOLVING,
            result=evolutor_result,
            # status="success",
            message="Evolutor completed successfully.",
        )

        task_state.set_routing(
            next_step=TaskStep.BUILDING_PROPOSAL,
            reason=f"Evolutor completed successfully.",
            source_step=TaskStep.EVOLVING,
        )

    def _build_mapping_proposal(self, task_state: TaskState):
        if task_state.routing["source_step"] == TaskStep.MATCHING:
            proposal_result = build_proposal(
                incoming_schema=task_state.incoming_schema,
                incoming_values=task_state.incoming_values,
                existing_schema=task_state.existing_schema,
                existing_values=task_state.existing_values,
                existing_constraints=task_state.constraints,
                result={
                    "source": Agents.MATCHER,
                    "payload": task_state.match_result,
                },
            )
        elif task_state.routing["source_step"] == TaskStep.EVOLVING:
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
        
        else:
            raise ValueError(f"Unsupported source_step: {task_state.routing['source_step']}")

        task_state.save_result(
            step=TaskStep.BUILDING_PROPOSAL,
            result=proposal_result,
            # status="success",
            message=f"{task_state.routing['source_step'].capitalize()} proposal is builded",
        )

        task_state.set_routing(
            next_step=TaskStep.BUILDING_PREVIEW,
            reason=f"Proposal is builded.",
            source_step=TaskStep.BUILDING_PROPOSAL,
        )

    def _build_preview(self, task_state: TaskState):
        
        preview_result = apply_proposal(
            incoming_schema=task_state.incoming_schema,
            existing_schema=task_state.existing_schema,
            existing_constraints=task_state.constraints,
            proposal=task_state.proposal_result,
            
        )

        task_state.save_result(
            step=TaskStep.BUILDING_PREVIEW,
            result=preview_result,
            # status="success",
            message=f"Proposal is applied",
        )

        task_state.set_routing(
            next_step=TaskStep.VALIDATING,
            reason=f"Proposal is applied.",
            source_step=TaskStep.BUILDING_PREVIEW,
        )
    
    def _run_validator(self, task_state: TaskState):
        validator_run_count = len(task_state.results[TaskStep.VALIDATING])

        if validator_run_count >= self.max_validator_runs:
            terminal_message("error", f"Validator ran more than the maximum allowed number of runs.", "\t")
            task_state.save_result(
                step=TaskStep.VALIDATING,
                result={
                    "route": "error",
                    "score": 0.0,
                    "rule_checks": {},
                    "issues": ["validator exceeded maximum retry limit"],
                    "summary": "Validator exceeded maximum retry limit.",
                },
                # status="failed",
                message="Validator exceeded maximum retry limit.",
            )

            task_state.set_routing(
                next_step=TaskStep.ERROR,
                reason="Validator exceeded maximum retry limit.",
                source_step=TaskStep.VALIDATING,
            )
            return
        
        validator_result = self.validator(
            proposal=task_state.proposal_result,
            before=task_state.preview_result["before"],
            after=task_state.preview_result["after"],
        )

        next_step = VALIDATOR_ROUTE_TO_STEP[validator_result["route"]]

        task_state.save_result(
            step=TaskStep.VALIDATING,
            result=validator_result,
            # status="success",
            message=f"Validator finish dicesion: go to {validator_result['route']}",
        )

        task_state.set_routing(
            next_step=next_step,
            reason=validator_result["summary"],
            source_step=TaskStep.VALIDATING,
        )

    def _finalize_decision(self, task_state: TaskState):
        decision_run_count = len(task_state.results[TaskStep.AWAITING_DECISION])

        if decision_run_count >= self.max_decision_runs:
            terminal_message("error", f"Decision ran more than the maximum allowed number of runs.", "\t")
            task_state.save_result(
                step=TaskStep.AWAITING_DECISION,
                result={
                    "approved": False,
                    "summary": "Decision exceeded maximum retry limit."
                },
                # status="failed",
                message="Decision exceeded maximum retry limit.",
            )

            task_state.set_routing(
                next_step=TaskStep.ERROR,
                reason="Decision exceeded maximum retry limit.",
                source_step=TaskStep.AWAITING_DECISION,
            )
            return
        # terminal input

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

        if decision_result["approved"]:
            task_state.save_result(
                step=TaskStep.AWAITING_DECISION,
                result=decision_result,
                # status="success",
                message="Decision is approved.",
            )

            task_state.set_routing(
                next_step=TaskStep.APPLYING_DECISION,
                reason=f"Decision is approved.",
                source_step=TaskStep.AWAITING_DECISION,
            )
        else:
            task_state.save_result(
                step=TaskStep.AWAITING_DECISION,
                result=decision_result,
                # status="success",
                message="Decision is rejected.",
            )

            task_state.set_routing(
                next_step=TaskStep.PROFILING,
                reason=f"Decision is rejected.",
                source_step=TaskStep.AWAITING_DECISION,
            )
        pass

    def _apply_final_decision(self, task_state: TaskState):

        task_state.update_status(
            current_step=TaskStep.APPLYING_DECISION,
            status=TaskStatus.RUNNING,
            message="Applying approved decision.",
        )

        updated_schema, updated_constraints, updated_profiles, updated_values = apply_update_plan_to_existing_parts(
            schema=task_state.existing_schema,
            constraints=task_state.constraints,
            profiles=task_state.existing_profiles,
            sample_values=task_state.existing_values,
            incoming_values=task_state.incoming_values,
            proposal=task_state.proposal_result,
            update_plan=task_state.preview_result,
        )

        task_state.existing_schema = updated_schema
        task_state.existing_profiles = updated_profiles
        task_state.constraints = updated_constraints
        task_state.existing_values = updated_values
        
        task_state.set_routing(
            next_step=TaskStep.COMPLETED,
            reason=f"Finish and Updated.",
            source_step=TaskStep.APPLYING_DECISION,
        )
    
    # @classmethod
    # def from_state_json(
    #     cls,
    #     state_path: str | Path,
    #     profiler_agent: Any,
    #     matcher_agent: Any,
    #     evolutor_agent: Any,
    #     validator_agent: Any,
    #     config: dict[str, Any],
    # ) -> "Orchestrator":
    #     """
    #     Resume an Orchestrator from a saved RunState JSON file.

    #     Agents are recreated outside and passed in.
    #     RunState is restored from JSON.
    #     """

    #     state_path = Path(state_path)
    #     state_data = load_json(state_path)
    #     run_state = TaskState.from_dict(state_data)

    #     orchestrator = cls(
    #         profiler_agent=profiler_agent,
    #         matcher_agent=matcher_agent,
    #         evolutor_agent=evolutor_agent,
    #         validator_agent=validator_agent,
    #         config=config,
    #     )

    #     orchestrator.run_state = run_state

    #     return orchestrator
    
    # def save_state(self, state_path: str | Path) -> None:
    #     """
    #     Save current RunState to a JSON file.
    #     """

    #     state_path = Path(state_path)
    #     save_json(self.run_state.to_dict(), state_path)
