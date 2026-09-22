import unittest

from model.agents.validator_agent import ValidatorAgent
from model.core.llm_client import merge_usage_summaries
from model.pipeline import create_agents


class RoleSpecificValidatorTest(unittest.TestCase):
    def test_create_agents_assigns_only_validator_to_larger_client(self) -> None:
        core_client = object()
        validator_client = object()

        agents = create_agents(core_client, validator_client)

        self.assertIs(agents["profiler"].llm_client, core_client)
        self.assertIs(agents["evolutor"].llm_client, core_client)
        self.assertIs(agents["validator"].llm_client, validator_client)

    def test_usage_merge_retains_model_role_for_every_call(self) -> None:
        merged = merge_usage_summaries({
            "core": {
                "model": "Qwen3.5-9B",
                "calls": [{
                    "caller": "EvolutorAgent",
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "elapsed_seconds": 1.0,
                }],
            },
            "validator": {
                "model": "Qwen3.5-27B",
                "calls": [{
                    "caller": "ValidatorAgent",
                    "input_tokens": 7,
                    "output_tokens": 3,
                    "elapsed_seconds": 2.0,
                }],
            },
        })

        self.assertEqual(merged["models"]["core"], "Qwen3.5-9B")
        self.assertEqual(merged["models"]["validator"], "Qwen3.5-27B")
        self.assertEqual(merged["call_count"], 2)
        self.assertEqual(merged["calls"][1]["client_role"], "validator")

    def test_validator_rejects_malformed_schema_without_calling_llm(self) -> None:
        class FailingClient:
            def generate_json(self, *args, **kwargs):
                raise AssertionError("LLM must not be called after a hard-rule failure")

        result = ValidatorAgent(FailingClient())(
            proposal={"source_decision": "extend_table"},
            before={},
            after={
                "schema": {
                    "tables": {
                        "customer": {
                            "columns": {"id": {"type": "integer"}},
                            "column_order": ["missing"],
                        }
                    }
                },
                "constraints": {},
            },
        )

        self.assertEqual(result["route"], "evolutor")
        self.assertEqual(result["score"], 0.0)
        self.assertFalse(result["rule_checks"]["after_schema_well_formed"])

    def test_validator_rejects_invalid_constraint_reference(self) -> None:
        result = ValidatorAgent(None)(
            proposal={"source_decision": "insert_table"},
            before={},
            after={
                "schema": {
                    "tables": {
                        "customer": {
                            "columns": {"id": {"type": "integer"}},
                            "column_order": ["id"],
                        }
                    }
                },
                "constraints": {
                    "primary_keys": {"customer": ["missing"]},
                },
            },
        )

        self.assertEqual(result["route"], "matcher")
        self.assertFalse(
            result["rule_checks"]["after_constraints_reference_valid"]
        )
