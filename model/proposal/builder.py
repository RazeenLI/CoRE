"""
有以下一些问题
1. proposal_type 我认为这个的意义不大，没什么作用。或者你能解释一下你为什么要这个？
2. source 有意义，但是没什么作用。可以保留给validator作为返回哪个agent的参考。
3. decision_type，operation和proposal_type这两个算是输入的而不是输出的吧？matcher是一种type evolutor会给顶一个decision_type
4. 
# Planned actions
"table_actions": list[dict[str, Any]],
"column_actions": list[dict[str, Any]],
"schema_actions": list[dict[str, Any]],
"constraint_actions": list[dict[str, Any]],
"relationship_actions": list[dict[str, Any]],
"data_actions": list[dict[str, Any]], 
这一部分我觉得你的写法太繁复了
而且不应该是这样的分开的，table的操作和column的操作是有关系的，应该是一个table_actions里面包含了table和column的操作，
schema_actions就是你所说的这个table操作，这两个应该是一样的
constraint_actions和relationship_actions是一样的，都是constraint的操作
data_actions是数据的操作，这个是单独的，和schema无关
5. 你这个proposal的结构太复杂了，我觉得不需要这么复杂，应该是一个简单的proposal，里面包含了table和column的操作，constraint的操作，和数据的操作，这样就够了
甚至数据的操作都是基于column的操作，应该是一个column_actions里面包含了数据的操作更合适
6. key_strategy这个就是constraint的操作，应该是一个constraint_actions里面包含了这个key_strategy的操作更合适
7. issues 这个如果是rule-based，就是很清晰的接收信息处理信息怎么会出现issues呢？
8. status也是不是这个result应该有的，这个是系统层级的信息，不应该存在于这个result中

"""
from typing import Any

from model.core.schemas import ColumnAction, TableAction, ConstraintAction, IntegrationProposal, ProposalDecisionType, TableActionType, ColumnActionType, ConstraintActionType
from model.utils.io import terminal_message

SUPPORTED_RESULT_SOURCES = {"matcher", "evolutor"}


