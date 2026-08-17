import unittest

import torch

from baselines.magneto.model.matcher import (
    normalize_reranker_output,
    retrieve_column_candidates,
    serialize_column,
)
from baselines.magneto.model.rules import RuleThresholds, build_rule_result


class MagnetoBaselineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.existing_schema = {
            "tables": {
                "album": {
                    "columns": {
                        "album_id": {"type": "integer", "nullable": False},
                        "title": {"type": "string", "nullable": False},
                    }
                },
                "artist": {
                    "columns": {
                        "artist_id": {"type": "integer", "nullable": False},
                        "name": {"type": "string", "nullable": True},
                    }
                },
            }
        }
        self.incoming_schema = {
            "tables": {
                "music_album": {
                    "columns": {
                        "album_id": {"type": "integer", "nullable": False},
                        "title": {"type": "string", "nullable": False},
                        "year": {"type": "integer", "nullable": True},
                    }
                }
            }
        }

    def test_mpnet_retrieval_returns_topk_per_source_column(self) -> None:
        class FakeEmbeddingModel:
            def encode(self, texts, **kwargs):
                vectors = []
                for text in texts:
                    lowered = text.lower()
                    vectors.append(
                        [
                            float("album" in lowered),
                            float("artist" in lowered),
                            float("title" in lowered),
                            float("name" in lowered),
                        ]
                    )
                return torch.nn.functional.normalize(
                    torch.tensor(vectors, dtype=torch.float32), dim=1
                )

        result = retrieve_column_candidates(
            embedding_model=FakeEmbeddingModel(),
            incoming_table_name="music_album",
            incoming_table=self.incoming_schema["tables"]["music_album"],
            incoming_values=[],
            existing_schema=self.existing_schema,
            existing_values={"album": [], "artist": []},
            top_k=2,
        )
        self.assertEqual(len(result["title"]), 2)
        self.assertEqual(result["title"][0]["target_table"], "album")
        self.assertEqual(result["title"][0]["target_column"], "title")

    def test_column_serialization_contains_header_type_and_values(self) -> None:
        text = serialize_column(
            table_name="invoice",
            column_name="total",
            column_schema={"type": "decimal"},
            values=[1.25, 9.50],
        )
        self.assertIn("Table: invoice", text)
        self.assertIn("Column: total", text)
        self.assertIn("Type: decimal", text)
        self.assertIn("1.25", text)

    def test_normalizer_rejects_hallucinated_names(self) -> None:
        result = normalize_reranker_output(
            raw={
                "column_matches": {
                    "album_id": [
                        {
                            "target_table": "album",
                            "target_column": "not_real",
                            "confidence": 1.0,
                        }
                    ],
                    "title": [
                        {
                            "target_table": "album",
                            "target_column": "title",
                            "confidence": 0.9,
                        }
                    ],
                    "year": [],
                }
            },
            incoming_columns=["album_id", "title", "year"],
            retrieved={
                "album_id": [
                    {
                        "target_table": "album",
                        "target_column": "album_id",
                        "retrieval_score": 0.8,
                    }
                ],
                "title": [
                    {
                        "target_table": "album",
                        "target_column": "title",
                        "retrieval_score": 0.9,
                    }
                ],
                "year": [],
            },
        )
        self.assertEqual(result["table_matches"][0]["column_matches"]["album_id"], [])

    def test_rule_selects_extend_and_keeps_unmatched_column(self) -> None:
        matching = {
            "table_matches": [
                {
                    "target_table": "album",
                    "confidence": 0.75,
                    "column_matches": {
                        "album_id": [
                            {"target_column": "album_id", "confidence": 0.95}
                        ],
                        "title": [
                            {"target_column": "title", "confidence": 0.95}
                        ],
                        "year": [],
                    },
                }
            ]
        }
        result = build_rule_result(
            incoming_schema=self.incoming_schema,
            existing_schema=self.existing_schema,
            existing_constraints={"constraints": {"primary_keys": {}}},
            matching_result=matching,
            thresholds=RuleThresholds(),
        )
        self.assertEqual(result["decision"]["decision_type"], "extend_table")
        self.assertEqual(
            result["column_placements"]["year"]["target_column"], "year"
        )

    def test_insert_requires_complete_column_coverage(self) -> None:
        incoming = {
            "tables": {
                "album": {
                    "columns": {
                        "album_id": {"type": "integer", "nullable": False},
                        "title": {"type": "string", "nullable": False},
                        "year": {"type": "integer", "nullable": True},
                    }
                }
            }
        }
        matching = {
            "table_matches": [
                {
                    "target_table": "album",
                    "confidence": 0.95,
                    "column_matches": {
                        "album_id": [
                            {"target_column": "album_id", "confidence": 0.95}
                        ],
                        "title": [{"target_column": "title", "confidence": 0.95}],
                        "year": [],
                    },
                }
            ]
        }
        result = build_rule_result(
            incoming_schema=incoming,
            existing_schema=self.existing_schema,
            existing_constraints={"constraints": {"primary_keys": {}}},
            matching_result=matching,
            thresholds=RuleThresholds(),
        )
        self.assertEqual(result["decision"]["decision_type"], "extend_table")

    def test_rule_selects_create_when_no_match(self) -> None:
        result = build_rule_result(
            incoming_schema=self.incoming_schema,
            existing_schema=self.existing_schema,
            existing_constraints={"constraints": {"primary_keys": {}}},
            matching_result={"table_matches": []},
            thresholds=RuleThresholds(),
        )
        self.assertEqual(result["decision"]["decision_type"], "create_table")
        self.assertEqual(result["decision"]["target_table"], "music_album")

    def test_create_name_and_primary_key_come_from_identifier(self) -> None:
        incoming = {
            "tables": {
                "invoice_details": {
                    "columns": {
                        "invoice_line_id": {"type": "integer", "nullable": False},
                        "invoice_id": {"type": "integer", "nullable": False},
                    }
                }
            }
        }
        result = build_rule_result(
            incoming_schema=incoming,
            existing_schema=self.existing_schema,
            existing_constraints={"constraints": {"primary_keys": {}}},
            matching_result={"table_matches": []},
            thresholds=RuleThresholds(),
        )
        self.assertEqual(result["decision"]["target_table"], "invoice_line")
        self.assertEqual(result["constraint_signals"][0]["constraint_type"], "primary_key")


if __name__ == "__main__":
    unittest.main()
