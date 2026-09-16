import unittest

from baselines.llm_adapter.orchestrator import (
    LLMAdapterOrchestrator,
    normalize_matcher_evidence,
)


class LLMAdapterBaselineTest(unittest.TestCase):
    def test_matcher_evidence_uses_one_shared_budget(self) -> None:
        raw = {
            "matcher": "example",
            "table_matches": [
                {
                    "target_table": "album",
                    "confidence": 0.9,
                    "column_matches": {
                        "title": [
                            {"target_column": "title", "confidence": 0.8},
                            {"target_column": "name", "confidence": 0.7},
                        ]
                    },
                },
                {
                    "target_table": "artist",
                    "confidence": 0.7,
                    "column_matches": {
                        "title": [
                            {"target_column": "name", "confidence": 0.6},
                        ]
                    },
                },
            ],
        }

        result = normalize_matcher_evidence(
            raw,
            matcher_name="example",
            table_top_k=1,
            column_top_k_per_table=1,
        )

        self.assertEqual(result["selected_tables"], ["album"])
        self.assertEqual(result["column_candidates"], {
            "title": [{
                "target_table": "album",
                "target_column": "title",
                "retrieval_score": 0.8,
            }]
        })

    def test_adapter_uses_standard_evolutor_without_profiles_or_validator(self) -> None:
        captured = {}

        class Evolutor:
            def __call__(self, **kwargs):
                captured.update(kwargs)
                return {"decision": {"decision_type": "create_table"}}

        class State:
            incoming_schema = {"tables": {"incoming": {"columns": {}}}}
            incoming_values = []
            existing_schema = {"tables": {}}
            existing_values = {}
            existing_profiles = {"tables": {"must_not": "be passed"}}
            constraints = {"constraints": {}}
            match_result = {"selected_tables": [], "column_candidates": {}}

            def save_result(self, *args):
                self.saved = args

            def set_routing(self, *args):
                self.routing = args

        orchestrator = object.__new__(LLMAdapterOrchestrator)
        orchestrator.evolutor = Evolutor()
        orchestrator._run_evolutor(State())

        self.assertIsNone(captured["incoming_profile"])
        self.assertIsNone(captured["existing_profiles"])
        self.assertIsNone(captured["validation_feedback"])
        self.assertEqual(captured["selection_result"], State.match_result)
