from __future__ import annotations

from typing import Any

from model.core.orchestrator import Orchestrator
from model.core.state import TaskState, TaskStep


class ValidatorPromptOrchestrator(Orchestrator):
    def _get_validation_feedback(
        self, task_state: TaskState
    ) -> dict[str, Any] | None:
        if task_state.routing.get("source_step") != TaskStep.VALIDATING:
            return None
        result = task_state.validation_result
        if result is None:
            return None
        return {
            "issues": result.get("issues", []),
            "summary": result.get("summary", ""),
            "preserve_decision": result.get("preserve_decision", False),
            "locked_decision": result.get("locked_decision", ""),
            "locked_target_table": result.get("locked_target_table", ""),
            "decision_change_allowed": result.get("decision_change_allowed", False),
            "recommended_decision": result.get("recommended_decision"),
            "decision_evidence": result.get("decision_evidence", []),
        }
