import unittest
from collections import namedtuple

from baselines.traditional.model.matcher import (
    build_table_match,
    normalize_valentine_matches,
    types_compatible,
)
from baselines.traditional.model.rules import (
    OperationThresholds,
    build_rule_result,
)


ColumnPair = namedtuple(
    "ColumnPair",
    "source_table source_column target_table target_column",
)


class TraditionalBaselinesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.incoming_schema = {
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
        self.target_schema = {
            "columns": {
                "album_id": {"type": "integer", "nullable": False},
                "title": {"type": "string", "nullable": False},
            }
        }
        self.existing_schema = {"tables": {"album": self.target_schema}}
        self.constraints = {
            "constraints": {"primary_keys": {"album": ["album_id"]}}
        }

    def test_valentine_results_are_normalized(self) -> None:
        matches = {
            ColumnPair("incoming", "album_id", "album", "album_id"): 0.95,
            ColumnPair("incoming", "title", "album", "title"): 0.85,
        }
        normalized = normalize_valentine_matches(
            matches=matches,
            source_label="incoming",
            target_label="album",
            source_columns=["album_id", "title", "year"],
            incoming_table=self.incoming_schema["tables"]["album"],
            target_schema=self.target_schema,
        )
        self.assertEqual(normalized["album_id"][0]["target_column"], "album_id")
        self.assertEqual(normalized["year"], [])
        table_match = build_table_match(
            target_table="album",
            source_columns=["album_id", "title", "year"],
            column_matches=normalized,
        )
        self.assertAlmostEqual(table_match["confidence"], 0.60)

    def test_incompatible_types_are_rejected(self) -> None:
        self.assertFalse(types_compatible("timestamp", "integer"))
        self.assertTrue(types_compatible("integer", "decimal"))

    def test_partial_key_compatible_match_selects_extend(self) -> None:
        matching = {
            "table_matches": [
                {
                    "target_table": "album",
                    "confidence": 0.60,
                    "column_matches": {
                        "album_id": [
                            {"target_column": "album_id", "confidence": 0.95}
                        ],
                        "title": [{"target_column": "title", "confidence": 0.85}],
                        "year": [],
                    },
                }
            ]
        }
        result = build_rule_result(
            matcher_name="coma",
            incoming_schema=self.incoming_schema,
            existing_schema=self.existing_schema,
            existing_constraints=self.constraints,
            matching_result=matching,
            thresholds=OperationThresholds(),
        )
        self.assertEqual(result["decision"]["decision_type"], "extend_table")
        self.assertTrue(result["rule_evidence"]["key_compatible"])

    def test_related_foreign_key_does_not_imply_table_match(self) -> None:
        matching = {
            "table_matches": [
                {
                    "target_table": "album",
                    "confidence": 0.80,
                    "column_matches": {
                        "album_id": [],
                        "title": [{"target_column": "title", "confidence": 0.90}],
                        "year": [],
                    },
                }
            ]
        }
        result = build_rule_result(
            matcher_name="jl",
            incoming_schema=self.incoming_schema,
            existing_schema=self.existing_schema,
            existing_constraints=self.constraints,
            matching_result=matching,
            thresholds=OperationThresholds(),
        )
        self.assertEqual(result["decision"]["decision_type"], "create_table")


if __name__ == "__main__":
    unittest.main()
