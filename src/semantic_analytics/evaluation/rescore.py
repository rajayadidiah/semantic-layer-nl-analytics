"""Re-score saved model outputs without making new LLM API calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

from semantic_analytics.evaluation.benchmark import Question, load_questions
from semantic_analytics.evaluation.execution import ExecutionResult, execute_read_only
from semantic_analytics.evaluation.experiment import ExperimentRecord, _failure_category
from semantic_analytics.evaluation.scoring import compare_result_sets


def load_records(path: Path) -> list[ExperimentRecord]:
    return [
        ExperimentRecord.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def rescore_records(
    con,
    questions: list[Question],
    records: list[ExperimentRecord],
) -> list[ExperimentRecord]:
    """Re-execute saved SQL and re-score it against gold outputs.

    This function never calls an LLM provider. Model outputs, model latency, and
    validator results are preserved exactly as recorded in the original run.
    """
    question_by_id = {question.id: question for question in questions}
    gold_cache: dict[str, ExecutionResult] = {}

    for question in questions:
        if question.answerable:
            gold = execute_read_only(con, question.gold_sql)
            if gold.status != "success":
                raise ValueError(
                    f"{question.id}: gold SQL did not execute successfully: {gold.error}"
                )
            gold_cache[question.id] = gold

    rescored: list[ExperimentRecord] = []
    for record in records:
        question = question_by_id.get(record.question_id)
        if question is None:
            raise ValueError(f"Unknown benchmark question in saved results: {record.question_id}")

        execution = None
        correct = False
        comparison_reason = "not_scored"

        if record.model_status == "UNSUPPORTED":
            correct = not question.answerable
            comparison_reason = (
                "correct_abstention" if correct else "answerable_question_abstained"
            )
        elif record.validator_valid is False:
            comparison_reason = "experimental_validator_rejected"
        elif not record.generated_sql:
            comparison_reason = "missing_generated_sql"
        else:
            execution = execute_read_only(con, record.generated_sql)
            if not question.answerable:
                comparison_reason = "unanswerable_question_returned_sql"
            elif execution.status != "success":
                comparison_reason = execution.status
            else:
                gold = gold_cache.get(question.id)
                if gold is None or gold.status != "success":
                    raise ValueError(f"{question.id}: gold execution unavailable")
                comparison = compare_result_sets(
                    gold.columns,
                    gold.rows,
                    execution.columns,
                    execution.rows,
                    order_sensitive=question.order_sensitive,
                    numeric_tolerance=question.numeric_tolerance,
                )
                correct = comparison.correct
                comparison_reason = comparison.reason

        rescored.append(
            record.model_copy(
                update={
                    "execution_status": execution.status if execution is not None else None,
                    "execution_latency_ms": (
                        execution.latency_ms if execution is not None else None
                    ),
                    "correct": correct,
                    "comparison_reason": comparison_reason,
                    "failure_category": _failure_category(
                        question,
                        record.model_status,
                        execution,
                        correct,
                        record.validator_valid,
                    ),
                }
            )
        )

    return rescored


def write_jsonl(records: list[ExperimentRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record.model_dump(mode="json")) + "\n" for record in records)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/processed/analytics.duckdb"),
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("benchmark/questions.jsonl"),
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/experiment_results.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/experiment_results_rescored.jsonl"),
    )
    args = parser.parse_args()

    questions = load_questions(args.benchmark)
    records = load_records(args.input)

    with duckdb.connect(str(args.database), read_only=True) as con:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='1GB'")
        rescored = rescore_records(con, questions, records)

    write_jsonl(rescored, args.output)
    print(
        f"Re-scored {len(rescored)} saved experiment records without API calls "
        f"and wrote {args.output}"
    )


if __name__ == "__main__":
    main()
