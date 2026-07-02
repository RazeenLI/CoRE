import json
from typing import Any, Callable

PromptBuilder = Callable[[dict[str, Any]], str]

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
    "role": "entity_table | transaction_table | lookup_table | relationship_table | unknown",
    "aliases": ["..."]
  }},
  "columns": {{
    "<original_column_name>": {{
      "meaning": "...",
      "semantic_type": "identifier | foreign_key_candidate | person_name | organization_name | email | phone | address | country | city | date | timestamp | money | quantity | category | status | description | code | boolean | unknown",
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