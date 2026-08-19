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
- Choose "insert_table" when the incoming table has the same row grain as one existing table and every incoming column can be reliably mapped to an existing column in that table without changing the existing schema.
- Choose "extend_table" when the incoming table has the same row grain as one existing table but introduces one or more columns that must be added to that table.
- Choose "create_table" when the incoming table has a new row grain that cannot be represented by any existing table.

Scope rules:
- Only use tables provided in existing_rdb.tables as existing tables.
- Do not infer, invent, or reference missing existing tables.
- related_tables may only contain tables from existing_rdb.tables.
- Do not create or reference an implied table only because an identifier column exists.
- Do not create an association table unless at least two referenced existing tables are present in existing_rdb.tables.
- Foreign keys may only reference tables from existing_rdb.tables.

Grain rules:
- Infer the incoming row grain from all incoming columns.
- A matched identifier column may indicate table identity or a reference-like attribute; it is not enough by itself to create a new table.
- If the incoming table name matches an existing table and all incoming columns reliably map to existing columns, prefer "insert_table".
- If the incoming table name matches an existing table and the incoming columns can be stored on that table after adding columns, prefer "extend_table".
- If a column looks like a reference to a missing table, keep it as a column on the selected target table and do not invent the missing table.

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
