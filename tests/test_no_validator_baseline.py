from unittest.mock import patch

from baselines.no_validator.model.orchestrator import NoValidatorOrchestrator
from model.core.state import TaskStep


class FakeState:
    incoming_schema = {"tables": {"incoming": {"columns": {}}}}
    existing_schema = {"tables": {}}
    constraints = {"constraints": {}}
    proposal_result = {"source_decision": "create_table"}

    def __init__(self) -> None:
        self.saved: tuple[TaskStep, dict] | None = None
        self.routing: tuple[TaskStep, TaskStep] | None = None

    def save_result(self, *, step, result, message) -> None:
        self.saved = (step, result)

    def set_routing(self, *, next_step, reason, source_step) -> None:
        self.routing = (next_step, source_step)


def test_preview_skips_validator() -> None:
    state = FakeState()
    orchestrator = object.__new__(NoValidatorOrchestrator)

    with patch(
        "baselines.no_validator.model.orchestrator.apply_proposal",
        return_value={"before": {}, "after": {}},
    ):
        orchestrator._build_preview(state)

    assert state.saved == (
        TaskStep.BUILDING_PREVIEW,
        {"before": {}, "after": {}},
    )
    assert state.routing == (
        TaskStep.AWAITING_DECISION,
        TaskStep.BUILDING_PREVIEW,
    )
