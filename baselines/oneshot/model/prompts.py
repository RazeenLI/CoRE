import json
from typing import Any, Literal

from model.core.prompts import PromptBuilder, literal_to_prompt_options
from model.core.schemas import ConstraintSignalType


OneShotDecisionType = Literal[
    "insert_table",
    "extend_table",
    "create_table",
]

def evolutor_prompt(llm_input: dict[str, Any]) -> str:
    return f"""
You are a one-shot database schema integration and evolution agent.

Given one incoming table and the complete existing RDB context, infer the integration or schema evolution signal needed for the incoming table.

The Evolutor does not build the final proposal.
It only decides:
1. the table-level integration or evolution type
2. where each incoming column should be placed
3. possible constraint signals

Input:
{json.dumps(llm_input, indent=2, ensure_ascii=False)}

Output Format:
Return only valid JSON with this exact structure:

{{
  "decision": {{
    "decision_type": "{literal_to_prompt_options(OneShotDecisionType)}",
    "target_table": "<table_name>",
    "related_tables": ["<existing_related_table_name>"],
    "reason": "..."
  }},
  "column_placements": {{
    "<incoming_column_name>": {{
      "source_column": "<incoming_column_name>",
      "target_table": "<table_name>",
      "target_column": "<column_name>",
      "reason": "..."
    }}
  }},
  "constraint_signals": [
    {{
      "constraint_type": "{literal_to_prompt_options(ConstraintSignalType)}",
      "table": "<table_name>",
      "columns": ["<column_name>"],
      "referenced_table": "<referenced_table_name>",
      "referenced_columns": ["<referenced_column_name>"],
      "reason": "..."
    }}
  ],
  "reason": "..."
}}

Decision rules:
- First determine whether the incoming rows are additional instances of an existing relation, direct attributes of an existing relation's semantic subject, or a distinct semantic concept.
- Choose "insert_table" only when the incoming rows are additional instances of one existing relation and every incoming column can be reliably mapped to an existing column in that relation without changing its schema.
- Choose "extend_table" when the incoming table describes the same semantic subject as one existing relation and introduces one or more direct attributes that require new columns.
- Choose "create_table" when the incoming table represents a distinct entity, event, relationship, or independently meaningful concept that should retain its own relation.
- Apply these rules in order: test "insert_table" first, then distinguish "extend_table" from "create_table" by semantic subject.

Scope rules:
- Only use tables provided in existing_rdb.tables as existing tables.
- Do not infer, invent, or reference missing existing tables.
- related_tables may only contain tables from existing_rdb.tables.
- Do not create or reference an implied table only because an identifier column exists.
- Do not create an association table unless at least two referenced existing tables are present in existing_rdb.tables.
- Foreign keys may only reference tables from existing_rdb.tables.

Grain and semantic-boundary rules:
- Infer what one incoming row represents from the table name, all columns, profiles, sample values, and constraints.
- Before choosing "insert_table", verify that every incoming column corresponds to an existing column in the target table. If any incoming column requires creating a new column, "insert_table" is not allowed.
- If the incoming table name exactly matches an existing table name after case and separator normalization, and at least one incoming column requires a new column, prefer "extend_table" over "create_table" unless the incoming rows clearly have a different grain.
- Do not treat a semantic alias or general topical similarity as an exact table-name match.
- Row grain is evidence, but it is not sufficient by itself to distinguish "extend_table" from "create_table".
- A shared identifier, key, one-to-one correspondence, foreign key, or joinability does not by itself imply "extend_table".
- Choose "extend_table" only when the incoming columns are direct attributes of the semantic subject represented by the existing target table.
- Choose "create_table" when the incoming columns collectively describe a different semantic subject, even if the incoming table shares a key or row grain with an existing table.
- A new table does not need to have a foreign-key relationship with the existing RDB.
- Table-name similarity is supporting evidence only and must not override the semantic meaning of the table and columns.
- If a column references a missing table, do not invent that missing table; preserve the column within the table selected by the decision.

Column placement rules:
- Every incoming column must appear exactly once in column_placements.
- For "insert_table", place every incoming column into its corresponding existing column in the existing target_table.
- For "extend_table", place all columns into the existing target_table. Map existing columns to their exact existing names and use new column names only for columns that must be added.
- For "create_table", place all columns into the new target_table.
- Use existing table and column names exactly when mapping to existing schema elements.
- Use new table and column names only for schema elements created by the selected decision.

Constraint signal rules:
- For "insert_table", normally return an empty constraint_signals list because the existing schema is unchanged.
- Do not emit foreign keys to missing tables.
- Do not emit constraints involving tables that are not in existing_rdb.tables or the selected new target_table.
- For "extend_table", only emit constraint signals that can be supported by the existing target_table.
- For "create_table", emit PK/FK signals only when supported by explicit columns and existing referenced tables.

Output rules:
- Return exactly one JSON object.
- decision_type must be one of: "insert_table", "extend_table", "create_table".
- Every reason must be one short phrase with at most 12 words.
- Do not use quotation marks, line breaks, braces, or brackets inside a reason.
- Do not repeat schemas, samples, candidate evidence, or rules in a reason.
- Do not add fields outside the required JSON structure.
- Return JSON only.
""".strip()
