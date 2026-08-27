from __future__ import annotations

from typing import Any

from model.agents.validator_agent import ValidatorAgent

from experiments.validator_prompt.model.prompts import validator_prompt


class ValidatorPromptAgent(ValidatorAgent):
    """Standard ValidatorAgent using the consistency-focused prompt."""

    def __init__(self, llm_client: Any | None = None) -> None:
        super().__init__(
            llm_client=llm_client,
            prompt_builder=validator_prompt,
        )
