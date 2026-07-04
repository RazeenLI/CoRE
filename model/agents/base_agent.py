from __future__ import annotations

import json

from typing import Any

from model.utils.io import terminal_message
from model.core.prompts import PromptBuilder


class BaseAgent:
    """
    Base class for agents that may call an LLM.

    Responsibilities:
    - store llm_client
    - store use_llm flag
    - enforce __call__ interface
    - provide a shared generate_json helper

    Expected llm_client interface:
        llm_client.generate_json(prompt: str) -> dict[str, Any]
    """

    def __init__(
        self,
        llm_client: Any | None = None,
        prompt_builder: PromptBuilder | None = None,
        # use_llm: bool = True,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        # self.use_llm = use_llm

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Every agent must be callable.

        Example:
            result = agent(...)
        """
        raise NotImplementedError

    def _generate_json(self, prompt: str) -> dict[str, Any]:
        """
        Expected llm_client interface:

            llm_client.generate_json(prompt: str) -> dict[str, Any]

        If your client returns a JSON string instead of a dict, this method
        also accepts that and parses it.
        """
        return self.llm_client.generate_json(prompt)
        # result = self.llm_client.generate_json(prompt)

        # if isinstance(result, dict):
        #     return result

        # if isinstance(result, str):
        #     return json.loads(result)

        # raise TypeError("llm_client.generate_json(prompt) must return dict or JSON str.")

    def _extract_single_table(
        self,
        incoming_schema: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        tables = incoming_schema.get("tables", {})

        if not tables:
            raise ValueError("incoming_schema must contain at least one table.")

        if len(tables) > 1:
            raise ValueError(
                "ProfilerAgent currently expects one incoming table per task."
            )

        table_name = next(iter(tables))
        table_schema = tables[table_name]

        return table_name, table_schema
    