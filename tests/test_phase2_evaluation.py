import json

from semantic_analytics.evaluation.benchmark import load_questions
from semantic_analytics.evaluation.execution import execute_read_only
from semantic_analytics.evaluation.experiment import run_experiment
from semantic_analytics.evaluation.report import summarize
from semantic_analytics.evaluation.scoring import compare_result_sets


class RoutingProvider:
    def __init__(self):
        self.calls = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if "salary" in user.lower():
            return json.dumps(
                {
                    "status": "UNSUPPORTED",
                    "sql": None,
                    "reason": "Driver salary is not present in the database.",
                }
            )
        return json.dumps(
            {
                "status": "SQL",
                "sql": (
                    "SELECT service_type, COUNT(*) AS records "
                    "FROM canonical_trips GROUP BY service_type ORDER BY service_type"
                ),
                "reason": None,
            }
        )


class BadSQLProvider:
    def complete(self, system: str, user: str) -> str:
        return json.dumps(
            {
                "status": "SQL",
                "sql": "SELECT salary FROM canonical_trips",
                "reason": None,
            }
        )


def test_result_scoring_ignores_row_and_column_order():
    result = compare_result_sets(
        ["zone", "value"],
        [["A", 1.0], ["B", 2.0]],
        ["value", "zone"],
        [[2.0000004, "B"], [1.0000004, "A"]],
        numeric_tolerance=1e-6,
    )
    assert result.correct
    assert result.reason == "match"


def test_result_scoring_respects_required_order():
    result = compare_result_sets(
        ["zone", "value"],
        [["A", 1.0], ["B", 2.0]],
        ["zone", "value"],
        [["B", 2.0], ["A", 1.0]],
        order_sensitive=True,
    )
    assert not result.correct
    assert result.reason == "ordered_value_mismatch"


def test_result_scoring_allows_cosmetic_alias_changes():
    result = compare_result_sets(
        ["zone", "value"],
        [["A", 1.0]],
        ["pickup_zone", "metric"],
        [["A", 1.0]],
    )
    assert result.correct


def test_result_scoring_detects_column_count_mismatch():
    result = compare_result_sets(
        ["zone", "value"],
        [["A", 1.0]],
        ["zone"],
        [["A"]],
    )
    assert not result.correct
    assert result.reason == "column_count_mismatch"


def test_read_only_execution_and_safety_gate(con):
    good = execute_read_only(con, "SELECT COUNT(*) AS records FROM canonical_trips")
    assert good.status == "success"
    assert good.columns == ["records"]
    assert good.rows == [[6]]

    write = execute_read_only(con, "DROP TABLE canonical_trips")
    assert write.status == "safety_rejected"

    external = execute_read_only(con, "SELECT * FROM read_parquet('other.parquet')")
    assert external.status == "safety_rejected"

    unknown_column = execute_read_only(con, "SELECT salary FROM canonical_trips")
    assert unknown_column.status == "execution_error"


def test_full_four_cell_runner_with_correct_sql_and_abstention(con):
    questions = load_questions()
    selected = [
        next(question for question in questions if question.id == "q01"),
        next(question for question in questions if question.id == "q11"),
    ]
    provider = RoutingProvider()
    records = run_experiment(con, selected, provider)

    assert len(records) == 8
    assert len(provider.calls) == 8
    assert all(record.correct for record in records)
    assert {record.configuration for record in records} == set("ABCD")
    summary = summarize(records)
    assert all(summary[configuration]["accuracy"] == 1.0 for configuration in "ABCD")


def test_validator_is_experimental_while_runtime_safety_is_shared(con):
    question = next(question for question in load_questions() if question.id == "q01")
    records = run_experiment(con, [question], BadSQLProvider())
    by_configuration = {record.configuration: record for record in records}

    assert by_configuration["A"].failure_category == "execution_error"
    assert by_configuration["B"].failure_category == "execution_error"
    assert by_configuration["C"].failure_category == "validator_rejected"
    assert by_configuration["D"].failure_category == "validator_rejected"
    assert by_configuration["A"].validator_enabled is False
    assert by_configuration["C"].validator_enabled is True
