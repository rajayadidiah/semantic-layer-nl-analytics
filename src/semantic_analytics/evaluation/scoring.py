"""Result comparison utilities for gold-vs-generated analytics outputs."""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
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


def compare_result_sets(
    gold_columns: list[str],
    gold_rows: list[list[object]],
    actual_columns: list[str],
    actual_rows: list[list[object]],
    *,
    order_sensitive: bool = False,
    numeric_tolerance: float = 1e-6,
) -> ComparisonResult:
    """Compare two result sets while allowing column reordering and numeric tolerance."""
    if numeric_tolerance < 0:
        raise ValueError("numeric_tolerance must be nonnegative")

    gold_keys = [_column_key(name) for name in gold_columns]
    actual_keys = [_column_key(name) for name in actual_columns]
    if len(set(gold_keys)) != len(gold_keys) or len(set(actual_keys)) != len(actual_keys):
        return ComparisonResult(
            correct=False,
            reason="duplicate_column_names",
            gold_row_count=len(gold_rows),
            actual_row_count=len(actual_rows),
        )
    if set(gold_keys) != set(actual_keys):
        return ComparisonResult(
            correct=False,
            reason="column_mismatch",
            gold_row_count=len(gold_rows),
            actual_row_count=len(actual_rows),
        )

    actual_index = {name: index for index, name in enumerate(actual_keys)}
    reordered_actual = [
        [row[actual_index[name]] for name in gold_keys]
        for row in actual_rows
    ]

    if len(gold_rows) != len(reordered_actual):
        return ComparisonResult(
            correct=False,
            reason="row_count_mismatch",
            gold_row_count=len(gold_rows),
            actual_row_count=len(actual_rows),
        )

    normalized_gold = [list(row) for row in gold_rows]
    if order_sensitive:
        correct = all(
            _rows_equal(gold, actual, numeric_tolerance)
            for gold, actual in zip(normalized_gold, reordered_actual, strict=True)
        )
        return ComparisonResult(
            correct=correct,
            reason="match" if correct else "ordered_value_mismatch",
            gold_row_count=len(gold_rows),
            actual_row_count=len(actual_rows),
        )

    unmatched = list(range(len(reordered_actual)))
    for gold in normalized_gold:
        match = next(
            (
                index
                for index in unmatched
                if _rows_equal(gold, reordered_actual[index], numeric_tolerance)
            ),
            None,
        )
        if match is None:
            return ComparisonResult(
                correct=False,
                reason="value_mismatch",
                gold_row_count=len(gold_rows),
                actual_row_count=len(actual_rows),
            )
        unmatched.remove(match)

    return ComparisonResult(
        correct=True,
        reason="match",
        gold_row_count=len(gold_rows),
        actual_row_count=len(actual_rows),
    )
