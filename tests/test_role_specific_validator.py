import unittest

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
