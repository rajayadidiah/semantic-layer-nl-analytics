"""Single-pass, conservative static SQL checks; this is not a security sandbox."""

from collections.abc import Mapping

import sqlglot
from pydantic import BaseModel
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str]


def validate(sql: str, schema: Mapping[str, Mapping[str, str]]) -> ValidationResult:
    try:
        statements = sqlglot.parse(sql, read="duckdb")
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.SetOperation)):
            raise ValueError("Exactly one SELECT query is required")
        tree = statements[0]
        forbidden = (exp.DDL, exp.DML, exp.Command, exp.Into)
        if any(isinstance(node, forbidden) for node in tree.walk()):
            raise ValueError("Writes, DDL, and commands are forbidden")
        # Reject table functions and external file scans as well as unknown tables.
        ctes = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
        known = {name.lower() for name in schema}
        for table in tree.find_all(exp.Table):
            if not isinstance(table.this, exp.Identifier):
                raise ValueError("Table functions and external scans are unsupported")
            if table.db or table.catalog or table.name.lower() not in known | ctes:
                raise ValueError(f"Unknown table: {table.sql()}")
        qualify(
            tree.copy(),
            dialect="duckdb",
            schema=dict(schema),
            validate_qualify_columns=True,
            quote_identifiers=False,
        )
        return ValidationResult(valid=True, errors=[])
    except (sqlglot.errors.SqlglotError, ValueError) as exc:
        return ValidationResult(valid=False, errors=[str(exc)])


def database_schema(con) -> dict[str, dict[str, str]]:
    return {
        table: {name: kind for name, kind, *_ in con.execute(f'DESCRIBE "{table}"').fetchall()}
        for table in ("canonical_trips", "taxi_zones")
    }
