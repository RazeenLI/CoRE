import json
from typing import Any, Callable, get_args
from model.core.schemas import TableRole, SemanticType, EvolutionDecisionType, ConstraintSignalType, ValidationRoute

PromptBuilder = Callable[[dict[str, Any]], str]

def literal_to_prompt_options(literal_type: Any) -> str:
    return " | ".join(get_args(literal_type))

def profiler_prompt(llm_input: dict[str, Any]) -> str:
    return f"""
You are a database table profiling agent.

Given an incoming table schema and sampled rows, infer the semantic meaning of the table and each column.

Task:
Generate a semantic profile for:
1. The table as a whole.
2. Every input column.

For each column, infer:
- meaning
- semantic_type
- business_concept
- aliases useful for schema matching

Input:
{json.dumps(llm_input, indent=2, ensure_ascii=False)}

Output Format:
Return only valid JSON with this exact structure:

{{
  "table": {{
    "summary": "...",
    "entity": "...",
    "role": "{literal_to_prompt_options(TableRole)}",
    "aliases": ["..."]
  }},
  "columns": {{
    "<original_column_name>": {{
      "meaning": "...",
      "semantic_type": "{literal_to_prompt_options(SemanticType)}",
      "business_concept": "...",
      "aliases": ["..."]
    }}
  }}
}}

Rules:
- Only describe the given incoming table and its columns.
- Do not invent tables or columns.
- Use the original column names exactly as keys.
- Use sample values only as evidence for semantic interpretation.
- Do not generate synthetic values.
- If the meaning is uncertain, use "unknown".
- Keep aliases concise and database-like.
- Return JSON only.
""".strip()


def evolutor_prompt(llm_input: dict[str, Any]) -> str:
    context_note = (
        "The existing tables are high-recall candidates selected by an embedding model. "
        "Selection is evidence, not a final match; independently verify it."
    )
    feedback_note = (
        "Previous validation feedback is provided. Revise the decision, placements, "
        "or constraints that caused those issues."
        if "validation_feedback" in llm_input
        else ""
    )
    return f"""
You are a one-shot database schema integration and evolution agent.

Given one incoming table and the provided existing RDB context, infer the
integration or schema evolution signal needed for the incoming table. There is
no separate matcher.

The Evolutor does not build the final proposal.
It only decides:
1. the table-level integration or evolution type
2. where each incoming column should be placed
3. possible constraint signals

{context_note}
{feedback_note}

Input:
{json.dumps(llm_input, indent=2, ensure_ascii=False)}

Return only valid JSON with this exact structure:

{{
  "decision": {{
    "decision_type": "{literal_to_prompt_options(EvolutionDecisionType)}",
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

def validator_prompt(llm_input: dict[str, Any]) -> str:
    return f"""
You are a relational database validation agent.

Given a proposal, a BEFORE partial RDB, and an AFTER partial RDB, judge whether the AFTER partial RDB is a reasonable generated database result.

Input:
{json.dumps(llm_input, indent=2, ensure_ascii=False)}

Output Format:
Return only valid JSON with this exact structure:

{{
  "route": "{literal_to_prompt_options(ValidationRoute)}",
  "score": 0.0,
  "issues": [
    "short issue phrase"
  ],
  "summary": "..."
}}

Judgment focus:
- Whether the AFTER partial RDB is a coherent relational database design.
- Whether the BEFORE-to-AFTER change is reasonably explained by the proposal.
- Whether tables, columns, and constraints in the AFTER partial RDB are designed appropriately.
- Whether the AFTER partial RDB introduces obvious redundancy, information loss, broken entity boundaries, or unreasonable constraints.

Routing rules:
- Use "decision" if the AFTER partial RDB is reasonable.
- Use "matcher" if the proposal source_decision is "insert_table" and the generated RDB should be revised.
- Use "evolutor" if the proposal source_decision is not "insert_table" and the generated RDB should be revised.

Scoring rules:
- 0.90-1.00: clearly reasonable and ready for final decision.
- 0.75-0.89: acceptable with minor concerns.
- 0.50-0.74: questionable with significant design risks.
- 0.00-0.49: unreasonable or poor generated RDB result.

Issue rules:
- issues must be short, concrete, and actionable.
- Name the affected table or column whenever possible.
- If route is matcher or evolutor, provide at least one issue.
- Use an empty list only when route is decision.

Output rules:
- summary must be one concise sentence.
- If revision is required, summary must briefly state what the next agent should reconsider.
- Return exactly one JSON object.
- Do not wrap the JSON in markdown code fences.
- Return JSON only.
""".strip()


def validation_feedback_prompt(
    llm_input: dict[str, Any],
    agent_name: str,
) -> str:
    feedback = llm_input.get("validation_feedback")

    if not feedback:
        return ""

    if agent_name == "matcher":
        revision_scope = (
            "Reconsider the target-table and column-matching "
            "results related to the feedback."
        )
    elif agent_name == "evolutor":
        revision_scope = (
            "Reconsider the decision, column placements, and "
            "constraint signals related to the feedback."
        )
    else:
        raise ValueError(
            f"Unsupported feedback agent: {agent_name}"
        )

    return f"""
Previous validation feedback is included in the input.

{revision_scope}

Use the feedback as revision guidance.
Do not repeat a rejected result without clear supporting evidence.
""".strip()