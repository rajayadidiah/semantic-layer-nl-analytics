"""Result comparison utilities for gold-vs-generated analytics outputs."""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from itertools import permutations
from numbers import Number

from pydantic import BaseModel


class ComparisonResult(BaseModel):
    correct: bool
    reason: str
    gold_row_count: int
    actual_row_count: int


def _column_key(name: str) -> str:
    return name.strip().lower()


def _is_number(value: object) -> bool:
    return isinstance(value, (Number, Decimal)) and not isinstance(value, bool)


def _values_equal(left: object, right: object, tolerance: float) -> bool:
    if left is None or right is None:
        return left is right
    if _is_number(left) and _is_number(right):
        left_value = float(left)
        right_value = float(right)
        if math.isnan(left_value) or math.isnan(right_value):
            return math.isnan(left_value) and math.isnan(right_value)
        return math.isclose(
            left_value,
            right_value,
            rel_tol=tolerance,
            abs_tol=tolerance,
        )
    if isinstance(left, (date, datetime)) and isinstance(right, (date, datetime)):
        return left.isoformat() == right.isoformat()
    if isinstance(left, str) and isinstance(right, str):
        return left.strip() == right.strip()
    return left == right


def _rows_equal(left: list[object], right: list[object], tolerance: float) -> bool:
    return len(left) == len(right) and all(
        _values_equal(a, b, tolerance) for a, b in zip(left, right, strict=True)
    )


def _result_rows_match(
    gold_rows: list[list[object]],
    actual_rows: list[list[object]],
    *,
    order_sensitive: bool,
    numeric_tolerance: float,
) -> bool:
    if order_sensitive:
        return all(
            _rows_equal(gold, actual, numeric_tolerance)
            for gold, actual in zip(gold_rows, actual_rows, strict=True)
        )

    unmatched = list(range(len(actual_rows)))
    for gold in gold_rows:
        match = next(
            (
                index
                for index in unmatched
                if _rows_equal(gold, actual_rows[index], numeric_tolerance)
            ),
            None,
        )
        if match is None:
            return False
        unmatched.remove(match)
    return True


def _candidate_column_orders(
    gold_keys: list[str],
    actual_keys: list[str],
) -> list[tuple[int, ...]]:
    """Return deterministic actual-column permutations worth comparing.

    Exact unique-name alignment is preferred. When aliases differ, column names are
    treated as cosmetic and every permutation is considered for small analytical
    result sets. This lets equivalent SQL score correctly when a model changes both
    aliases and SELECT-column order.

    The benchmark uses compact result schemas. The cap prevents factorial growth if
    this helper is reused on an unexpectedly wide query.
    """
    width = len(actual_keys)
    identity = tuple(range(width))

    names_are_unique = (
        len(set(gold_keys)) == len(gold_keys)
        and len(set(actual_keys)) == len(actual_keys)
    )
    if names_are_unique and set(gold_keys) == set(actual_keys):
        actual_index = {name: index for index, name in enumerate(actual_keys)}
        return [tuple(actual_index[name] for name in gold_keys)]

    if width <= 6:
        return list(permutations(range(width)))

    return [identity]


def compare_result_sets(
    gold_columns: list[str],
    gold_rows: list[list[object]],
    actual_columns: list[str],
    actual_rows: list[list[object]],
    *,
    order_sensitive: bool = False,
    numeric_tolerance: float = 1e-6,
) -> ComparisonResult:
    """Compare result values while tolerating cosmetic aliases and column order."""
    if numeric_tolerance < 0:
        raise ValueError("numeric_tolerance must be nonnegative")

    gold_keys = [_column_key(name) for name in gold_columns]
    actual_keys = [_column_key(name) for name in actual_columns]
    if len(gold_keys) != len(actual_keys):
        return ComparisonResult(
            correct=False,
            reason="column_count_mismatch",
            gold_row_count=len(gold_rows),
            actual_row_count=len(actual_rows),
        )

    if len(gold_rows) != len(actual_rows):
        return ComparisonResult(
            correct=False,
            reason="row_count_mismatch",
            gold_row_count=len(gold_rows),
            actual_row_count=len(actual_rows),
        )

    normalized_gold = [list(row) for row in gold_rows]
    for order in _candidate_column_orders(gold_keys, actual_keys):
        reordered_actual = [[row[index] for index in order] for row in actual_rows]
        if _result_rows_match(
            normalized_gold,
            reordered_actual,
            order_sensitive=order_sensitive,
            numeric_tolerance=numeric_tolerance,
        ):
            return ComparisonResult(
                correct=True,
                reason="match",
                gold_row_count=len(gold_rows),
                actual_row_count=len(actual_rows),
            )

    return ComparisonResult(
        correct=False,
        reason="ordered_value_mismatch" if order_sensitive else "value_mismatch",
        gold_row_count=len(gold_rows),
        actual_row_count=len(actual_rows),
    )
