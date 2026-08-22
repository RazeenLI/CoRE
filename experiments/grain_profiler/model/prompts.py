from __future__ import annotations

import json
from typing import Any

from model.core.prompts import literal_to_prompt_options
from model.core.schemas import SemanticType, TableRole


GRAIN_ROLES = (
    "identifier",
    "reference",
    "attribute",
    "measure",
    "temporal",
    "unknown",
)


def grain_profiler_prompt(llm_input: dict[str, Any]) -> str:
    """Ask only for semantic evidence needed to determine row grain."""

    return f"""
You are a concise database row-grain profiling agent.

Infer what one row represents and how every column contributes to that grain.

Input:
{json.dumps(llm_input, indent=2, ensure_ascii=False)}

Return only valid JSON with this exact structure:

{{
  "table": {{
    "entity": "short entity name",
    "role": "{literal_to_prompt_options(TableRole)}",
    "row_grain": "one row per ..."
  }},
  "columns": {{
    "<original_column_name>": {{
      "semantic_type": "{literal_to_prompt_options(SemanticType)}",
      "business_concept": "short concept",
      "grain_role": "{literal_to_prompt_options(GRAIN_ROLES)}"
    }}
  }}
}}

Rules:
- Include every input column exactly once and use its original name as the key.
- identifier means a column that identifies the incoming row grain.
- reference means an identifier of another entity.
- measure means a numeric fact such as amount, price, count, or quantity.
- temporal means a date or timestamp describing the row.
- attribute means a descriptive property of the row entity.
- Keep entity and business_concept to at most four words.
- Keep row_grain to at most six words and start it with "one row per".
- Do not output aliases, summaries, meanings, dtypes, value patterns, or samples.
- Do not invent columns.
- Return JSON only.
""".strip()
