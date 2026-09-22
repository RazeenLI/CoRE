from __future__ import annotations

from typing import Any

from model.agents.base_agent import BaseAgent
from model.core.prompts import PromptBuilder, validator_prompt
from model.utils.io import terminal_message


class ValidatorAgent(BaseAgent):
    """
    Validate whether the generated AFTER partial RDB is reasonable.

    This validator applies deterministic schema checks before LLM judgment.

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
        existing_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source_decision = proposal["source_decision"]

        terminal_message("info", f"Validating generated partial RDB from decision: {source_decision}.", "\t")

        rule_checks, rule_issues = run_rule_checks(
            before=before,
            after=after,
            existing_schema=existing_schema,
        )
        if rule_issues:
            result = {
                "route": fallback_route(source_decision),
                "score": 0.0,
                "rule_checks": rule_checks,
                "llm_judgment": None,
                "issues": rule_issues,
                "summary": "Deterministic schema validation failed.",
            }
            terminal_message(
                "error",
                f"ValidatorAgent rejected preview with {len(rule_issues)} hard-rule issue(s).",
                "\t",
            )
            return result

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
        result["rule_checks"] = rule_checks
        result["llm_judgment"] = {
            "route": result["route"],
            "score": result["score"],
            "issues": result["issues"],
            "summary": result["summary"],
        }

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


def run_rule_checks(
    after: dict[str, Any],
    existing_schema: dict[str, Any] | None = None,
    before: dict[str, Any] | None = None,
) -> tuple[dict[str, bool], list[str]]:
    schema_issues = validate_after_schema(after)
    constraint_issues = validate_after_constraints(
        after=after,
        existing_schema=existing_schema,
    )
    if before is not None:
        existing_constraint_issues = set(validate_after_constraints(
            after=before,
            existing_schema=existing_schema,
        ))
        constraint_issues = [
            issue
            for issue in constraint_issues
            if issue not in existing_constraint_issues
        ]
    checks = {
        "after_schema_well_formed": not schema_issues,
        "after_constraints_reference_valid": not constraint_issues,
    }
    return checks, schema_issues + constraint_issues


def validate_after_schema(after: dict[str, Any]) -> list[str]:
    schema = after.get("schema") if isinstance(after, dict) else None
    tables = schema.get("tables") if isinstance(schema, dict) else None
    if not isinstance(tables, dict):
        return ["after.schema.tables must be an object"]

    issues: list[str] = []
    for table_name, table_schema in tables.items():
        if not isinstance(table_name, str) or not table_name:
            issues.append("after schema contains an invalid table name")
            continue
        if not isinstance(table_schema, dict):
            issues.append(f"{table_name} schema must be an object")
            continue

        columns = table_schema.get("columns")
        column_order = table_schema.get("column_order")
        if not isinstance(columns, dict) or not columns:
            issues.append(f"{table_name} must contain at least one column")
            continue
        if any(not isinstance(name, str) or not name for name in columns):
            issues.append(f"{table_name} contains an invalid column name")
        if any(not isinstance(meta, dict) for meta in columns.values()):
            issues.append(f"{table_name} column metadata must be objects")
        if not isinstance(column_order, list):
            issues.append(f"{table_name}.column_order must be a list")
        elif (
            any(not isinstance(name, str) for name in column_order)
            or len(column_order) != len(set(column_order))
            or set(column_order) != set(columns)
        ):
            issues.append(f"{table_name}.column_order must match columns exactly")

    return issues


def validate_after_constraints(
    after: dict[str, Any],
    existing_schema: dict[str, Any] | None = None,
) -> list[str]:
    partial_schema = after.get("schema", {}).get("tables", {})
    known_tables = dict(
        existing_schema.get("tables", {})
        if isinstance(existing_schema, dict)
        else {}
    )
    if isinstance(partial_schema, dict):
        known_tables.update(partial_schema)

    constraints = after.get("constraints", {}) if isinstance(after, dict) else {}
    if isinstance(constraints, dict) and "constraints" in constraints:
        constraints = constraints.get("constraints")
    if not isinstance(constraints, dict):
        return ["after.constraints must be an object"]

    issues: list[str] = []

    def columns_exist(table: Any, columns: Any, label: str) -> bool:
        if table not in known_tables:
            issues.append(f"{label} references missing table {table}")
            return False
        table_columns = known_tables[table].get("columns", {})
        if not isinstance(columns, list) or not columns:
            issues.append(f"{label} must reference at least one column")
            return False
        missing = [column for column in columns if column not in table_columns]
        if missing:
            issues.append(f"{label} references missing columns in {table}")
            return False
        return True

    primary_keys = constraints.get("primary_keys", {})
    unique_constraints = constraints.get("unique_constraints", {})
    indexes = constraints.get("indexes", {})
    foreign_keys = constraints.get("foreign_keys", {})
    sections = (primary_keys, unique_constraints, indexes, foreign_keys)
    if any(not isinstance(section, dict) for section in sections):
        return ["constraint sections must be objects"]

    for table, columns in primary_keys.items():
        columns_exist(table, columns, f"primary key on {table}")
    for section_name, section in (
        ("unique constraint", unique_constraints),
        ("index", indexes),
    ):
        for table, column_groups in section.items():
            if not isinstance(column_groups, list):
                issues.append(f"{section_name} list on {table} is invalid")
                continue
            for columns in column_groups:
                columns_exist(table, columns, f"{section_name} on {table}")

    for table, table_fks in foreign_keys.items():
        if not isinstance(table_fks, list):
            issues.append(f"foreign key list on {table} is invalid")
            continue
        for fk in table_fks:
            if not isinstance(fk, dict):
                issues.append(f"foreign key on {table} is invalid")
                continue
            columns = fk.get("columns")
            referenced_table = fk.get("referenced_table")
            referenced_columns = fk.get("referenced_columns")
            columns_exist(table, columns, f"foreign key on {table}")
            columns_exist(
                referenced_table,
                referenced_columns,
                f"foreign key on {table}",
            )
            if (
                isinstance(columns, list)
                and isinstance(referenced_columns, list)
                and len(columns) != len(referenced_columns)
            ):
                issues.append(f"foreign key on {table} has unequal column counts")

    return issues


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
