import json
from typing import Any, Callable, get_args
from model.core.schemas import TableRole, SemanticType, MatchStatus, EvolutionDecisionType, ConstraintSignalType, ValidationRoute

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

def matcher_prompt(llm_input: dict[str, Any]) -> str:
    return f"""
You are a database table matching agent.

Given one incoming table and one existing table, infer whether the existing table is a direct schema match for the incoming table and how their columns correspond.

Important:
Table matching means the existing table can directly explain, absorb, or represent the incoming table.
It does not mean the two tables are merely related, connected by a foreign key, or in the same business domain.

Task:
Generate a table matching result for:
1. The incoming table against the existing table as a whole.
2. Every incoming column against possible existing columns.

For the table pair, infer:
- confidence
- match_status
- reason

For each incoming column, infer zero or more possible target column matches.
Each source column must appear exactly once as a key in column_matches.

For each candidate target column, infer:
- target_column
- confidence
- reason

Input:
{json.dumps(llm_input, indent=2, ensure_ascii=False)}

Output Format:
Return only valid JSON with this exact structure:

{{
  "target_table": "<existing_table_name>",
  "confidence": 0.0,
  "match_status": "{literal_to_prompt_options(MatchStatus)}",
  "column_matches": {{
    "<incoming_column_name>": [
      {{
        "target_column": "<existing_column_name>",
        "confidence": 0.0,
        "reason": "..."
      }}
    ]
  }},
  "reason": "..."
}}

Rules:
- Only compare the given incoming table and the given existing table.
- Do not invent tables or columns.
- Use the original existing table name exactly as target_table.
- Use the original incoming column names exactly as keys in column_matches.
- Use the original existing column names exactly as target_column values.
- Every incoming column must appear exactly once as a key in column_matches.
- If an incoming column has no reliable target column in this existing table, use an empty list for that source column.
- A source column may have multiple candidate target columns if multiple matches are plausible.
- Sort candidate target columns for each source column by confidence descending.
- Use schema, sample values, profiles, and constraints as evidence.

Column matching rules:
- A high-confidence column match requires compatible meaning, semantic type, business concept, data type, and sample values.
- Similar names alone are not enough for high confidence.
- Similar data types alone are not enough for high confidence.
- Generic identifier columns such as id, code, key, customer_id, user_id, and invoice_id are weak evidence unless supported by table context, sample values, and profile semantics.
- A foreign-key-like identifier may match at the column level, but it is weak evidence for table-level matching.

Table confidence rules:
- Table confidence measures whether the target table can directly serve as the destination table for the incoming table.
- Table confidence must not measure general semantic relatedness.
- Table confidence must be mainly grounded in how many incoming columns have reliable target column matches.
- Table profile similarity is useful, but it cannot replace column-level evidence.
- Shared domain, shared entity names, foreign-key relationships, or related business concepts are not enough for high table confidence.
- If all or almost all incoming columns have strong target column matches and the table profiles describe the same entity, table confidence may be 0.90 to 1.00.
- If most incoming columns have reliable target column matches and the table profiles are compatible, table confidence may be 0.70 to 0.89.
- If only some incoming columns match, table confidence should usually be 0.40 to 0.69.
- If fewer than half of incoming columns have reliable target column matches, table confidence must be below 0.50.
- If the only strong column match is a generic identifier or foreign-key-like column, table confidence must be below 0.35.
- If the target table represents a different entity, event, transaction, or relationship type, table confidence must be below 0.60 even if several columns are related.
- If the existing table does not directly explain the incoming table, do not give high confidence.

Match status rules:
- full_match means every incoming column has a reliable target column match in the existing table. The existing table may contain additional columns that are not present in the incoming table.
- partial_match means the existing table can explain some incoming columns, but at least one incoming column has no reliable match.
- poor_match means this existing table does not meaningfully explain the incoming table as a direct destination table.
- ambiguous_match means one or more incoming columns have multiple plausible target columns with similar confidence.

Confidence calibration:
- 0.90-1.00: Direct same-table match; nearly all incoming columns have strong matches.
- 0.70-0.89: Strong partial or near-complete match; most incoming columns are explainable.
- 0.40-0.69: Some meaningful column matches, but the table is not a complete destination.
- 0.20-0.39: Weak relationship; usually only identifiers or a small number of related fields match.
- 0.00-0.19: No meaningful direct table match.

Output rules:
- Confidence values must be numbers between 0 and 1.
- Keep evidence concise and specific.
- Return exactly one JSON object.
- Do not include reasoning, analysis, explanations, or examples.
- Do not wrap the JSON in markdown code fences.
- Return JSON only.
""".strip()


