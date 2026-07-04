from typing import Any
from pathlib import Path
from model.utils.io import terminal_message, load_json, save_json
from model.core.state import RunState, TaskState

from model.agents.base_agent import BaseAgent
from model.agents.profiler_agent import ProfilerAgent
from model.agents.matcher_agent import MatcherAgent


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
        evolution_agent: BaseAgent,
        validator_agent: BaseAgent,
        decision_agent: BaseAgent,
        existing_rdb,
        config,
    ) -> None:
        self.profiler = profiler_agent
        self.matcher = matcher_agent
        self.evolution = evolution_agent
        self.validator = validator_agent
        self.decision = decision_agent

        self.threshold = config.get("high_confidence_threshold", 0.8)
        self.config = config

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

            elif next_step == "mapping":
                self._build_mapping_proposal(task_state)

            elif next_step == "evolution":
                self._run_evolutor(task_state)

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
        # TODO: Profiler for incomming table profiler
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
        # TODO: Matcher for matching incoming table with tables in existing rdb

        # TODO: Deside routing based on the confidence from Matcher
        # can return routing result
        # task_state.set_routing(
        #     next_step="mapping",
        #     reason="just test",
        #     source_step=None,
        # )
        matching_result = self.matcher(
            incoming_schema=task_state.incoming_schema,
            incoming_values=task_state.incoming_values,
            incoming_profile=task_state.results["profiler"][-1],
            existing_schema=task_state.existing_schema,
            existing_values=task_state.existing_values,
            existing_profiles=task_state.existing_profiles,
        )
        task_state.save_result(
            agent="matcher",
            result=matching_result,
            status="success",
            message="Matcher completed successfully.",
        )

        confidence = matching_result["table_matches"][0].get("confidence", 0.0)

        if confidence >= self.threshold:
            task_state.set_routing(
                next_step="mapping",
                reason=f"Matcher confidence {confidence} >= threshold {self.threshold}.",
                source_step="matcher",
            )
        else:
            task_state.set_routing(
                next_step="evolution",
                reason=f"Matcher confidence {confidence} < threshold {self.threshold}.",
                source_step="matcher",
            )
        pass

    def _build_mapping_proposal(self, task_state: TaskState):
        # TODO: Build mapping proposal 
        # 1. only mapping
        # 2. if evolution happens
        # terminal_message("info", f"Building mapping proposal for task '{task_state.task_id}'.", "\t")
        task_state.set_routing(
            next_step="finish_task",
            reason=f"Example reason.",
            source_step="mapping",
        )
        pass

    def _run_evolutor(self, task_state: TaskState):
        # TODO: Evolutor for evolute tables in existing rdb for incoming table

        # TODO: Deside routing based on the confidence from Evolutor (Currently mush return to Matcher) only allow 5 times in loop
        task_state.set_routing(
            next_step="finish_task",
            reason=f"Example reason.",
            source_step="evolution",
        )
        pass
    
    def _run_validator(self, task_state: TaskState):
        # TODO: Validator recent result
        # Deside routing 
        # 1. Profiler Problem: back to Profiler
        # 2. Matcher Problem
        # 3. Evolutor Problem
        task_state.set_routing(
            next_step="finish_task",
            reason=f"Example reason.",
            source_step="validator",
        )
        pass

    def _finalize_decision(self, task_state: TaskState):
        # TODO: Human in the loop
        task_state.set_routing(
            next_step="finish_task",
            reason=f"Example reason.",
            source_step="finial_decision",
        )
        pass

    def _apply_final_decision(self, task_state: TaskState):
        # TODO: Auto apply after dedesided
        pass
    
    @classmethod
    def from_state_json(
        cls,
        state_path: str | Path,
        profiler_agent: Any,
        matcher_agent: Any,
        evolution_agent: Any,
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
            evolution_agent=evolution_agent,
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
