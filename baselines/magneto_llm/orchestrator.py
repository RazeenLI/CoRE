from pathlib import Path
from typing import Any

from model.agents.evolutor_agent import EvolutorAgent
from model.core.orchestrator import Orchestrator as StandardOrchestrator
from model.core.state import TaskState, TaskStep
from model.proposal.applier import apply_proposal


class Orchestrator(StandardOrchestrator):
    """Use Magneto evidence with the Standard Evolutor, without validation."""

    def __init__(self, *, matcher: Any, evolutor: EvolutorAgent,
                 save_path: str | Path, config: dict[str, Any]) -> None:
        super().__init__(
            profiler_agent=None,
            selector_agent=matcher,
            evolutor_agent=evolutor,
            validator_agent=None,
            save_path=save_path,
            config=config,
        )

    def _create_state(self, task_id, existing_rdb, incoming_table) -> TaskState:
        state = TaskState(id=task_id, existing_rdb=existing_rdb,
                          incoming_table=incoming_table)
        state.set_routing(TaskStep.MATCHING, "Start Magneto matching.",
                          TaskStep.INITIALIZED)
        return state

    def _run_selector(self, state: TaskState) -> None:
        raw = self.selector(
            incoming_schema=state.incoming_schema,
            incoming_values=state.incoming_values,
            existing_schema=state.existing_schema,
            existing_values=state.existing_values,
            existing_profiles=state.existing_profiles,
        )
        table_matches = raw.get("table_matches", [])
        selected = table_matches[:5]
        selection = {
            **raw,
            "selector": "magneto",
            "selected_tables": [item["target_table"] for item in selected],
            "table_matches": selected,
            "column_candidates": _column_candidates(selected),
        }
        state.save_result(TaskStep.MATCHING, selection,
                          "Magneto candidate evidence completed.")
        state.set_routing(TaskStep.EVOLVING, "Magneto evidence prepared.",
                          TaskStep.MATCHING)

    def _run_evolutor(self, state: TaskState) -> None:
        result = self.evolutor(
            incoming_schema=state.incoming_schema,
            incoming_values=state.incoming_values,
            incoming_profile=None,
            existing_schema=state.existing_schema,
            existing_values=state.existing_values,
            existing_profiles=None,
            existing_constraints=state.constraints,
            selection_result=state.match_result,
            validation_feedback=None,
        )
        state.save_result(TaskStep.EVOLVING, result,
                          "LLM evolution adapter completed.")
        state.set_routing(TaskStep.BUILDING_PROPOSAL,
                          "LLM evolution adapter completed.", TaskStep.EVOLVING)

    def _build_preview(self, state: TaskState) -> None:
        preview = apply_proposal(
            incoming_schema=state.incoming_schema,
            existing_schema=state.existing_schema,
            existing_constraints=state.constraints,
            proposal=state.proposal_result,
        )
        state.save_result(TaskStep.BUILDING_PREVIEW, preview,
                          "Proposal preview completed.")
        state.set_routing(TaskStep.AWAITING_DECISION,
                          "Skip Validator for adapter isolation.",
                          TaskStep.BUILDING_PREVIEW)


def _column_candidates(table_matches: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for table_match in table_matches:
        table_name = table_match["target_table"]
        for source, candidates in table_match.get("column_matches", {}).items():
            for candidate in candidates[:1]:
                result.setdefault(source, []).append({
                    "target_table": table_name,
                    "target_column": candidate["target_column"],
                    "retrieval_score": candidate.get("confidence", 0.0),
                })
    return result