def evolutor_prompt(llm_input: dict[str, Any]) -> str:
    return f"""
You are a database schema evolution agent.

Given one incoming table, matcher evidence, and selected existing RDB context, infer the schema evolution signal needed for the incoming table.

The Evolutor does not build the final proposal.
It only decides:
1. the table-level evolution type
2. where each incoming column should be placed
3. possible constraint signals

Input:
{json.dumps(llm_input, indent=2, ensure_ascii=False)}

Output Format:
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

Decision type rules:
- Use "extend_table" when the incoming table has the same row grain as one existing candidate table and the remaining columns are attributes of that same table.
- Use "create_entity_table" when the incoming table has its own entity, event, transaction, or record identity.
- Use "create_entity_table" when the incoming table contains one existing entity identifier plus additional event-specific, transaction-specific, or record-specific attributes.
- Use "create_association_table" when the incoming table is mainly identified by references to two or more existing candidate tables and describes their relationship.
- Use "create_child_table" when the incoming table contains repeated child records under one existing parent table.
- Use "reject_source" when the incoming table belongs to a different business domain from the current RDB.
- Use "defer_decision" when multiple incompatible interpretations remain equally plausible from the provided evidence.

Grain rules:
- First infer the incoming table row grain.
- Prefer the decision that explains all incoming columns under one consistent row grain.
- A reference to an existing entity is evidence of relationship, not automatically evidence of same-table extension.
- An existing entity identifier such as customer_id can indicate a foreign-key reference to that entity.
- A reference column alone is weaker than event-specific, transaction-specific, or entity-specific attributes for deciding row grain.
- Date, amount, status, total, quantity, billing, shipping, payment, order, invoice, line, and transaction fields usually indicate event or transaction grain.
- Name, email, phone, address, demographic, profile, and descriptive fields usually indicate entity/profile grain when they belong to the same entity.
- If the incoming table name and non-key attributes indicate an event or transaction, choose create_entity_table for that event or transaction table.
- If the incoming table contains customer_id plus invoice_date, billing fields, or total, interpret customer_id as a reference and choose an invoice-like target_table.
- If the incoming table contains only attributes of one existing entity and shares that entity grain, choose extend_table.
- If the incoming table mixes columns from multiple grains, choose the decision that best explains the primary row grain and explain the mixed evidence in reason.

Target table rules:
- target_table is the main table affected by the decision.
- For "extend_table", target_table is the existing candidate table with the same row grain as the incoming table.
- For "create_entity_table", target_table is the new entity, event, transaction, or record table to create.
- For "create_association_table", target_table is the new association table to create.
- For "create_child_table", target_table is the new child table to create.
- For new tables, use a concise database-style table name based on the incoming table meaning.
- related_tables contains existing candidate tables referenced by or connected to target_table.
- For "create_association_table", related_tables contains the existing entity tables connected by the new association table.
- For "create_child_table", related_tables contains the existing parent table.
- For "create_entity_table", related_tables may contain existing tables referenced by identifier columns.
- For "extend_table", related_tables can be an empty list unless another existing table is needed to explain the relationship.

Column placement rules:
- Every incoming column appears exactly once in column_placements.
- Each key in column_placements is the original incoming column name.
- source_column equals the original incoming column name.
- target_table is the table where the source column should land.
- target_column is the column name that should store the source column.
- Place each incoming column into the table that matches the incoming row grain.
- For "extend_table", place columns into the selected existing target_table when they are attributes of that table's row grain.
- For "create_entity_table", place all entity/event/transaction attributes into the new target_table.
- For "create_entity_table", place reference columns such as customer_id into the new target_table, because they are foreign-key-like columns stored on the new table.
- For "create_association_table", place all relationship key columns and relationship attributes into the new association target_table.
- For "create_child_table", place the parent reference column and child attributes into the new child target_table.
- When the source column corresponds to an existing concept in the selected target table, use the existing target column name.
- When the source column represents a new concept, use a concise database-style column name.
- Column placement only describes where the data should land. ProposalBuilder will decide whether the target column already exists or should be created.

Matcher evidence rules:
- Use each candidate table's matcher summary as evidence.
- Treat table confidence as evidence for whether the candidate table can directly explain the incoming table.
- Treat column confidence as evidence for local column correspondence or possible references.
- Treat strong identifier matches as evidence for table identity, foreign-key reference, or association-table structure depending on row grain.
- Treat ambiguous source columns as columns requiring evolution-level interpretation.
- Prefer the decision that best explains the whole incoming table grain.
- Prefer an existing table as target_table only when the table-level match and row grain both support it.
- Prefer a new table when the strongest evidence is a reference to an existing table plus new event/entity attributes.

Schema evolution rules:
- Preserve the incoming table grain.
- Prefer "extend_table" when the incoming rows describe the same entity grain as one existing table.
- Prefer "create_entity_table" when the incoming rows describe a new entity, event, transaction, or record with its own identifier and attributes.
- Prefer "create_association_table" when the incoming rows are identified by references to two or more existing entities.
- Prefer "create_child_table" when multiple incoming rows can belong to one existing parent entity.
- Prefer "defer_decision" when the evidence supports multiple incompatible interpretations.

Output rules:
- Use existing table names exactly as shown in candidate_tables when referring to existing tables.
- Use existing column names exactly as shown in candidate_tables when mapping to existing concepts.
- Use new table and column names only for schema elements created by the selected decision.
- Keep reasons concise and evidence-based.
- Return exactly one JSON object.
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
- Use "matcher" if the proposal source_decision is "insert" and the generated RDB should be revised.
- Use "evolutor" if the proposal source_decision is not "insert" and the generated RDB should be revised.

Scoring rules:
- 0.90-1.00: clearly reasonable and ready for final decision.
- 0.75-0.89: acceptable with minor concerns.
- 0.50-0.74: questionable with significant design risks.
- 0.00-0.49: unreasonable or poor generated RDB result.

Issue rules:
- issues must be a list of short phrases.
- Use an empty list if there are no issues.

Output rules:
- summary must be one concise sentence.
- Return exactly one JSON object.
- Do not wrap the JSON in markdown code fences.
- Return JSON only.
""".strip()