from pathlib import Path
from typing import Any

from model.agents.evolutor_agent import EvolutorAgent
from model.core.orchestrator import Orchestrator as StandardOrchestrator
from model.core.state import TaskState, TaskStep
from model.proposal.applier import apply_proposal


class LLMAdapterOrchestrator(StandardOrchestrator):
    """Use native matcher evidence with the unchanged Standard Evolutor.

    Standard's Profiler, Selector, and Validator are deliberately excluded.
    Every adapted matcher receives the same evidence budget and exactly one
    shared LLM decision tail.
    """

    def __init__(
        self,
        *,
        matcher: Any,
        matcher_name: str,
        evolutor: EvolutorAgent,
        save_path: str | Path,
        config: dict[str, Any],
    ) -> None:
        super().__init__(
            profiler_agent=None,
            selector_agent=matcher,
            evolutor_agent=evolutor,
            validator_agent=None,
            save_path=save_path,
            config=config,
        )
        self.matcher_name = matcher_name
        self.table_top_k = int(config.get("table_top_k", 5))
        self.column_top_k_per_table = int(
            config.get("column_top_k_per_table", 1)
        )

    def _create_state(self, task_id, existing_rdb, incoming_table) -> TaskState:
        state = TaskState(
            id=task_id,
            existing_rdb=existing_rdb,
            incoming_table=incoming_table,
        )
        state.set_routing(
            TaskStep.MATCHING,
            f"Start {self.matcher_name} matching.",
            TaskStep.INITIALIZED,
        )
        return state

    def _run_selector(self, state: TaskState) -> None:
        raw = self.selector(
            incoming_schema=state.incoming_schema,
            incoming_values=state.incoming_values,
            existing_schema=state.existing_schema,
            existing_values=state.existing_values,
            existing_profiles=state.existing_profiles,
        )
        selection = normalize_matcher_evidence(
            raw,
            matcher_name=self.matcher_name,
            table_top_k=self.table_top_k,
            column_top_k_per_table=self.column_top_k_per_table,
        )
        state.save_result(
            TaskStep.MATCHING,
            selection,
            f"{self.matcher_name} candidate evidence completed.",
        )
        state.set_routing(
            TaskStep.EVOLVING,
            f"{self.matcher_name} evidence prepared.",
            TaskStep.MATCHING,
        )

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
        state.save_result(
            TaskStep.EVOLVING,
            result,
            "Shared LLM decision adapter completed.",
        )
        state.set_routing(
            TaskStep.BUILDING_PROPOSAL,
            "Shared LLM decision adapter completed.",
            TaskStep.EVOLVING,
        )

    def _build_preview(self, state: TaskState) -> None:
        preview = apply_proposal(
            incoming_schema=state.incoming_schema,
            existing_schema=state.existing_schema,
            existing_constraints=state.constraints,
            proposal=state.proposal_result,
        )
        state.save_result(
            TaskStep.BUILDING_PREVIEW,
            preview,
            "Proposal preview completed.",
        )
        state.set_routing(
            TaskStep.AWAITING_DECISION,
            "Skip Validator for LLM-adapter isolation.",
            TaskStep.BUILDING_PREVIEW,
        )


def normalize_matcher_evidence(
    raw: dict[str, Any],
    *,
    matcher_name: str,
    table_top_k: int,
    column_top_k_per_table: int,
) -> dict[str, Any]:
    """Apply one common evidence budget without altering matcher scores."""

    table_matches = list(raw.get("table_matches", []))[:table_top_k]
    return {
        **raw,
        "selector": matcher_name,
        "selected_tables": [item["target_table"] for item in table_matches],
        "table_matches": table_matches,
        "column_candidates": _column_candidates(
            table_matches,
            per_table_limit=column_top_k_per_table,
        ),
    }


def _column_candidates(
    table_matches: list[dict[str, Any]],
    *,
    per_table_limit: int,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for table_match in table_matches:
        table_name = table_match["target_table"]
        for source, candidates in table_match.get("column_matches", {}).items():
            for candidate in candidates[:per_table_limit]:
                result.setdefault(source, []).append({
                    "target_table": table_name,
                    "target_column": candidate["target_column"],
                    "retrieval_score": candidate.get("confidence", 0.0),
                })
    return result
