from __future__ import annotations

import json
from typing import Any


def reranker_prompt(llm_input: dict[str, Any]) -> str:
    """Rerank retrieved pairs and return compact cross-table evidence."""

    return f"""
You are the LLM reranking stage of Magneto schema matching.

For every incoming column, evaluate its retrieved target-column candidates by
semantic correspondence, but return only the ten best reliable matches. This
is column matching only: do not decide insert, extend, or create, and do not
generate a proposal.

Input:
{json.dumps(llm_input, indent=2, ensure_ascii=False)}

Return only valid JSON:
{{
  "column_matches": {{
    "<incoming_column>": [
      {{
        "target_table": "<retrieved target table>",
        "target_column": "<retrieved target column>",
        "confidence": 0.0
      }}
    ]
  }}
}}

Rules:
- Every incoming column must appear exactly once as a key.
- Only return target pairs present in that column's retrieved candidates.
- Evaluate all retrieved candidates, but return at most 10 matches per incoming column.
- Return at most one target column from the same target table; retain only that
  table's highest-confidence column match.
- Do not return weak candidates merely to fill the 10-result limit.
- Return an empty list when no candidate is a reliable semantic match.
- Names, data types, table context, and sampled values are evidence.
- Similar types or foreign-key relatedness alone do not establish a match.
- Sort each returned list by confidence descending.
- Confidence must be between 0 and 1.
- Keep the JSON compact: do not add explanations or extra fields.
- Return JSON only.
""".strip()
