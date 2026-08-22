from __future__ import annotations

import unittest

from experiments.constraint_filter.model.constraint_filter import (
    filter_constraints_to_tables,
)


class ConstraintFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.constraints = {
            "database": "example",
            "constraints": {
                "primary_keys": {
                    "invoice": ["invoice_id"],
                    "customer": ["customer_id"],
                    "track": ["track_id"],
                },
                "foreign_keys": {
                    "invoice": [
                        {
                            "columns": ["customer_id"],
                            "referenced_table": "customer",
                            "referenced_columns": ["customer_id"],
                        }
                    ],
                    "invoice_line": [
                        {
                            "columns": ["invoice_id"],
                            "referenced_table": "invoice",
                            "referenced_columns": ["invoice_id"],
                        },
                        {
                            "columns": ["track_id"],
                            "referenced_table": "track",
                            "referenced_columns": ["track_id"],
                        },
                    ],
                },
                "unique_constraints": {},
                "check_constraints": {"track": [["unit_price"]]},
                "indexes": {
                    "invoice": [["customer_id"]],
                    "track": [["album_id"]],
                },
                "inferred_constraints": {},
            },
        }

    def test_filters_table_scoped_sections(self) -> None:
        result = filter_constraints_to_tables(
            self.constraints,
            {"invoice", "customer"},
        )
        body = result["constraints"]

        self.assertEqual(
            set(body["primary_keys"]),
            {"invoice", "customer"},
        )
        self.assertEqual(set(body["indexes"]), {"invoice"})
        self.assertEqual(body["check_constraints"], {})

    def test_keeps_only_foreign_keys_with_both_endpoints_selected(self) -> None:
        result = filter_constraints_to_tables(
            self.constraints,
            {"invoice", "customer", "invoice_line"},
        )
        body = result["constraints"]

        self.assertEqual(set(body["foreign_keys"]), {"invoice", "invoice_line"})
        self.assertEqual(
            len(body["foreign_keys"]["invoice_line"]),
            1,
        )
        self.assertEqual(
            body["foreign_keys"]["invoice_line"][0]["referenced_table"],
            "invoice",
        )

    def test_does_not_mutate_input(self) -> None:
        filter_constraints_to_tables(self.constraints, {"invoice"})

        self.assertIn(
            "track",
            self.constraints["constraints"]["primary_keys"],
        )


if __name__ == "__main__":
    unittest.main()
