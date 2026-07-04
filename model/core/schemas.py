"""
示例占位

TODO: 根据 agent 开发 完成 result 的结构和格式

column matches这个地方我有一个问题，是一个column只能有一个配对吗？有时候不是会有好几个潜在的选项吗？
这个地方我的想法是
"column_matches": [
"source_column_1": [
{
target_column: "target_column_1"
confidence: 0.8
reason: ""
}
]
"""

from typing import Any, Literal, Optional, TypedDict

TableRole = Literal[
    "entity_table",
    "transaction_table",
    "lookup_table",
    "relationship_table",
    "unknown",
]

SemanticType = Literal[
    "identifier",
    "foreign_key_candidate",
    "person_name",
    "organization_name",
    "email",
    "phone",
    "address",
    "country",
    "city",
    "date",
    "timestamp",
    "money",
    "quantity",
    "category",
    "status",
    "description",
    "code",
    "boolean",
    "unknown",
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

# -----------------------------
# Profile
# -----------------------------

class TableProfile(TypedDict, total=False):
    # original incoming table name
    name: str 

    # LLM-generated short description of what this table represents
    summary: str
    # LLM-generated main business entity, e.g. "customer", "invoice", "artist"
    entity: str
    # LLM-generated table role
    role: TableRole
    # LLM-generated alternative names for matching
    aliases: list[str]

    # column_count: int


# class ColumnSymbolicProfile(TypedDict, total=False):
#     # inferred from sample values or provided stats
#     inferred_dtype: str

#     # sample-level statistics
#     null_count_in_sample: int
#     null_ratio_in_sample: float
#     distinct_count_in_sample: int
#     distinct_ratio_in_sample: float

#     # rule-based value pattern labels
#     value_patterns: list[str]

#     # rule-based structural signals
#     looks_like_id: bool
#     looks_like_fk: bool
#     looks_like_email: bool
#     looks_like_date: bool
#     looks_like_code: bool

# class ColumnSemanticProfile(TypedDict, total=False):
#     # LLM-generated explanation of the column meaning
#     meaning: str

#     # LLM-generated semantic type
#     semantic_type: SemanticType

#     # LLM-generated business concept, e.g. "customer identifier"
#     business_concept: str

#     # LLM-generated aliases for matching
#     aliases: list[str]

class ColumnProfile(TypedDict, total=False):
    # original incoming column name
    name: str

    # # optional; include only if you want SourceProfile to be self-contained
    # sample_values: list[Any]

    # # deterministic / rule-based / statistic-based profile
    # symbolic: ColumnSymbolicProfile

    # inferred from sample values or provided stats
    dtype: str
    # rule-based value pattern labels
    value_patterns: list[str]


    # # LLM-generated semantic profile
    # semantic: ColumnSemanticProfile

    # LLM-generated explanation of the column meaning
    meaning: str

    # LLM-generated semantic type
    semantic_type: SemanticType

    # LLM-generated business concept, e.g. "customer identifier"
    business_concept: str

    # LLM-generated aliases for matching
    aliases: list[str]

class ProfilerResult(TypedDict, total=False):
    table: TableProfile

    # key = original column name
    columns: dict[str, ColumnProfile]

# class ColumnProfile(TypedDict, total=False):
#     column_name: str
#     inferred_type: str
#     nullable: bool
#     sample_values: list[Any]
#     description: str


# class SourceProfile(TypedDict, total=False):
#     table_name: str
#     row_count: int
#     columns: list[ColumnProfile]
#     description: str


# -----------------------------
# Matcher
# -----------------------------

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

# class ColumnMapping(TypedDict, total=False):
#     source_column: str
#     target_table: str
#     target_column: str
#     confidence: float
#     reason: str


# class MatcherResult(TypedDict, total=False):
#     decision: Literal[
#         "high_confidence_match",
#         "partial_match",
#         "no_match",
#     ]
#     matched_target_table: Optional[str]
#     confidence: float
#     column_mappings: list[ColumnMapping]
#     unmatched_source_columns: list[str]
#     reason: str


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