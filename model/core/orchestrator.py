from typing import Any
from pathlib import Path
from model.utils.io import terminal_message, load_json, save_json
from model.core.state import RunState, TaskState

from model.proposal.builder import build_proposal
from model.proposal.applier import apply_proposal
from model.proposal.updater import apply_update_plan_to_existing_parts

from model.agents.base_agent import BaseAgent
from model.agents.profiler_agent import ProfilerAgent
from model.agents.matcher_agent import MatcherAgent
from model.agents.evolutor_agent import EvolutorAgent
from model.agents.validator_agent import ValidatorAgent
from model.core.decision import build_decision

class Orchestrator:
    """
    Run-level controller for the RDB integration pipeline.

    The orchestrator owns the workflow logic:
    - calls agents
    - routes task execution
    - updates RunState / TaskState
    - returns task result

    It does not load datasets or implement agent reasoning.
    """

    def __init__(
        self,
        profiler_agent: ProfilerAgent,
        matcher_agent: MatcherAgent,
        evolutor_agent: EvolutorAgent,
        validator_agent: ValidatorAgent,
        # decision_agent: BaseAgent,
        existing_rdb,
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
        self.save_path = save_path

        self.run_state = RunState(existing_rdb=existing_rdb)

    def run_task(self, task_id, incoming_table):
        task_state = self.run_state.start_task(incoming_table, task_id)

        if not task_state.routing:
            task_state.set_routing(
                next_step="profiler",
                reason="Start new task.",
                source_step="orchestrator",
            )

        while task_state.status not in {"succeeded", "failed"}:
            next_step = task_state.routing["next_step"]

            if next_step == "profiler":
                self._run_profiler(task_state)

            elif next_step == "matcher":
                self._run_matcher(task_state)

            elif next_step == "evolutor":
                self._run_evolutor(task_state)

            elif next_step == "proposal":
                self._build_mapping_proposal(task_state)

            elif next_step == "preview":
                self._apply_mapping_proposal(task_state)

            elif next_step == "validator":
                self._run_validator(task_state)

            elif next_step == "decision":
                self._finalize_decision(task_state)

            elif next_step == "apply_decision":
                self._apply_final_decision(task_state)

            elif next_step == "finish_task":
                self.run_state.finish_task(task_id)
                break

            elif next_step == "error":
                task_state.status = "failed"
                break

            else:
                task_state.status = "failed"
                task_state.set_routing(
                    next_step="error",
                    reason=f"Unknown next_step: {next_step}",
                    source_step="orchestrator",
                )
                break

            # self.save_state(self.config["state_path"])

        return self.run_state.current_existing_rdb
        
    
    def _run_profiler(self, task_state: TaskState):
        profiler_result = self.profiler(
            incoming_schema=task_state.incoming_schema,
            incoming_values=task_state.incoming_values,
        )
        task_state.save_result(
            agent="profiler",
            result=profiler_result,
            status="success",
            message="Profiler completed successfully.",
        )
        task_state.set_routing(
            next_step="matcher",
            reason="Profiler completed successfully.",
            source_step="profiler",
        )

    def _run_matcher(self, task_state: TaskState):
        matcher_result = self.matcher(
            incoming_schema=task_state.incoming_schema,
            incoming_values=task_state.incoming_values,
            incoming_profile=task_state.results["profiler"][-1],
            existing_schema=task_state.existing_schema,
            existing_values=task_state.existing_values,
            existing_profiles=task_state.existing_profiles,
        )
        task_state.save_result(
            agent="matcher",
            result=matcher_result,
            status="success",
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
                next_step="proposal",
                reason=f"Matcher confidence {confidence} >= threshold {self.threshold}.",
                source_step="matcher",
            )
        else:
            task_state.set_routing(
                next_step="evolutor",
                reason=f"Matcher confidence {confidence} < threshold {self.threshold}.",
                source_step="matcher",
            )

    def _run_evolutor(self, task_state: TaskState):
        evolutor_result = self.evolutor(
            incoming_schema=task_state.incoming_schema,
            incoming_values=task_state.incoming_values,
            incoming_profile=task_state.results["profiler"][-1],
            matcher_result=task_state.results["matcher"][-1],
            existing_schema=task_state.existing_schema,
            existing_values=task_state.existing_values,
            existing_profiles=task_state.existing_profiles,
            existing_constraints=task_state.constraints,
        )
        task_state.save_result(
            agent="evolutor",
            result=evolutor_result,
            status="success",
            message="Evolutor completed successfully.",
        )

        task_state.set_routing(
            next_step="proposal",
            reason=f"Evolutor completed successfully.",
            source_step="evolutor",
        )

    def _build_mapping_proposal(self, task_state: TaskState):
        if task_state.routing["source_step"] == "matcher":
            proposal_result = build_proposal(
                incoming_schema=task_state.incoming_schema,
                incoming_values=task_state.incoming_values,
                existing_schema=task_state.existing_schema,
                existing_values=task_state.existing_values,
                existing_constraints=task_state.constraints,
                result={
                    "source":"matcher",
                    "payload": task_state.results["matcher"][-1],
                },
            )
        elif task_state.routing["source_step"] == "evolutor":
            proposal_result = build_proposal(
                incoming_schema=task_state.incoming_schema,
                incoming_values=task_state.incoming_values,
                existing_schema=task_state.existing_schema,
                existing_values=task_state.existing_values,
                existing_constraints=task_state.constraints,
                result={
                    "source":"evolutor",
                    "payload": task_state.results["evolutor"][-1],
                },
            )
        
        else:
            raise ValueError(f"Unsupported source_step: {task_state.routing['source_step']}")

        task_state.save_result(
            agent="proposal",
            result=proposal_result,
            status="success",
            message=f"{task_state.routing['source_step'].capitalize()} proposal is builded",
        )

        task_state.set_routing(
            next_step="preview",
            reason=f"Proposal is builded.",
            source_step="proposal",
        )

    def _apply_mapping_proposal(self, task_state: TaskState):
        
        preview_result = apply_proposal(
            incoming_schema=task_state.incoming_schema,
            existing_schema=task_state.existing_schema,
            existing_constraints=task_state.constraints,
            proposal=task_state.results["proposal"][-1],
            
        )

        task_state.save_result(
            agent="preview",
            result=preview_result,
            status="success",
            message=f"Proposal is applied",
        )

        task_state.set_routing(
            next_step="validator",
            reason=f"Proposal is applied.",
            source_step="preview",
        )
    
    def _run_validator(self, task_state: TaskState):
        validator_run_count = len(task_state.results.get("validator", []))

        if validator_run_count >= self.max_validator_runs:
            terminal_message("error", f"Validator ran more than the maximum allowed number of runs.", "\t")
            task_state.save_result(
                agent="validator",
                result={
                    "route": "error",
                    "score": 0.0,
                    "rule_checks": {},
                    "issues": ["validator exceeded maximum retry limit"],
                    "summary": "Validator exceeded maximum retry limit.",
                },
                status="failed",
                message="Validator exceeded maximum retry limit.",
            )

            task_state.set_routing(
                next_step="error",
                reason="Validator exceeded maximum retry limit.",
                source_step="validator",
            )
            return
        validator_result = self.validator(
            proposal=task_state.results["proposal"][-1],
            before=task_state.results["preview"][-1]["before"],
            after=task_state.results["preview"][-1]["after"],
        )

        task_state.save_result(
            agent="validator",
            result=validator_result,
            status="success",
            message=f"Validator finish dicesion: go to {validator_result['route']}",
        )

        task_state.set_routing(
            next_step=validator_result["route"],
            reason=validator_result["summary"],
            source_step="validator",
        )

    def _finalize_decision(self, task_state: TaskState):
        # TODO: Human in the loop
        decision_run_count = len(task_state.results.get("decision", []))

        if decision_run_count >= self.max_decision_runs:
            terminal_message("error", f"Decision ran more than the maximum allowed number of runs.", "\t")
            task_state.save_result(
                agent="decision",
                result={
                    "approved": False,
                    "summary": "Decision exceeded maximum retry limit."
                },
                status="failed",
                message="Decision exceeded maximum retry limit.",
            )

            task_state.set_routing(
                next_step="error",
                reason="Decision exceeded maximum retry limit.",
                source_step="decision",
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
            save_path=self.save_path + "/visualization",
        )

        if decision_result["approved"]:
            task_state.save_result(
                agent="decision",
                result=decision_result,
                status="success",
                message="Decision is approved.",
            )

            task_state.set_routing(
                next_step="apply_decision",
                reason=f"Decision is approved.",
                source_step="decision",
            )
        else:
            task_state.save_result(
                agent="decision",
                result=decision_result,
                status="success",
                message="Decision is rejected.",
            )

            task_state.set_routing(
                next_step="profiler",
                reason=f"Decision is rejected.",
                source_step="decision",
            )
        pass

    def _apply_final_decision(self, task_state: TaskState):
        # TODO: Auto apply after dedesided

        updated_schema, updated_constraints, updated_profiles = apply_update_plan_to_existing_parts(
            schema=task_state.existing_schema,
            constraints=task_state.constraints,
            profiles=task_state.existing_profiles,
            update_plan=task_state.results["preview"][-1],
        )

        task_state.existing_schema = updated_schema
        task_state.existing_profiles = updated_profiles
        task_state.constraints = updated_constraints
        
        task_state.set_routing(
            next_step="finish_task",
            reason=f"Finish and Updated.",
            source_step="finial_decision",
        )
        pass
    
    @classmethod
    def from_state_json(
        cls,
        state_path: str | Path,
        profiler_agent: Any,
        matcher_agent: Any,
        evolutor_agent: Any,
        validator_agent: Any,
        decision_agent: Any,
        config: dict[str, Any],
    ) -> "Orchestrator":
        """
        Resume an Orchestrator from a saved RunState JSON file.

        Agents are recreated outside and passed in.
        RunState is restored from JSON.
        """

        state_path = Path(state_path)
        state_data = load_json(state_path)
        run_state = RunState.from_dict(state_data)

        orchestrator = cls(
            profiler_agent=profiler_agent,
            matcher_agent=matcher_agent,
            evolutor_agent=evolutor_agent,
            validator_agent=validator_agent,
            decision_agent=decision_agent,
            existing_rdb=run_state.current_existing_rdb,
            config=config,
        )

        orchestrator.run_state = run_state

        return orchestrator
    
    def save_state(self, state_path: str | Path) -> None:
        """
        Save current RunState to a JSON file.
        """

        state_path = Path(state_path)
        save_json(self.run_state.to_dict(), state_path)
