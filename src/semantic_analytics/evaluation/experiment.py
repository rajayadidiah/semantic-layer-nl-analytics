"""End-to-end A/B/C/D benchmark execution and structured logging."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

import duckdb
from pydantic import BaseModel

from semantic_analytics.evaluation.benchmark import Question, load_questions
from semantic_analytics.evaluation.execution import ExecutionResult, execute_read_only
from semantic_analytics.evaluation.run import run_question
from semantic_analytics.evaluation.scoring import compare_result_sets
from semantic_analytics.llm.baseline import OpenAIProvider, Provider
from semantic_analytics.validation.sql import database_schema


class ExperimentRecord(BaseModel):
    question_id: str
    configuration: str
    family: str
    answerable: bool
    requires_semantics: bool
    semantics_enabled: bool
    validator_enabled: bool
    model_status: str
    generated_sql: str | None
    model_reason: str | None
    model_latency_ms: float
    validator_valid: bool | None
    validation_errors: list[str]
    execution_status: str | None
    execution_latency_ms: float | None
    correct: bool
    comparison_reason: str
    failure_category: str


def _failure_category(
    question: Question,
    model_status: str,
    execution: ExecutionResult | None,
    correct: bool,
    validator_valid: bool | None,
) -> str:
    if correct:
        return "correct"
    if model_status == "UNSUPPORTED":
        return "incorrect_abstention"
    if not question.answerable:
        return "unsupported_hallucination"
    if validator_valid is False:
        return "validator_rejected"
    if execution is None:
        return "not_executed"
    if execution.status == "safety_rejected":
        return "safety_rejected"
    if execution.status == "execution_error":
        return "execution_error"
    if execution.status == "output_too_large":
        return "output_too_large"
    return "semantic_result_mismatch" if question.requires_semantics else "wrong_result"


def run_one(
    configuration: str,
    question: Question,
    con,
    provider: Provider,
    *,
    gold: ExecutionResult | None,
    schema: dict[str, dict[str, str]],
) -> ExperimentRecord:
    started = perf_counter()
    model = run_question(configuration, question.question, schema, provider)
    model_latency_ms = (perf_counter() - started) * 1000
    response = model["response"]
    validation = model["validation"]
    semantics_enabled = configuration in {"B", "D"}
    validator_enabled = configuration in {"C", "D"}
    validator_valid = validation.valid if validation is not None else None
    validation_errors = validation.errors if validation is not None else []

    execution = None
    correct = False
    comparison_reason = "not_scored"

    if response.status == "UNSUPPORTED":
        correct = not question.answerable
        comparison_reason = "correct_abstention" if correct else "answerable_question_abstained"
    elif validation is not None and not validation.valid:
        comparison_reason = "experimental_validator_rejected"
    else:
        execution = execute_read_only(con, response.sql)
        if not question.answerable:
            comparison_reason = "unanswerable_question_returned_sql"
        elif execution.status != "success":
            comparison_reason = execution.status
        elif gold is None or gold.status != "success":
            raise ValueError(f"{question.id}: gold execution unavailable")
        else:
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

    return ExperimentRecord(
        question_id=question.id,
        configuration=configuration,
        family=question.family,
        answerable=question.answerable,
        requires_semantics=question.requires_semantics,
        semantics_enabled=semantics_enabled,
        validator_enabled=validator_enabled,
        model_status=response.status,
        generated_sql=response.sql,
        model_reason=response.reason,
        model_latency_ms=model_latency_ms,
        validator_valid=validator_valid,
        validation_errors=validation_errors,
        execution_status=execution.status if execution is not None else None,
        execution_latency_ms=execution.latency_ms if execution is not None else None,
        correct=correct,
        comparison_reason=comparison_reason,
        failure_category=_failure_category(
            question,
            response.status,
            execution,
            correct,
            validator_valid,
        ),
    )


def run_experiment(
    con,
    questions: list[Question],
    provider: Provider,
    *,
    configurations: tuple[str, ...] = ("A", "B", "C", "D"),
) -> list[ExperimentRecord]:
    schema = database_schema(con)
    gold_cache: dict[str, ExecutionResult] = {}
    for question in questions:
        if question.answerable:
            gold = execute_read_only(con, question.gold_sql)
            if gold.status != "success":
                raise ValueError(
                    f"{question.id}: gold SQL did not execute successfully: {gold.error}"
                )
            gold_cache[question.id] = gold

    records = []
    for question in questions:
        for configuration in configurations:
            records.append(
                run_one(
                    configuration,
                    question,
                    con,
                    provider,
                    gold=gold_cache.get(question.id),
                    schema=schema,
                )
            )
    return records


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
        "--output",
        type=Path,
        default=Path("data/processed/experiment_results.jsonl"),
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--configurations",
        nargs="+",
        choices=list("ABCD"),
        default=list("ABCD"),
    )
    args = parser.parse_args()

    questions = load_questions(args.benchmark)
    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("--limit must be positive")
        questions = questions[: args.limit]

    provider = OpenAIProvider()
    with duckdb.connect(str(args.database), read_only=True) as con:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='1GB'")
        records = run_experiment(
            con,
            questions,
            provider,
            configurations=tuple(args.configurations),
        )
    write_jsonl(records, args.output)
    print(f"Wrote {len(records)} experiment records to {args.output}")


if __name__ == "__main__":
    main()
