from __future__ import annotations

import json
from typing import Any

from model.core.prompts import evolutor_prompt, literal_to_prompt_options
from model.core.schemas import ValidationRoute


def validator_prompt(llm_input: dict[str, Any]) -> str:
    return f"""
You are a conservative relational-database validation agent.

Given a proposal, a BEFORE partial RDB, and an AFTER partial RDB, first check
whether AFTER implements the proposal. Only then assess whether the relational
decision itself is demonstrably wrong.

Input:
{json.dumps(llm_input, indent=2, ensure_ascii=False)}

Return only valid JSON with this exact structure:

{{
  "route": "{literal_to_prompt_options(ValidationRoute)}",
  "score": 0.0,
  "revision_scope": "none | proposal | decision",
  "recommended_decision": "insert_table | extend_table | create_table | none",
  "decision_confidence": 0.0,
  "decision_evidence": [
    {{
      "type": "relation_granularity | row_identity | functional_dependency | cardinality | target_existence",
      "objects": ["concrete table or column"],
      "observation": "concrete observation grounded in the input"
    }}
  ],
  "issues": ["short actionable issue"],
  "summary": "one concise sentence"
}}

Operation semantics (do not reverse these definitions):
- insert_table loads rows into an existing table. Every source column maps to
  an existing target column; BEFORE and AFTER schemas remain identical.
- extend_table changes an existing table by creating at least one new column.
- create_table creates a target table that is absent from BEFORE.
- Mapping incoming columns to existing columns is expected for insert_table;
  it is not evidence that insert_table is invalid.
- insert_table does not create a table despite its historical name.

Validation procedure:
1. Check that every incoming source column is handled exactly once.
2. Check mapped columns against BEFORE and created columns against AFTER.
3. Check foreign-key endpoints, duplicate definitions, conflicts, and
   preservation of unrelated schema objects.
4. Distinguish a faulty proposal implementation from a faulty decision.

Conservative decision policy:
- Use revision_scope="proposal" when column placements or constraints should
  be repaired while retaining the current source_decision.
- Use revision_scope="decision" only when the current source_decision is
  contradicted by strong relational evidence, not merely because a different
  design is plausible.
- A decision revision requires confidence >= 0.95, a different
  recommended_decision, and at least two independent evidence items naming
  concrete tables or columns.
- Ambiguity, naming similarity, or a single suspicious mapping is insufficient
  to change the decision. In those cases preserve the decision and repair the
  proposal, or accept it when no blocking defect exists.

Routing:
- Use decision when the result is ready; revision_scope must be none.
- Use matcher to revise an insert_table proposal.
- Use evolutor to revise an extend_table or create_table proposal.
- A revision route must include at least one actionable issue.

Scoring:
- 0.90--1.00 means ready or a high-confidence diagnosis.
- 0.75--0.89 means a concrete proposal-level repair is needed.
- Below 0.75 means uncertain; do not authorize a decision change.

Return exactly one JSON object without markdown fences.
""".strip()


def conservative_evolutor_prompt(llm_input: dict[str, Any]) -> str:
    prompt = evolutor_prompt(llm_input)
    feedback = llm_input.get("validation_feedback") or {}
    if not feedback.get("preserve_decision"):
        return prompt
    locked_decision = feedback.get("locked_decision", "")
    locked_target = feedback.get("locked_target_table", "")
    return (
        prompt
        + f"""

Mandatory conservative revision constraint:
- Keep decision.decision_type exactly "{locked_decision}".
- Keep decision.target_table exactly "{locked_target}".
- Repair only column placements, constraints, or explanations identified by
  validation_feedback.
- Do not reinterpret a proposal-level defect as permission to change the
  relational operation.
"""
    ).strip()
