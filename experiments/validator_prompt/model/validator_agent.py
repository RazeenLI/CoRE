from __future__ import annotations

from typing import Any

from model.agents.validator_agent import ValidatorAgent, apply_llm_output, build_llm_input
from model.utils.io import terminal_message
from experiments.validator_prompt.model.prompts import validator_prompt


EVIDENCE_TYPES = {
    "relation_granularity", "row_identity", "functional_dependency",
    "cardinality", "target_existence",
}
DECISIONS = {"insert_table", "extend_table", "create_table"}


def _normalize_evidence(
    raw_evidence: Any, known_objects: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(raw_evidence, list):
        return []
    evidence: list[dict[str, Any]] = []
    for item in raw_evidence:
        if not isinstance(item, dict):
            continue
        evidence_type = item.get("type")
        objects = item.get("objects")
        observation = item.get("observation")
        if evidence_type not in EVIDENCE_TYPES or not isinstance(objects, list):
            continue
        normalized_objects = [
            value.strip() for value in objects
            if isinstance(value, str) and value.strip()
        ]
        if not normalized_objects:
            continue
        if known_objects is not None and not any(
            value in known_objects for value in normalized_objects
        ):
            continue
        if not isinstance(observation, str) or len(observation.strip()) < 12:
            continue
        evidence.append({
            "type": evidence_type,
            "objects": normalized_objects,
            "observation": observation.strip(),
        })
    return evidence[:8]


def apply_conservative_gate(
    llm_output: dict[str, Any], source_decision: str, target_table: str,
    known_objects: set[str] | None = None,
) -> dict[str, Any]:
    result = apply_llm_output(llm_output, source_decision)
    evidence = _normalize_evidence(
        llm_output.get("decision_evidence"), known_objects=known_objects
    )
    recommended = llm_output.get("recommended_decision")
    scope = llm_output.get("revision_scope")
    try:
        confidence = min(
            max(float(llm_output.get("decision_confidence", 0.0)), 0.0), 1.0
        )
    except (TypeError, ValueError):
        confidence = 0.0
    decision_change_allowed = (
        result["route"] != "decision"
        and scope == "decision"
        and recommended in DECISIONS
        and recommended != source_decision
        and confidence >= 0.95
        and len(evidence) >= 2
        and len({item["type"] for item in evidence}) >= 2
    )
    result.update({
        "revision_scope": scope if scope in {"none", "proposal", "decision"} else "proposal",
        "recommended_decision": recommended if recommended in DECISIONS else None,
        "decision_confidence": confidence,
        "decision_evidence": evidence,
        "decision_change_allowed": decision_change_allowed,
        "preserve_decision": result["route"] != "decision" and not decision_change_allowed,
        "locked_decision": source_decision,
        "locked_target_table": target_table,
    })
    if result["preserve_decision"]:
        result["revision_scope"] = "proposal"
        gate_issue = (
            f"Conservative gate: preserve {source_decision} on {target_table}; "
            "decision-change evidence did not meet the threshold."
        )
        if gate_issue not in result["issues"]:
            result["issues"].append(gate_issue)
        result["summary"] = gate_issue
    return result


class ValidatorPromptAgent(ValidatorAgent):
    """Prompt validator with a deterministic gate for decision changes."""

    def __init__(self, llm_client: Any | None = None) -> None:
        super().__init__(llm_client=llm_client, prompt_builder=validator_prompt)

    def __call__(
        self, proposal: dict[str, Any], before: dict[str, Any], after: dict[str, Any],
    ) -> dict[str, Any]:
        source_decision = proposal["source_decision"]
        table_actions = proposal.get("table_actions", [])
        target_table = table_actions[0].get("table", "") if table_actions else ""
        llm_output = self._generate_json(
            self.prompt_builder(build_llm_input(proposal, before, after))
        )
        known_objects: set[str] = set()
        for partial_rdb in (before, after):
            for table_name, table in partial_rdb.get("schema", {}).get(
                "tables", {}
            ).items():
                known_objects.add(table_name)
                for column_name in table.get("columns", {}):
                    known_objects.add(column_name)
                    known_objects.add(f"{table_name}.{column_name}")
        for table_action in table_actions:
            action_table = str(table_action.get("table", ""))
            known_objects.add(action_table)
            for column_action in table_action.get("column_actions", []):
                known_objects.update(column_action.get("source_columns", []))
                for column_name in column_action.get("target_columns", []):
                    known_objects.add(column_name)
                    known_objects.add(f"{action_table}.{column_name}")
        result = apply_conservative_gate(
            llm_output, source_decision, target_table, known_objects=known_objects
        )
        terminal_message(
            "success",
            f"ValidatorPromptAgent completed with route={result['route']} "
            f"preserve_decision={result['preserve_decision']}.",
            "\t",
        )
        return result
