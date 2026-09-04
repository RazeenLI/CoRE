"""
State: Shared Pipeline State Objects
State：共享 Pipeline 状态对象

This module defines the internal state objects used by the pipeline.

TaskState
   Represents the workspace for one incoming table task.
   Each TaskState stores the input table, the existing RDB snapshot used for
   this task, agent outputs, routing decisions, and lightweight execution trace.

本模块定义 pipeline 内部使用的状态对象。

TaskState
   表示一个 incoming table task 的工作区。
   每个 TaskState 保存该 task 的输入表、当时使用的 existing RDB 快照、
   agent 输出、routing 决策和轻量执行记录。

Important:
重要说明：

- TaskState is for one incoming table only.
- Agent outputs are stored as histories because some agents, especially matcher
  and evolutor, may run multiple times.
- State objects do not implement profiling, matching, evolution, validation,
  decision making, or RDB update logic.
- Pipeline controller is responsible for reading agent results and deciding routing.
- State only stores data and records lightweight execution history.

- TaskState 只对应一个 incoming table。
- agent outputs 使用 history list 保存，因为 matcher 和 evolutor 等 agent 可能会执行多次。
- state 对象不实现 profiling、matching、evolution、validation、decision making
  或 RDB update 逻辑。
- pipeline controller 负责读取 agent result 并决定 routing。
- state 只负责保存数据和记录轻量执行历史。

"""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Any
import uuid
from enum import StrEnum

class Agents(StrEnum):
    PROFILER = "profiler"
    MATCHER = "matcher"
    EVOLUTOR = "evolutor"
    VALIDATOR = "validator"

# TASK_STEPS = {
#     "initialized",
#     "profiler",
#     "matcher",
#     "proposal",
#     "preview",
#     "evolutor",
#     "validator",
#     "decision",
#     "apply",
# }

class TaskStep(StrEnum):
    INITIALIZED = "initialized"
    PROFILING = "profiling"
    MATCHING = "matching"
    EVOLVING = "evolving"
    BUILDING_PROPOSAL = "building_proposal"
    BUILDING_PREVIEW = "building_preview"
    VALIDATING = "validating"
    AWAITING_DECISION = "awaiting_decision"
    APPLYING_DECISION = "applying_decision"
    COMPLETED = "completed"
    ERROR = "error"

# TASK_STATUS = {
#     "initialized",
#     "running",
#     "succeeded",
#     "failed",
#     "skipped",
#     "waiting_review",
# }

class TaskStatus(StrEnum):
    # INITIALIZED = "initialized"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    # SKIPPED = "skipped"
    # WAITING_REVIEW = "waiting_review"

ROUTING_REASONS = {
    "start_task",
    "profile_completed",
    "high_confidence_match",
    "low_confidence_match",
    "partial_match",
    "schema_evolved_rematch_required",
    "proposal_generated",
    "validation_passed",
    "validation_failed",
    "decision_accepted",
    "decision_rejected",
    "manual_review_required",
}

def _new_id(state: str = "task") -> str:
    return f"{state}_{uuid.uuid4().hex[:8]}"


