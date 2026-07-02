# core/schema.py

"""
示例占位

TODO: 根据 agent 开发 完成 result 的结构和格式
"""

from typing import Any, Literal, Optional, TypedDict


class ColumnProfile(TypedDict, total=False):
    column_name: str
    inferred_type: str
    nullable: bool
    sample_values: list[Any]
    description: str


class SourceProfile(TypedDict, total=False):
    table_name: str
    row_count: int
    columns: list[ColumnProfile]
    description: str


class ColumnMapping(TypedDict, total=False):
    source_column: str
    target_table: str
    target_column: str
    confidence: float
    reason: str


class MatchingResult(TypedDict, total=False):
    decision: Literal[
        "high_confidence_match",
        "partial_match",
        "no_match",
    ]
    matched_target_table: Optional[str]
    confidence: float
    column_mappings: list[ColumnMapping]
    unmatched_source_columns: list[str]
    reason: str


class EvolutionProposal(TypedDict, total=False):
    action: Literal[
        "extend_existing_table",
        "create_new_table",
        "create_multiple_tables",
        "reject",
        "needs_review",
    ]
    target_table: Optional[str]
    new_table_name: Optional[str]
    added_columns: list[ColumnProfile]
    reason: str


class ValidationReport(TypedDict, total=False):
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    reason: str


class FinalDecision(TypedDict, total=False):
    action: Literal[
        "apply_mapping",
        "apply_schema_evolution",
        "reject",
        "manual_review",
    ]
    approved: bool
    target_table: Optional[str]
    reason: str