"""Shared result schemas for pipeline agents and proposal construction."""

from typing import Literal, TypedDict

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

# -----------------------------
# Evolution
# -----------------------------

EvolutionDecisionType = Literal[
    # v1 implemented
    "insert_table",
    "extend_table",
    "create_table",
    # "create_association_table",

    # # reserved for future
    # "transform_table", # transform column structure, e.g. split, merge
    # "create_child_table",
    # "reject_source",
    # "defer_decision",
]


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

    target_table:
        The table that this evolution points to.

        - if decision_type == "extend_table":
            target_table is the existing table to modify.

        - if decision_type starts with "create_":
            target_table is the new table to create.

    related_tables:
        Existing tables related to target_table.

        - for create_association_table:
            related_tables are the entity tables connected by the association table.

        - for create_child_table:
            related_tables are usually the parent table(s).

        - for extend_table / create_entity_table:
            this can usually be empty.

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


    - if target_table exists but target_column does not exist:
        add target_column to target_table


    - if target_table does not exist:
        create target_table and add target_column to the new table

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


# -----------------------------
# Proposal
# -----------------------------

ProposalDecisionType = EvolutionDecisionType 

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

    source_decision: EvolutionDecisionType

    table_actions: list[TableAction]

    constraint_actions: list[ConstraintAction]


from typing import Any, Literal, TypedDict


# -----------------------------
# Validator
# -----------------------------

ValidationRoute = Literal[
    "decision",
    "matcher",
    "evolutor",
]


class ValidatorRuleChecks(TypedDict):
    """
    Hard rule checks.

    These checks are deterministic.
    If any rule is False, validation stops and LLM judgment is not called.
    """

    after_schema_well_formed: bool
    after_constraints_reference_valid: bool


class ValidatorLLMJudgment(TypedDict):
    """
    LLM judgment result.

    Only produced when all hard rule checks pass.
    The final route and score are directly copied from this judgment
    in the current single-LLM validator design.
    """

    route: ValidationRoute
    score: float

    # Short issue phrases selected/generated by the LLM.
    # Example:
    # [
    #   "new table lacks a clear primary key",
    #   "foreign key relationship may be lost"
    # ]
    issues: list[str]

    summary: str


class ValidationReport(TypedDict, total=False):
    """
    Final validator output.

    If rule checks fail:
        - score = 0.0
        - route is determined from source_decision
        - llm_judgment is omitted or None
        - issues / summary explain the hard-rule failure

    If rule checks pass:
        - route comes from llm_judgment.route
        - score comes from llm_judgment.score
        - issues / summary usually copy llm_judgment
    """

    route: ValidationRoute
    score: float

    rule_checks: ValidatorRuleChecks

    # Present only if all rule checks passed.
    llm_judgment: ValidatorLLMJudgment | None

    # Final issues exposed to orchestrator.
    # For rule failure: hard-rule issues.
    # For LLM judgment: copied from llm_judgment["issues"].
    issues: list[str]

    # Final summary exposed to orchestrator.
    summary: str

class FinalDecision(TypedDict, total=False):
    approved: bool
