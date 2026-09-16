from pathlib import Path
from typing import Any

from baselines.llm_adapter.orchestrator import LLMAdapterOrchestrator
from model.agents.evolutor_agent import EvolutorAgent


class Orchestrator(LLMAdapterOrchestrator):
    """Compatibility wrapper for the shared matcher-to-LLM adapter."""

    def __init__(
        self,
        *,
        matcher: Any,
        evolutor: EvolutorAgent,
        save_path: str | Path,
        config: dict[str, Any],
    ) -> None:
        super().__init__(
            matcher=matcher,
            matcher_name="magneto",
            evolutor=evolutor,
            save_path=save_path,
            config=config,
        )
