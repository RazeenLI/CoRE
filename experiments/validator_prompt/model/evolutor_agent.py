from __future__ import annotations

from typing import Any

from model.agents.evolutor_agent import EvolutorAgent
from experiments.validator_prompt.model.prompts import conservative_evolutor_prompt


class ValidatorPromptEvolutorAgent(EvolutorAgent):
    """Evolutor that honors a decision lock from the validator gate."""

    def __init__(self, llm_client: Any) -> None:
        super().__init__(llm_client, prompt_builder=conservative_evolutor_prompt)

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        feedback = kwargs.get("validation_feedback") or {}
        result = super().__call__(**kwargs)
        if feedback.get("preserve_decision"):
            result["decision"]["decision_type"] = feedback["locked_decision"]
            result["decision"]["target_table"] = feedback["locked_target_table"]
        return result
