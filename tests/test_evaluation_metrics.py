from evaluation.aggregate_result import summarize_dataset_results
from evaluation.evaluator import compute_task_state_metrics
from evaluation.metrics import (
    compute_fact_set_metrics,
    extract_constraint_facts,
    extract_schema_facts,
)


def test_fact_set_metrics_handles_empty_and_mismatch() -> None:
    assert compute_fact_set_metrics(set(), set())["exact_match"] is True
    result = compute_fact_set_metrics({("a", 1)}, {("a", 1), ("b", 2)})
    assert result["precision"] == 1.0
    assert result["recall"] == 0.5
    assert result["exact_match"] is False


def test_schema_and_constraint_fact_extraction() -> None:
    rdb = {
        "schema": {
            "tables": {
                "customer": {
                    "columns": {"id": {"type": "integer"}},
                    "column_order": ["id"],
                }
            }
        },
        "constraints": {
            "constraints": {
                "primary_keys": {"customer": ["id"]},
                "foreign_keys": {},
            }
        },
    }
    assert ("table", "customer") in extract_schema_facts(rdb)
    assert ("primary_key", "customer", ("id",)) in extract_constraint_facts(rdb)


def test_malformed_foreign_key_is_counted_without_crashing() -> None:
    rdb = {
        "schema": {
            "tables": {
                "child": {"columns": {}},
                "parent": {"columns": {}},
            }
        },
        "constraints": {
            "constraints": {
                "primary_keys": {},
                "foreign_keys": {
                    "child": [
                        {
                            "columns": ["parent_id"],
                            "referenced_table": "parent",
                            "referenced_columns": None,
                        }
                    ]
                },
            }
        },
    }
    assert (
        "foreign_key",
        "child",
        ("parent_id",),
        "parent",
        None,
    ) in extract_constraint_facts(rdb)


def test_task_state_retry_metrics() -> None:
    result = compute_task_state_metrics(
        {
            "status": "succeeded",
            "results": {
                "validating": [
                    {"route": "evolutor", "issues": ["bad mapping"]},
                    {"route": "decision", "issues": []},
                ]
            },
        }
    )
    assert result["pipeline_succeeded"] is True
    assert result["retry_count"] == 1
    assert result["retried"] is True
    assert result["retry_exhausted"] is False


def test_aggregate_new_metrics() -> None:
    rows = [
        {
            "evaluation_status": "evaluated",
            "decision_reference": "create_table",
            "decision_predicted": "extend_table",
            "decision_correct": False,
            "target_table_applicable": False,
            "column_placement_true_positive": 1,
            "column_placement_false_positive": 0,
            "column_placement_false_negative": 0,
            "column_placement_precision": 1.0,
            "column_placement_recall": 1.0,
            "column_placement_f1": 1.0,
            "proposal_fact_true_positive": 1,
            "proposal_fact_false_positive": 1,
            "proposal_fact_false_negative": 1,
            "proposal_fact_precision": 0.5,
            "proposal_fact_recall": 0.5,
            "proposal_fact_f1": 0.5,
            "operation_only_fact_true_positive": 1,
            "operation_only_fact_false_positive": 0,
            "operation_only_fact_false_negative": 1,
            "operation_only_fact_precision": 1.0,
            "operation_only_fact_recall": 0.5,
            "operation_only_fact_f1": 2 / 3,
            "operation_only_fact_exact_match": False,
            "run_pipeline_succeeded": True,
            "run_validator_call_count": 2,
            "run_retry_count": 1,
            "run_retried": True,
            "run_retry_exhausted": False,
        }
    ]
    summary = summarize_dataset_results(rows)
    assert summary["decision_create_to_extend_rate"] == 1.0
    assert summary["column_placement_exact_match_rate"] == 1.0
    assert summary["wrong_decision_useful_action_rate"] == 1.0
    assert summary["validator_retry_rate"] == 1.0
