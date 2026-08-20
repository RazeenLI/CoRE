"""
示例占位

TODO: 根据 agent 开发 完成 result 的结构和格式
"""

from typing import Literal, TypedDict


# -----------------------------
# Matcher
# -----------------------------

MatcherEvolutionDecisionType = Literal[
    "extend_table",
    "create_table",
]

MatchStatus = Literal[
    "full_match",
    "partial_match",
    "ambiguous_match",
    "poor_match",
]


# MatchType = Literal[
#     "direct",
#     "semantic_equivalent",
#     "possible_identifier",
#     "possible_fk",
#     "transform_needed",
# ]

class ColumnMatch(TypedDict, total=False):
    target_column: str
    confidence: float
    # match_type: MatchType
    # requires_transform: bool
    reason: str


class TableMatch(TypedDict, total=False):
    target_table: str
    confidence: float
    match_status: MatchStatus

    # Key: source column name
    # Value: candidate target columns for this source column
    column_matches: dict[str, list[ColumnMatch]]

    # Computed after LLM output normalization.
    unmatched_source_columns: list[str]

    # Computed after LLM output normalization.
    ambiguous_source_columns: list[str]

    reason: str


class MatcherResult(TypedDict, total=False):
    # Must be sorted by confidence descending.
    # The best match is table_matches[0] if the list is not empty.
    table_matches: list[TableMatch]

