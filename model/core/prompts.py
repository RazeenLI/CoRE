import json
from typing import Any, Callable, get_args
from model.core.schemas import TableRole, SemanticType, MatchStatus

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
- full_match means the existing table can reliably explain all incoming columns.
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