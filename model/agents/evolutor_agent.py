from __future__ import annotations

from typing import Any


from model.agents.base_agent import BaseAgent
from model.core.prompts import PromptBuilder, evolutor_prompt
from model.utils.io import terminal_message
from model.utils.structure import get_column_values
from model.core.schemas import (
    ColumnPlacement,
    ConstraintSignal,
)

# from experiments.selector.model.prompts import evolutor_prompt


class EvolutorAgent(BaseAgent):
    """Make the final relationship and evolution decision without a matcher."""

    def __init__(
        self,
        llm_client: Any,
        prompt_builder: PromptBuilder = evolutor_prompt,
    ) -> None:
        super().__init__(llm_client=llm_client, prompt_builder=prompt_builder)

    def __call__(
        self,
        *,
        incoming_schema: dict[str, Any],
        incoming_values: list[dict[str, Any]],
        incoming_profile: dict[str, Any] | None,
        existing_schema: dict[str, Any],
        existing_values: dict[str, list[dict[str, Any]]],
        existing_profiles: dict[str, Any] | None,
        existing_constraints: dict[str, Any],
        selection_result: dict[str, Any],
        validation_feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        table_name, table_schema = self._extract_single_table(incoming_schema)
        selected_tables = _selected_table_names(
            selection_result=selection_result,
            existing_schema=existing_schema,
        )
        selected_schema = {
            **existing_schema,
            "tables": {
                name: existing_schema["tables"][name]
                for name in selected_tables
            },
        }

        llm_input: dict[str, Any] = {
            "incoming_table": build_table_context(
                table_name=table_name,
                table_schema=table_schema,
                rows=incoming_values,
                profile=incoming_profile,
            ),
            "existing_rdb": {
                "database": existing_schema.get("database"),
                "dialect": existing_schema.get("dialect"),
                "version": existing_schema.get("version"),
                "tables": build_existing_tables_context(
                    existing_schema=selected_schema,
                    existing_profiles=existing_profiles,
                    existing_values=existing_values,
                ),
                "constraints": existing_constraints.get(
                    "constraints",
                    existing_constraints,
                ),
            },
        }
        llm_input["candidate_selection"] = selection_result
        if validation_feedback is not None:
            llm_input["validation_feedback"] = validation_feedback

        terminal_message(
            "info",
            f"Selector evolving incoming table '{table_name}' against candidates: {selected_tables}.",
            "\t",
        )
        result = apply_llm_output(
            self._generate_json(self.prompt_builder(llm_input))
        )
        terminal_message(
            "success",
            f"Experimental Evolutor completed with decision: {result['decision']['decision_type']}.",
            "\t",
        )
        return result


def build_llm_input(
    incoming_table_name: str,
    incoming_table_schema: dict[str, Any],
    incoming_values: list[dict[str, Any]],
    incoming_profile: dict[str, Any] | None,
    existing_schema: dict[str, Any],
    existing_profiles: dict[str, Any] | None,
    existing_values: dict[str, list[dict[str, Any]]],
    existing_constraints: dict[str, Any],
) -> dict[str, Any]:
    """Build the complete one-shot context without matcher preselection."""

    return {
        "incoming_table": build_table_context(
            table_name=incoming_table_name,
            table_schema=incoming_table_schema,
            rows=incoming_values,
            profile=incoming_profile,
        ),
        "existing_rdb": {
            "database": existing_schema.get("database"),
            "dialect": existing_schema.get("dialect"),
            "version": existing_schema.get("version"),
            "tables": build_existing_tables_context(
                existing_schema=existing_schema,
                existing_profiles=existing_profiles,
                existing_values=existing_values,
            ),
            "constraints": existing_constraints.get(
                "constraints",
                existing_constraints,
            ),
        },
    }


def build_existing_tables_context(
    existing_schema: dict[str, Any],
    existing_profiles: dict[str, Any] | None,
    existing_values: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Build context for every existing table, with no candidate filtering."""

    profiles_by_table = get_profiles_by_table(existing_profiles)
    tables_context: dict[str, dict[str, Any]] = {}

    for table_name, table_schema in existing_schema.get("tables", {}).items():
        tables_context[table_name] = build_table_context(
            table_name=table_name,
            table_schema=table_schema,
            rows=existing_values.get(table_name, []),
            profile=profiles_by_table.get(table_name),
        )

    return tables_context


def build_table_context(
    table_name: str,
    table_schema: dict[str, Any],
    rows: list[dict[str, Any]],
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Combine schema, samples, and profiles into one table-level context."""

    profile = profile or {}
    table_profile = profile.get("table", {})
    column_profiles = profile.get("columns", {})

    columns: dict[str, Any] = {}

    for column_name, column_schema in table_schema.get("columns", {}).items():
        columns[column_name] = {
            "schema": column_schema,
            "sample_values": get_column_values(
                rows=rows,
                column_name=column_name,
            ),
            "profile": column_profiles.get(column_name, {}),
        }

    table_schema_metadata = {
        key: value
        for key, value in table_schema.items()
        if key != "columns"
    }

    return {
        "name": table_name,
        "schema": table_schema_metadata,
        "profile": table_profile,
        "columns": columns,
    }


def apply_llm_output(
    llm_output: dict[str, Any],
) -> dict[str, Any]:
    return {
        "decision": normalize_decision(llm_output["decision"]),
        "column_placements": normalize_column_placements(
            llm_output["column_placements"]
        ),
        "constraint_signals": normalize_constraint_signals(
            llm_output["constraint_signals"]
        ),
        "reason": llm_output.get("reason", ""),
    }


def normalize_decision(
    raw_decision: dict[str, Any],
) -> dict[str, Any]:
    return {
        "decision_type": raw_decision["decision_type"],
        "target_table": raw_decision["target_table"],
        "related_tables": raw_decision["related_tables"],
        "reason": raw_decision["reason"],
    }


def normalize_column_placements(
    raw_column_placements: dict[str, Any],
) -> dict[str, ColumnPlacement]:
    column_placements: dict[str, ColumnPlacement] = {}

    for source_column, raw_placement in raw_column_placements.items():
        column_placements[source_column] = {
            "source_column": raw_placement["source_column"],
            "target_table": raw_placement["target_table"],
            "target_column": raw_placement["target_column"],
            "reason": raw_placement["reason"],
        }

    return column_placements


def normalize_constraint_signals(
    raw_constraint_signals: list[dict[str, Any]],
) -> list[ConstraintSignal]:
    constraint_signals: list[ConstraintSignal] = []

    for raw_signal in raw_constraint_signals:
        signal: ConstraintSignal = {
            "constraint_type": raw_signal["constraint_type"],
            "table": raw_signal["table"],
            "columns": raw_signal["columns"],
            "reason": raw_signal["reason"],
        }

        if raw_signal["constraint_type"] == "foreign_key":
            signal["referenced_table"] = raw_signal["referenced_table"]
            signal["referenced_columns"] = raw_signal[
                "referenced_columns"
            ]

        constraint_signals.append(signal)

    return constraint_signals


def get_profiles_by_table(
    existing_profiles: dict[str, Any] | None,
) -> dict[str, Any]:
    if not existing_profiles:
        return {}

    tables = existing_profiles.get("tables")

    if isinstance(tables, dict):
        return tables

    return existing_profiles

def _selected_table_names(
    *,
    selection_result: dict[str, Any],
    existing_schema: dict[str, Any],
) -> list[str]:
    selected = selection_result.get("selected_tables", [])
    return [name for name in selected if name in existing_schema.get("tables", {})]

