from __future__ import annotations

from typing import Any

from model.agents.base_agent import BaseAgent
from model.core.prompts import PromptBuilder, validator_prompt
from model.utils.io import terminal_message


class ValidatorAgent(BaseAgent):
    """
    Validate whether the generated AFTER partial RDB is reasonable.

    This validator is LLM-based.

    Input:
    - proposal
    - before partial RDB
    - after partial RDB

    Output:
    {
        "route": "decision" | "matcher" | "evolutor",
        "score": float,
        "issues": list[str],
        "summary": str
    }
    """

    def __init__(
        self,
        llm_client: Any | None = None,
        prompt_builder: PromptBuilder = validator_prompt,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder

    def __call__(
        self,
        proposal: dict[str, Any],
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> dict[str, Any]:
        source_decision = proposal["source_decision"]

        terminal_message("info", f"Validating generated partial RDB from decision: {source_decision}.", "\t")

        llm_input = build_llm_input(
            proposal=proposal,
            before=before,
            after=after,
        )

        prompt = self.prompt_builder(llm_input)
        llm_output = self._generate_json(prompt)

        result = apply_llm_output(
            llm_output=llm_output,
            source_decision=source_decision,
        )

        terminal_message("success", f"ValidatorAgent completed with route={result['route']} score={result['score']}.","\t",)

        return result


def build_llm_input(
    proposal: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    return {
        "proposal": proposal,
        "before_partial_rdb": before,
        "after_partial_rdb": after,
    }


def apply_llm_output(
    llm_output: dict[str, Any],
    source_decision: str,
) -> dict[str, Any]:
    return {
        "route": normalize_route(
            raw_route=llm_output.get("route"),
            source_decision=source_decision,
        ),
        "score": normalize_score(llm_output.get("score")),
        "issues": normalize_issues(llm_output.get("issues")),
        "summary": normalize_summary(llm_output.get("summary")),
    }


def normalize_route(
    raw_route: Any,
    source_decision: str,
) -> str:
    allowed_routes = allowed_routes_from_source_decision(source_decision)

    if isinstance(raw_route, str) and raw_route in allowed_routes:
        return raw_route

    return fallback_route(source_decision)


def allowed_routes_from_source_decision(
    source_decision: str,
) -> list[str]:
    if source_decision == "insert_table":
        return ["decision", "matcher"]

    return ["decision", "evolutor"]


def fallback_route(
    source_decision: str,
) -> str:
    if source_decision == "insert_table":
        return "matcher"

    return "evolutor"


def normalize_score(
    raw_score: Any,
) -> float:
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return 0.0

    return min(max(score, 0.0), 1.0)


def normalize_issues(
    raw_issues: Any,
    max_issues: int = 8,
) -> list[str]:
    if not isinstance(raw_issues, list):
        return []

    issues: list[str] = []

    for issue in raw_issues:
        if not isinstance(issue, str):
            continue

        issue = issue.strip()

        if issue:
            issues.append(issue)

    return issues[:max_issues]


def normalize_summary(
    raw_summary: Any,
) -> str:
    if not isinstance(raw_summary, str):
        return ""

    return raw_summary.strip()