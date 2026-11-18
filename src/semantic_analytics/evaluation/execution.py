"""Read-only execution for generated analytics SQL.

The safety check is intentionally narrower than the experimental SQL validator. It is a
runtime guard used in every experimental cell and must not be interpreted as the C/D validator.
"""

from __future__ import annotations

from time import perf_counter

from pydantic import BaseModel
import sqlglot
from sqlglot import exp

from semantic_analytics.validation.sql import ValidationResult


class ExecutionResult(BaseModel):
    status: str
    columns: list[str] = []
    rows: list[list[object]] = []
    row_count: int = 0
    latency_ms: float = 0.0
    error: str | None = None


def execution_safety_check(sql: str) -> ValidationResult:
    """Allow one read-only SELECT/set query and reject writes or external table scans."""
    try:
        statements = sqlglot.parse(sql, read="duckdb")
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.SetOperation)):
            raise ValueError("Exactly one SELECT query is required")
        tree = statements[0]
        forbidden = (exp.DDL, exp.DML, exp.Command, exp.Into)
        if any(isinstance(node, forbidden) for node in tree.walk()):
            raise ValueError("Writes, DDL, and commands are forbidden")
        for table in tree.find_all(exp.Table):
            if not isinstance(table.this, exp.Identifier):
                raise ValueError("External table functions and file scans are forbidden")
        return ValidationResult(valid=True, errors=[])
    except (sqlglot.errors.SqlglotError, ValueError) as exc:
        return ValidationResult(valid=False, errors=[str(exc)])


def execute_read_only(con, sql: str, *, max_rows: int = 10_000) -> ExecutionResult:
    """Execute a safety-checked query on an already read-only DuckDB connection."""
    if max_rows < 1:
        raise ValueError("max_rows must be positive")
    safety = execution_safety_check(sql)
    if not safety.valid:
        return ExecutionResult(
            status="safety_rejected",
            error=safety.errors[0],
        )

    started = perf_counter()
    try:
        cursor = con.execute(sql)
        columns = [item[0] for item in cursor.description or []]
        rows = cursor.fetchmany(max_rows + 1)
        latency_ms = (perf_counter() - started) * 1000
        if len(rows) > max_rows:
            return ExecutionResult(
                status="output_too_large",
                columns=columns,
                row_count=len(rows),
                latency_ms=latency_ms,
                error=f"Query exceeded the {max_rows}-row evaluation limit",
            )
        return ExecutionResult(
            status="success",
            columns=columns,
            rows=[list(row) for row in rows],
            row_count=len(rows),
            latency_ms=latency_ms,
        )
    except Exception as exc:
        return ExecutionResult(
            status="execution_error",
            latency_ms=(perf_counter() - started) * 1000,
            error=str(exc),
        )
