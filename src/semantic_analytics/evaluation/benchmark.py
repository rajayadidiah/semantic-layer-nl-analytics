"""Validate benchmark records and execute gold SQL read-only (no expected answers invented)."""

import json
from pathlib import Path

import duckdb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from semantic_analytics.validation.sql import database_schema, validate


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    question: str
    family: str
    answerable: bool
    requires_semantics: bool
    gold_sql: str | None
    notes: str
    difficulty: str = "medium"
    order_sensitive: bool = False
    numeric_tolerance: float = Field(default=1e-6, ge=0)

    @model_validator(mode="after")
    def gold_present(self):
        if self.answerable != bool(self.gold_sql):
            raise ValueError("Only answerable questions must have gold SQL")
        if not self.answerable and self.order_sensitive:
            raise ValueError("Unsupported questions cannot be order-sensitive")
        return self


def load_questions(path=Path("benchmark/questions.jsonl")):
    records = [
        Question.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()
    ]
    if len({q.id for q in records}) != len(records):
        raise ValueError("Duplicate benchmark IDs")
    return records


def verify(con, questions):
    schema = database_schema(con)
    results = []
    for q in questions:
        if not q.answerable:
            results.append({"id": q.id, "status": "unsupported_not_executed"})
            continue
        result = validate(q.gold_sql, schema)
        if not result.valid:
            raise ValueError(f"{q.id}: {result.errors}")
        cursor = con.execute(q.gold_sql)
        count = 0
        while batch := cursor.fetchmany(1000):
            count += len(batch)
        results.append({"id": q.id, "status": "executed", "result_rows": count})
    return results


def main():
    path = Path("data/processed/analytics.duckdb")
    if not path.is_file():
        raise SystemExit("Database absent. Run make build-db first.")
    with duckdb.connect(str(path), read_only=True) as con:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='1GB'")
        results = verify(con, load_questions())
    output = Path("data/processed/benchmark_verification.json")
    output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