class TaskState:
    """
    Shared state for one incoming-table task.
    """

    def __init__(
        self,
        incoming_table: dict[str, Any],
        existing_rdb: dict[str, Any],
        id: str | None = None,
    ) -> None:
        # Metadata
        self.id: str = id or _new_id()
        self.current_step: TaskStep = TaskStep.INITIALIZED
        self.status: TaskStatus = TaskStatus.RUNNING

        # Input data
        self.incoming_path: str = incoming_table["path"]
        self.incoming_schema: dict[str, Any] = incoming_table["schema"]
        self.incoming_values: Any = incoming_table["sample_values"]

        self.existing_path: str = existing_rdb["path"]
        self.existing_schema: dict[str, Any] = existing_rdb["schema"]
        self.existing_profiles: dict[str, Any] = existing_rdb["profiles"]
        self.existing_values: Any = existing_rdb["sample_values"]
        self.constraints: dict[str, Any] = existing_rdb["constraints"]

        # Step outputs as histories
        self.results: dict[TaskStep, list[dict[str, Any]]] = {
            TaskStep.PROFILING: [],
            TaskStep.MATCHING: [],
            TaskStep.EVOLVING: [],
            TaskStep.BUILDING_PROPOSAL: [],
            TaskStep.BUILDING_PREVIEW: [],
            TaskStep.VALIDATING: [],
            TaskStep.AWAITING_DECISION: [],
        }

        # Current routing decision, decided by pipeline controller
        self.routing: dict[str, Any] | None = None

        # Lightweight execution history
        self.trace: list[dict[str, Any]] = []

        self.timing: dict[str, Any] = {
            "end_to_end_seconds": 0.0,
            "steps": {
                step.value: {
                    "total_seconds": 0.0,
                    "call_count": 0,
                    "runs": [],
                }
                for step in (
                    TaskStep.PROFILING,
                    TaskStep.MATCHING,
                    TaskStep.EVOLVING,
                    TaskStep.BUILDING_PROPOSAL,
                    TaskStep.BUILDING_PREVIEW,
                    TaskStep.VALIDATING,
                    TaskStep.AWAITING_DECISION,
                    TaskStep.APPLYING_DECISION,
                )
            },
        }
        self.llm_usage: dict[str, Any] = {}

    @contextmanager
    def measure_step(self, step: TaskStep):
        started_at = perf_counter()
        try:
            yield
        finally:
            elapsed = perf_counter() - started_at
            key = step.value
            entry = self.timing["steps"].get(key)
            if entry is not None:
                entry["total_seconds"] += elapsed
                entry["call_count"] += 1
                entry["runs"].append(elapsed)

    @contextmanager
    def measure_end_to_end(self):
        started_at = perf_counter()
        try:
            yield
        finally:
            self.timing["end_to_end_seconds"] = perf_counter() - started_at

    def start_timer(self) -> float:
        return perf_counter()

    def finish_end_to_end(self, started_at: float) -> None:
        self.timing["end_to_end_seconds"] = perf_counter() - started_at

    def save_result(
        self,
        step: TaskStep,
        result: dict[str, Any],
        # status: TaskStatus,
        message: str | None = None,
    ) -> None:
        """
        Save one step result.

        This updates:
        - current_step
        - results
        - trace

        It does NOT update routing.
        Routing is decided by the pipeline controller.
        """
        self.results[step].append(result)
        self.current_step = step
        # self.status = status

        self._record_event(
            event="save_result",
            step=step,
            # status=self.status,
            message=message or f"{step} saved result.",
            data={
                "result_index": len(self.results[step]) - 1,
            },
        )

    def set_routing(
        self,
        next_step: TaskStep,
        reason: str,
        source_step: TaskStep | None = None,
    ) -> None:
        """
        Save current routing decision.

        This does NOT change current_step or status.
        """
        self.routing = {
            "next_step": next_step,
            "reason": reason,
            "source_step": source_step or self.current_step,
        }

        self._record_event(
            event="set_routing",
            step=self.current_step,
            # status=self.status,
            message=f"Routing set to {next_step}",
            data={
                "routing": self.routing,
            },
        )

    def update_status(
        self,
        current_step: TaskStep,
        status: TaskStatus,
        message: str = "",
    ) -> None:
        """
        Update pipeline status without saving an agent result.

        Use this only for controller-level transitions.
        """
        self.current_step = current_step
        self.status = status

        self._record_event(
            event="update_status",
            step=current_step,
            # status=status,
            message=message,
            data={
                "status": status,
            },
        )

    def latest_result(
        self,
        step: TaskStep,
    ) -> dict[str, Any] | None:
        results = self.results.get(step, [])
        return results[-1] if results else None

    @property
    def profile_result(self) -> dict[str, Any] | None:
        return self.latest_result(TaskStep.PROFILING)

    @property
    def match_result(self) -> dict[str, Any] | None:
        return self.latest_result(TaskStep.MATCHING)

    @property
    def proposal_result(self) -> dict[str, Any] | None:
        return self.latest_result(TaskStep.BUILDING_PROPOSAL)

    @property
    def preview_result(self) -> dict[str, Any] | None:
        return self.latest_result(TaskStep.BUILDING_PREVIEW)

    @property
    def evolutor_result(self) -> dict[str, Any] | None:
        return self.latest_result(TaskStep.EVOLVING)

    @property
    def validation_result(self) -> dict[str, Any] | None:
        return self.latest_result(TaskStep.VALIDATING)

    @property
    def final_decision(self) -> dict[str, Any] | None:
        return self.latest_result(TaskStep.AWAITING_DECISION)

    @property
    def existing_rdb(self) -> dict[str, Any]:
        return {
            "path": self.existing_path,
            "schema": self.existing_schema,
            "profiles": self.existing_profiles,
            "constraints": self.constraints,
            "sample_values": self.existing_values,
        }

    @property
    def incoming_table(self) -> dict[str, Any]:
        return {
            "path": self.incoming_path,
            "schema": self.incoming_schema,
            "sample_values": self.incoming_values,
        }
    
    def _record_event(
        self,
        event: str,
        step: TaskStep,
        # status: str,
        message: str,
        data: dict[str, Any],
    ) -> None:
        """
        Internal trace writer.

        External code should not call this directly.
        """
        self.trace.append(
            {
                "event": event,
                "step": step,
                # "status": status,
                "message": message,
                "data": data,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "current_step": self.current_step,
            "status": self.status,
            "incoming_table": {
                "path": self.incoming_path,
                "schema": self.incoming_schema,
                "sample_values": self.incoming_values,
            },
            "existing_rdb": {
                "path": self.existing_path,
                "schema": self.existing_schema,
                "profiles": self.existing_profiles,
                "constraints": self.constraints,
                "sample_values": self.existing_values,
            },
            "results": self.results,
            "routing": self.routing,
            "trace": self.trace,
            "timing": self.timing,
            "llm_usage": self.llm_usage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskState":
        state = cls(
            id=data["id"],
            incoming_table=data["incoming_table"],
            existing_rdb=data["existing_rdb"],
        )

        state.current_step = TaskStep(
            data.get("current_step", TaskStep.INITIALIZED)
        )

        state.status = TaskStatus(
            data.get("status", TaskStatus.RUNNING)
        )

        # Restore result keys from JSON strings to TaskStep
        saved_results = data.get("results", {})
        state.results.update(
            {
                TaskStep(step): results
                for step, results in saved_results.items()
            }
        )

        # Restore routing step values from JSON strings to TaskStep
        routing = data.get("routing")
        if routing is not None:
            state.routing = {
                **routing,
                "next_step": TaskStep(routing["next_step"]),
                "source_step": (
                    TaskStep(routing["source_step"])
                    if routing.get("source_step") is not None
                    else None
                ),
            }
        else:
            state.routing = None
        state.trace = data.get("trace", [])
        state.timing = data.get(
            "timing",
            state.timing,
        )
        state.llm_usage = data.get("llm_usage", {})

        return state
