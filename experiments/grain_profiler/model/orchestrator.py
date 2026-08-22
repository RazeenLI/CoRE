from __future__ import annotations

from copy import deepcopy
from typing import Any

from model.core.orchestrator import Orchestrator as StandardOrchestrator

from experiments.grain_profiler.model.profile_compression import compact_profiles


class GrainProfilerOrchestrator(StandardOrchestrator):
    """Standard workflow with compact profiles on both sides of the comparison."""

    def _create_state(
        self,
        task_id: str,
        existing_rdb: dict[str, Any],
        incoming_table: dict[str, Any],
    ):
        compact_rdb = deepcopy(existing_rdb)
        compact_rdb["profiles"] = compact_profiles(existing_rdb.get("profiles"))
        return super()._create_state(task_id, compact_rdb, incoming_table)
