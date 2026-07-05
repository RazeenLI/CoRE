"""
示例占位

TODO: 根据 agent 开发 完成 result 的结构和格式
"""

from typing import Any, Literal, Optional, TypedDict

# -----------------------------
# Profile
# -----------------------------

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

from typing import Literal, TypedDict


# -----------------------------
# Evolution
# -----------------------------

EvolutionDecisionType = Literal[
    # v1 implemented
    "extend_table",
    "create_entity_table",
    "create_association_table",

    # reserved for future
    "transform_table", # transform column structure, e.g. split, merge
    "create_child_table",
    "reject_source",
    "defer_decision",
]
# insert_table


ConstraintSignalType = Literal[
    "primary_key",
    "foreign_key",
    "unique_constraint",
    "index",
]


class EvolutionDecision(TypedDict, total=False):
    """
    Table-level evolution decision.

    decision_type:
        The main evolution type.
        主 evolution 类型。

    target_table:
        The table that this evolution points to.

        统一含义：
        - if decision_type == "extend_table":
            target_table is the existing table to modify.
            target_table 是要修改的已有表。

        - if decision_type starts with "create_":
            target_table is the new table to create.
            target_table 是要创建的新表。

    related_tables:
        Existing tables related to target_table.

        相关已有表：
        - for create_association_table:
            related_tables are the entity tables connected by the association table.
            related_tables 是 association table 连接的实体表。

        - for create_child_table:
            related_tables are usually the parent table(s).
            related_tables 通常是 child table 的 parent table。

        - for extend_table / create_entity_table:
            this can usually be empty.
            对 extend_table / create_entity_table 来说通常可以为空。

    """

    decision_type: EvolutionDecisionType

    target_table: str

    # Existing tables related to target_table.
    # For create_association_table:
    #   related_tables = entities connected by the association table.
    # For create_child_table:
    #   related_tables = parent table(s).
    related_tables: list[str]

    reason: str


class ColumnPlacement(TypedDict, total=False):
    """
    Column-level placement signal.

    Evolutor only decides where each incoming column should land.
    ProposalBuilder decides whether the target column already exists
    or should be created.

    - if target_table exists and target_column exists:
        map source_column to existing target_table.target_column

        如果 target_table 存在，且 target_column 存在：
        把 source_column 映射到已有的 target_table.target_column

    - if target_table exists but target_column does not exist:
        add target_column to target_table

        如果 target_table 存在，但 target_column 不存在：
        给 target_table 添加 target_column

    - if target_table does not exist:
        create target_table and add target_column to the new table

        如果 target_table 不存在：
        创建 target_table，并在新表里添加 target_column
    """

    source_column: str

    target_table: str
    target_column: str

    reason: str


class ConstraintSignal(TypedDict, total=False):
    """
    Constraint-level signal.

    Constraints are separate from column placement because PK/FK/indexes
    are stored in constraints metadata.
    """

    constraint_type: ConstraintSignalType

    table: str
    columns: list[str]

    # Only for foreign_key
    referenced_table: str
    referenced_columns: list[str]

    reason: str


class EvolutorResult(TypedDict, total=False):
    """
    Evolutor output.

    Evolutor decides the evolution direction and column placement.
    ProposalBuilder converts this into concrete schema / constraint updates.
    """

    decision: EvolutionDecision

    # Key: incoming/source column name
    column_placements: dict[str, ColumnPlacement]

    constraint_signals: list[ConstraintSignal]

    reason: str


# class EvolutionProposal(TypedDict, total=False):
#     action: Literal[
#         "extend_existing_table",
#         "create_new_table",
#         "create_multiple_tables",
#         "reject",
#         "needs_review",
#     ]
#     target_table: Optional[str]
#     new_table_name: Optional[str]
#     added_columns: list[ColumnProfile]
#     reason: str


# -----------------------------
# Proposal
# -----------------------------

ProposalDecisionType = EvolutionDecisionType | Literal[
    "insert_table",
]


TableActionType = Literal[
    # Use an existing table as the target.
    "map",

    # Create a new table.
    "create",
]


ColumnActionType = Literal[
    # source column maps to existing target column.
    "map",

    # source column becomes a new target column.
    "create",

    # existing target column is removed or migrated out.
    "drop",

    # one source column is split into multiple target columns.
    "split",

    # multiple source columns are merged into one target column.
    "merge",

    # target column is derived from source/existing data.
    "derive",
]


ConstraintActionType = Literal[
    "add_primary_key",
    "add_foreign_key",
    "add_unique_constraint",
    "add_index",
]


class ColumnAction(TypedDict, total=False):
    """
    Column-level integration action.

    This is not only schema-level.
    It represents how incoming columns are placed into the target table.

    action:
        - map:
            source_columns -> existing target_columns

        - create:
            source_columns -> newly created target_columns

        - drop:
            remove target_columns from an existing table

        - split:
            one source column -> multiple target columns

        - merge:
            multiple source columns -> one target column

        - derive:
            target column is derived from source/existing data

    Because split / merge exist, both source_columns and target_columns
    are always lists.
    """

    action: ColumnActionType

    # Incoming/source columns.
    # For drop, this can be absent or empty.
    source_columns: list[str]

    # Target columns in the table of the parent TableAction.
    target_columns: list[str]


class TableAction(TypedDict, total=False):
    """
    Table-level integration action.

    action:
        - map:
            Use an existing table.

        - create:
            Create a new table.

    table:
        - if action == "map":
            existing table name

        - if action == "create":
            new table name

    column_actions:
        Column placement / transformation actions inside this table.
    """

    action: TableActionType

    table: str

    column_actions: list[ColumnAction]


class ConstraintAction(TypedDict, total=False):
    """
    Constraint-level integration action.

    Constraints are independent from table / column placement.
    Usually created when a new table is created.
    """

    action: ConstraintActionType

    table: str
    columns: list[str]

    # Only for add_foreign_key.
    referenced_table: str
    referenced_columns: list[str]


class IntegrationProposal(TypedDict, total=False):
    """
    ProposalBuilder output.

    This is only a structural integration plan.

    It does NOT contain:
        - incoming_schema
        - incoming_values
        - existing_schema
        - existing_values
        - existing_constraints
        - generated RDB
        - validation status
        - LLM reasons

    The proposal only contains:
        - table / column integration actions
        - constraint actions
    """

    source_decision: ProposalDecisionType

    table_actions: list[TableAction]

    constraint_actions: list[ConstraintAction]

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