def build_proposal(
    *,
    incoming_schema: dict[str, Any],
    incoming_values: list[dict[str, Any]],
    existing_schema: dict[str, Any],
    existing_values: dict[str, list[dict[str, Any]]],
    existing_constraints: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Build an integration proposal from either matcher result or evolutor result.

    This function is only a dispatcher.
    It does not contain matcher-specific or evolutor-specific proposal logic.
    """

    source = result["source"]
    payload = result["payload"]

    terminal_message("info", f"Building proposal from {source}.", "\t")

    if source == "matcher":
        return _build_from_matcher_result(
            incoming_schema=incoming_schema,
            incoming_values=incoming_values,
            existing_schema=existing_schema,
            existing_values=existing_values,
            existing_constraints=existing_constraints,
            matcher_result=payload
        )

    if source == "evolutor":
        return _build_from_evolutor_result(
            incoming_schema=incoming_schema,
            incoming_values=incoming_values,
            existing_schema=existing_schema,
            existing_values=existing_values,
            existing_constraints=existing_constraints,
            evolutor_result=payload,
        )

    raise ValueError(f"Unsupported result source: {source}")


def _build_from_matcher_result(
    *,
    incoming_schema: dict[str, Any],
    incoming_values: list[dict[str, Any]],
    existing_schema: dict[str, Any],
    existing_values: dict[str, list[dict[str, Any]]],
    existing_constraints: dict[str, Any],
    matcher_result: dict[str, Any],
) -> IntegrationProposal:
    """
    Build proposal from matcher result.

    Assumption:
        matcher_result["table_matches"] is already sorted by confidence.
        The first table match is the selected target table.

    Matcher proposal:
        - maps incoming table to an existing table
        - maps each incoming column to the best existing target column
        - does not create constraints
    """

    selected_match = matcher_result["table_matches"][0]
    target_table = selected_match["target_table"]

    column_actions: list[ColumnAction] = _build_matcher_column_actions(
        column_matches=selected_match["column_matches"]
    )

    table_action: TableAction = {
        "action": "map",
        "table": target_table,
        "column_actions": column_actions,
    }

    constraint_actions: list[ConstraintAction] = []

    proposal: IntegrationProposal = {
        "source_decision": "insert_table",
        "table_actions": [table_action],
        "constraint_actions": constraint_actions,
    }

    terminal_message("success", f"Matching proposal builded by decision 'insert_table'.", "\t")

    return proposal


def _build_matcher_column_actions(
    *,
    column_matches: dict[str, list[dict[str, Any]]],
) -> list[ColumnAction]:
    """
    Build column actions from matcher column matches.

    For each incoming column, select the target column with the highest confidence.
    """

    column_actions: list[ColumnAction] = []

    for source_column, candidates in column_matches.items():
        best_candidate = max(
            candidates,
            key=lambda candidate: candidate["confidence"],
        )

        column_action: ColumnAction = {
            "action": "map",
            "source_columns": [source_column],
            "target_columns": [best_candidate["target_column"]],
        }

        column_actions.append(column_action)

    return column_actions


def _build_from_evolutor_result(
    *,
    incoming_schema: dict[str, Any],
    incoming_values: list[dict[str, Any]],
    existing_schema: dict[str, Any],
    existing_values: dict[str, list[dict[str, Any]]],
    existing_constraints: dict[str, Any],
    evolutor_result: dict[str, Any],
) -> IntegrationProposal:
    """
    Build proposal from evolutor result.

    Evolutor result is expected to contain:
    {
        "decision": {
            "decision_type": ...
        },
        "column_placements": {...},
        "constraint_signals": [...]
    }

    Rule:
        - if target_table exists:
            table action = "map"
        - if target_table does not exist:
            table action = "create"

        - if target_column exists in target_table:
            column action = "map"
        - if target_column does not exist:
            column action = "create"
    """

    decision_type = evolutor_result["decision"]["decision_type"]

    if decision_type in {
        "extend_table",
        "create_entity_table",
        "create_association_table",
    }:
        terminal_message("success", f"Evolution proposal builded by decision '{decision_type}'.", "\t")
        return _build_standard_evolution_proposal(
            existing_schema=existing_schema,
            evolutor_result=evolutor_result,
        )

    if decision_type == "create_child_table":
        raise NotImplementedError("create_child_table proposal builder is not implemented yet.")

    if decision_type == "reject_source":
        return {
            "source_decision": "reject_source",
            "table_actions": [],
            "constraint_actions": [],
        }

    if decision_type == "defer_decision":
        return {
            "source_decision": "defer_decision",
            "table_actions": [],
            "constraint_actions": [],
        }

    raise ValueError(f"Unsupported evolutor decision_type: {decision_type}")

def _build_standard_evolution_proposal(
    *,
    existing_schema: dict[str, Any],
    evolutor_result: dict[str, Any],
) -> IntegrationProposal:
    decision_type = evolutor_result["decision"]["decision_type"]

    table_actions = _build_table_actions_from_column_placements(
        existing_schema=existing_schema,
        column_placements=evolutor_result["column_placements"],
    )

    constraint_actions = _build_constraint_actions_from_signals(
        constraint_signals=evolutor_result.get("constraint_signals", []),
    )

    proposal: IntegrationProposal = {
        "source_decision": decision_type,
        "table_actions": table_actions,
        "constraint_actions": constraint_actions,
    }

    return proposal

def _build_table_actions_from_column_placements(
    *,
    existing_schema: dict[str, Any],
    column_placements: dict[str, dict[str, Any]],
) -> list[TableAction]:
    table_action_by_table: dict[str, TableAction] = {}

    for placement in column_placements.values():
        target_table = placement["target_table"]
        target_column = placement["target_column"]
        source_column = placement["source_column"]

        if target_table not in table_action_by_table:
            table_action_by_table[target_table] = {
                "action": _infer_table_action(
                    existing_schema=existing_schema,
                    table=target_table,
                ),
                "table": target_table,
                "column_actions": [],
            }

        column_action: ColumnAction = {
            "action": _infer_column_action(
                existing_schema=existing_schema,
                table=target_table,
                column=target_column,
            ),
            "source_columns": [source_column],
            "target_columns": [target_column],
        }

        table_action_by_table[target_table]["column_actions"].append(column_action)

    return list(table_action_by_table.values())

def _build_constraint_actions_from_signals(
    *,
    constraint_signals: list[dict[str, Any]],
) -> list[ConstraintAction]:
    constraint_actions: list[ConstraintAction] = []

    for signal in constraint_signals:
        constraint_type = signal["constraint_type"]

        if constraint_type == "primary_key":
            constraint_action: ConstraintAction = {
                "action": "add_primary_key",
                "table": signal["table"],
                "columns": signal["columns"],
            }

        elif constraint_type == "foreign_key":
            constraint_action = {
                "action": "add_foreign_key",
                "table": signal["table"],
                "columns": signal["columns"],
                "referenced_table": signal["referenced_table"],
                "referenced_columns": signal["referenced_columns"],
            }

        elif constraint_type == "unique_constraint":
            constraint_action = {
                "action": "add_unique_constraint",
                "table": signal["table"],
                "columns": signal["columns"],
            }

        elif constraint_type == "index":
            constraint_action = {
                "action": "add_index",
                "table": signal["table"],
                "columns": signal["columns"],
            }

        else:
            raise ValueError(f"Unsupported constraint_type: {constraint_type}")

        constraint_actions.append(constraint_action)

    return constraint_actions

def _infer_table_action(
    *,
    existing_schema: dict[str, Any],
    table: str,
) -> str:
    if _table_exists(existing_schema=existing_schema, table=table):
        return "map"

    return "create"


def _infer_column_action(
    *,
    existing_schema: dict[str, Any],
    table: str,
    column: str,
) -> str:
    if _column_exists(
        existing_schema=existing_schema,
        table=table,
        column=column,
    ):
        return "map"

    return "create"


def _table_exists(
    *,
    existing_schema: dict[str, Any],
    table: str,
) -> bool:
    return table in existing_schema["tables"]


def _column_exists(
    *,
    existing_schema: dict[str, Any],
    table: str,
    column: str,
) -> bool:
    if not _table_exists(existing_schema=existing_schema, table=table):
        return False

    return column in existing_schema["tables"][table]["columns"]