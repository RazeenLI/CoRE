"""
State: Shared Pipeline State Objects
State：共享 Pipeline 状态对象

This module defines the internal state objects used by the pipeline.

It provides two levels of state:

1. TaskState
   Represents the workspace for one incoming table task.
   Each TaskState stores the input table, the existing RDB snapshot used for
   this task, agent outputs, routing decisions, and lightweight execution trace.

2. RunState
   Represents one full pipeline run containing multiple incoming table tasks.
   Each RunState manages multiple TaskState objects and maintains the latest
   version of the existing RDB after accepted task decisions.

本模块定义 pipeline 内部使用的状态对象。

它包含两层 state：

1. TaskState
   表示一个 incoming table task 的工作区。
   每个 TaskState 保存该 task 的输入表、当时使用的 existing RDB 快照、
   agent 输出、routing 决策和轻量执行记录。

2. RunState
   表示一次完整 pipeline run，包含多个 incoming table tasks。
   每个 RunState 管理多个 TaskState，并维护 accepted decision 之后更新得到的
   最新 existing RDB。

Important:
重要说明：

- TaskState is for one incoming table only.
- RunState is for multiple incoming tables in one pipeline run.
- Agent outputs are stored as histories because some agents, especially matcher
  and evolutor, may run multiple times.
- State objects do not implement profiling, matching, evolution, validation,
  decision making, or RDB update logic.
- Pipeline controller is responsible for reading agent results and deciding routing.
- State only stores data and records lightweight execution history.

- TaskState 只对应一个 incoming table。
- RunState 对应一次包含多个 incoming tables 的 pipeline run。
- agent outputs 使用 history list 保存，因为 matcher 和 evolutor 等 agent 可能会执行多次。
- state 对象不实现 profiling、matching、evolution、validation、decision making
  或 RDB update 逻辑。
- pipeline controller 负责读取 agent result 并决定 routing。
- state 只负责保存数据和记录轻量执行历史。

Example:
示例：

    from core.state import RunState

    run_state = RunState(
        id="chinook_run_01",
        existing_rdb=existing_rdb,
    )

    task = run_state.add_task(
        task_id="step_01_customer_profile",
        incoming_table=incoming_table,
    )

    task.save_result(
        agent="profiler",
        result=profile_result,
        status="succeeded",
        message="Profiler completed.",
    )

    task.save_result(
        agent="matcher",
        result=match_result,
        status="succeeded",
        message="Matcher completed.",
    )

    if match_result["match_status"] == "high_confidence":
        task.set_routing(
            next_step="proposal",
            reason="high_confidence_match",
            source_step="matcher",
        )
    else:
        task.set_routing(
            next_step="evolutor",
            reason="low_confidence_match",
            source_step="matcher",
        )

    latest_match = task.match_result
    all_match_results = task.results["matcher"]
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
import uuid

AGENTS = {
    "profiler",
    "matcher",
    "proposal",
    "evolutor",
    "validator",
    "decision",
}

TASK_STEPS = {
    "initialized",
    "profiler",
    "matcher",
    "proposal",
    "preview",
    "evolutor",
    "validator",
    "decision",
    "controller",
}

TASK_STATUS = {
    "initialized",
    "running",
    "succeeded",
    "failed",
    "skipped",
    "waiting_review",
}

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

RUN_STEPS = {
    "initialized",
    "start_task",
    "run_task", # recent not used
    "finish_task",
    "update_existing_rdb",
    "finish_run",
}

RUN_STATUS = {
    "initialized",
    "running",
    "succeeded",
    "failed",
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
        self.current_step: str = "initialized"
        self.status: str = "initialized"

        # Input data
        self.incoming_path: str = incoming_table["path"]
        self.incoming_schema: dict[str, Any] = incoming_table["schema"]
        self.incoming_values: Any = incoming_table["sample_values"]

        self.existing_path: str = existing_rdb["path"]
        self.existing_schema: dict[str, Any] = existing_rdb["schema"]
        self.existing_profiles: dict[str, Any] = existing_rdb["profiles"]
        self.existing_values: Any = existing_rdb["sample_values"]
        self.constraints: dict[str, Any] = existing_rdb["constraints"]

        # Agent outputs as histories
        self.results: dict[str, list[dict[str, Any]]] = {
            "profiler": [],
            "matcher": [],
            "evolutor": [],
            "proposal": [],
            "preview": [],
            "validator": [],
            "decision": [],
        }

        # Current routing decision, decided by pipeline controller
        self.routing: dict[str, Any] | None = None

        # Lightweight execution history
        self.trace: list[dict[str, Any]] = []

    def save_result(
        self,
        agent: str,
        result: dict[str, Any],
        status: str,
        message: str | None = None,
    ) -> None:
        """
        Save one agent result.

        This updates:
        - current_step
        - status
        - results
        - trace

        It does NOT update routing.
        Routing is decided by the pipeline controller.
        """
        self.results[agent].append(result)
        self.current_step = agent
        self.status = status

        self._record_event(
            event="save_result",
            step=agent,
            status=status,
            message=message or f"{agent} saved result with status '{status}'.",
            data={
                "result_index": len(self.results[agent]) - 1,
            },
        )

    def set_routing(
        self,
        next_step: str,
        reason: str,
        source_step: str | None = None,
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
            status=self.status,
            message=f"Routing set to {next_step}",
            data={
                "routing": self.routing,
            },
        )

    def update_status(
        self,
        current_step: str,
        status: str,
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
            status=status,
            message=message,
            data={},
        )

    def latest_result(self, agent: str) -> dict[str, Any] | None:
        if agent not in self.AGENTS:
            raise ValueError(f"Unknown agent: {agent}")

        results = self.results[agent]
        if not results:
            return None

        return results[-1]

    @property
    def profile_result(self) -> dict[str, Any] | None:
        return self.latest_result("profiler")

    @property
    def match_result(self) -> dict[str, Any] | None:
        return self.latest_result("matcher")

    @property
    def proposal_result(self) -> dict[str, Any] | None:
        return self.latest_result("proposal")

    @property
    def evolutor_result(self) -> dict[str, Any] | None:
        return self.latest_result("evolutor")

    @property
    def validation_result(self) -> dict[str, Any] | None:
        return self.latest_result("validator")

    @property
    def final_decision(self) -> dict[str, Any] | None:
        return self.latest_result("decision")

    def _record_event(
        self,
        event: str,
        step: str,
        status: str,
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
                "status": status,
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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskState":
        state = cls(
            id=data["id"],
            incoming_table=data["incoming_table"],
            existing_rdb=data["existing_rdb"],
        )

        state.current_step = data.get("current_step", data.get("step_id", "initialized"))
        state.status = data.get("status", "initialized")

        state.results = data.get(
            "results",
            {
                "profiler": [],
                "matcher": [],
                "proposal": [],
                "evolutor": [],
                "validator": [],
                "decision": [],
            },
        )

        state.routing = data.get("routing")
        state.trace = data.get("trace", [])

        return state


class RunState:
    """
    Shared state for one full pipeline run.

    One RunState = multiple incoming-table tasks processed sequentially
    against an evolving existing RDB.
    """

    def __init__(
        self,
        existing_rdb: dict[str, Any],
        id: str | None = None,
    ) -> None:
        # Metadata
        self.id: str = id or _new_id("run")
        self.current_step: str = "initialized"
        self.status: str = "initialized"

        # RDB state
        self.initial_existing_rdb: dict[str, Any] = deepcopy(existing_rdb)
        self.current_existing_rdb: dict[str, Any] = deepcopy(existing_rdb)

        # Task states
        self.tasks: dict[str, TaskState] = {}
        self.task_order: list[str] = []
        self.current_task_id: str | None = None

        # Lightweight run-level history
        self.trace: list[dict[str, Any]] = []

    def start_task(
        self,
        incoming_table: dict[str, Any],
        task_id: str | None = None,
    ) -> TaskState:
        """
        Create a TaskState for one incoming table.

        The task receives a snapshot of the current existing RDB.
        """
        task = TaskState(
            id=task_id,
            incoming_table=incoming_table,
            existing_rdb=deepcopy(self.current_existing_rdb),
        )

        self.tasks[task.id] = task
        self.task_order.append(task.id)
        self.current_task_id = task.id

        self.current_step = "start_task"
        self.status = "running"

        self._record_event(
            event="start_task",
            message=f"Started task {task.id}.",
            data={
                "task_id": task.id,
                "incoming_path": task.incoming_path,
            },
        )

        return task
    
    def finish_task(
        self,
        task_id: str | None = None,
        status: str = "succeeded",
        message: str = "",
    ) -> None:
        finished_task_id = task_id or self.current_task_id

        if finished_task_id is None:
            raise ValueError("No task_id provided and no current task is active.")

        task_state: TaskState = self.tasks[finished_task_id]
        self.current_existing_rdb["schema"] = deepcopy(task_state.existing_schema)
        self.current_existing_rdb["profiles"] = deepcopy(task_state.existing_profiles)
        self.current_existing_rdb["sample_values"] = deepcopy(task_state.existing_values)
        self.current_existing_rdb["constraints"] = deepcopy(task_state.constraints)

        self.current_task_id = finished_task_id
        self.current_step = "finish_task"
        self.status = status

        self._record_event(
            event="finish_task",
            message=message or f"Finished task {finished_task_id}.",
            data={
                "task_id": finished_task_id,
                "task_status": self.tasks[finished_task_id].status,
                "task_current_step": self.tasks[finished_task_id].current_step,
            },
        )

    def get_task(self, task_id: str) -> TaskState:
        return self.tasks[task_id]

    @property
    def current_task(self) -> TaskState | None:
        if self.current_task_id is None:
            return None
        return self.tasks[self.current_task_id]

    def set_current_task(
        self,
        task_id: str,
    ) -> None:
        """
        1. 暂停后恢复：知道上次跑到哪个 task
        2. 并发 / 异步调度：知道当前 worker 正在处理哪个 task
        3. 人工 review 后返回某个 task 继续
        4. UI 展示：当前正在处理哪个 task
        """
        self.current_task_id = task_id
        self.current_step = "run_task"
        self.status = "running"

        self._record_event(
            event="set_current_task",
            message=f"Current task set to {task_id}.",
            data={
                "task_id": task_id,
            },
        )

    def update_existing_rdb(
        self,
        # existing_rdb: dict[str, Any],
        # source_task_id: str | None = None,
        # message: str = "",
    ) -> None:
        """
        Update the run-level current existing RDB.

        This should be called after a task final decision is accepted
        and the existing RDB has been updated.
        TODO: not load a existing rdb outside, just update the changed rdb
        """
        # self.current_existing_rdb = deepcopy(existing_rdb)
        # self.current_step = "update_existing_rdb"
        # self.status = "succeeded"

        # self._record_event(
        #     event="update_existing_rdb",
        #     message=message or "Current existing RDB updated.",
        #     data={
        #         "source_task_id": source_task_id,
        #         "existing_path": self.current_existing_rdb.get("path"),
        #     },
        # )
        pass

    def update_status(
        self,
        current_step: str,
        status: str,
        message: str = "",
    ) -> None:
        self.current_step = current_step
        self.status = status

        self._record_event(
            event="update_status",
            message=message,
            data={
                "current_step": current_step,
                "status": status,
            },
        )

    def _record_event(
        self,
        event: str,
        message: str,
        data: dict[str, Any],
    ) -> None:
        self.trace.append(
            {
                "event": event,
                "step": self.current_step,
                "status": self.status,
                "message": message,
                "data": data,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "current_step": self.current_step,
            "status": self.status,
            "initial_existing_rdb": self.initial_existing_rdb,
            "current_existing_rdb": self.current_existing_rdb,
            "task_order": self.task_order,
            "current_task_id": self.current_task_id,
            "tasks": {
                task_id: task.to_dict()
                for task_id, task in self.tasks.items()
            },
            "trace": self.trace,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        state = cls(
            id=data["id"],
            existing_rdb=data["initial_existing_rdb"],
        )

        state.current_step = data.get("current_step", "initialized")
        state.status = data.get("status", "initialized")

        state.initial_existing_rdb = data["initial_existing_rdb"]
        state.current_existing_rdb = data["current_existing_rdb"]

        state.task_order = data.get("task_order", [])
        state.current_task_id = data.get("current_task_id")

        state.tasks = {
            task_id: TaskState.from_dict(task_data)
            for task_id, task_data in data.get("tasks", {}).items()
        }

        state.trace = data.get("trace", [])

        return state