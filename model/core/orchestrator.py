from core.state import RunState


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
        profiler_agent,
        matcher_agent,
        evolution_agent,
        validator_agent,
        decision_agent,
        existing_rdb,
        config,
    ):
        self.profiler = profiler_agent
        self.matcher = matcher_agent
        self.evolution = evolution_agent
        self.validator = validator_agent
        self.decision = decision_agent
        self.config = config

        self.run_state = RunState(existing_rdb=existing_rdb)

    def run_task(self, task, incoming_table):
        task_state = self.run_state.start_task(incoming_table, task_id=task)

        self._run_profiler(task_state)

        self._run_matcher(task_state)

        if task_state.routing["next_step"] == "mapping":
            self._build_mapping_proposal(task_state)
        elif task_state.routing["next_step"] == "evolution":
            self._run_evolutor(task_state)

        self._run_validator(task_state)

        self._finalize_decision(task_state)
        self._apply_final_decision(task_state)

        self.run_state.update_existing_rdb()

        self.run_state.finish_task(task_id=task)
        
    
    def _run_profiler(self, task_state):
        # TODO: Profiler for incomming table profiler
        pass

    def _run_matcher(self, task_state):
        # TODO: Matcher for matching incoming table with tables in existing rdb

        # TODO: Deside routing based on the confidence from Matcher
        # can return routing result
        pass

    def _build_mapping_proposal(self, task_state):
        # TODO: Build mapping proposal 
        # 1. only mapping
        # 2. if evolution happens
        pass

    def _run_evolutor(self, task_state):
        # TODO: Evolutor for evolute tables in existing rdb for incoming table

        # TODO: Deside routing based on the confidence from Evolutor (Currently mush return to Matcher) only allow 5 times in loop
        pass
    
    def _run_validator(self, task_state):
        # TODO: Validator recent result
        # Deside routing 
        # 1. Profiler Problem: back to Profiler
        # 2. Matcher Problem
        # 3. Evolutor Problem
        pass

    def _finalize_decision(self, task_state):
        # TODO: Human in the loop
        pass

    def _apply_final_decision(self, task_state):
        # TODO: Auto apply after dedesided
        pass
    
