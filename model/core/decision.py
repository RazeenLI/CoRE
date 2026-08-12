from typing import Any
from pathlib import Path

from model.visualization.task_state import save_task_state_visualization


def build_decision(is_auto: bool = False):
    if is_auto:
        return auto_approve_decision
    return terminal_decision


def terminal_decision(
    task_id: str,
    incoming_schema: dict[str, Any],
    incoming_values: Any,
    existing_schema: dict[str, Any],
    constraints: dict[str, Any],
    existing_values: Any,
    existing_profiles: dict[str, Any],
    results: dict[str, list[dict[str, Any]]],
    trace: list[dict[str, Any]],
    save_path: str | Path,
) -> dict[str, Any]:
    save_task_state_visualization(
        task_id=task_id,
        incoming_schema=incoming_schema,
        incoming_values=incoming_values,
        existing_schema=existing_schema,
        constraints=constraints,
        existing_values=existing_values,
        existing_profiles=existing_profiles,
        results=results,
        trace=trace,
        save_path=save_path,
    )

    while True:
        answer = input("Approve? [y/n]: ").strip().lower()

        if answer in {"y", "yes"}:
            return {
                "approved": True,
                "summary": "Human approved the decision.",
            }

        if answer in {"n", "no"}:
            return {
                "approved": False,
                "summary": "Human rejected the decision.",
            }

        print("Invalid input. Please enter y or n.")


def auto_approve_decision(
    task_id: str,
    incoming_schema: dict[str, Any],
    incoming_values: Any,
    existing_schema: dict[str, Any],
    constraints: dict[str, Any],
    existing_values: Any,
    existing_profiles: dict[str, Any],
    results: dict[str, list[dict[str, Any]]],
    trace: list[dict[str, Any]],
    save_path: str | Path,
) -> dict[str, Any]:
    # save_task_state_visualization(
    #     task_id=task_id,
    #     incoming_schema=incoming_schema,
    #     incoming_values=incoming_values,
    #     existing_schema=existing_schema,
    #     constraints=constraints,
    #     existing_values=existing_values,
    #     existing_profiles=existing_profiles,
    #     results=results,
    #     trace=trace,
    #     save_path=save_path,
    # )
    return {
        "approved": True,
        "summary": "Auto-approved.",
    }