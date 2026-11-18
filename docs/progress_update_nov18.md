# November 18, 2026 project progress update

## Project goal

The project evaluates whether two engineering interventions improve the reliability of
LLM-generated analytics SQL over NYC TLC data: explicit semantic definitions and a static SQL
validator. The controlled design remains the same 2 × 2 experiment:

| Configuration | Semantic definitions | Experimental validator |
|---|---|---|
| A | No | No |
| B | Yes | No |
| C | No | Yes |
| D | Yes | Yes |

All configurations use the same database, benchmark questions, base instructions, abstention
policy, and model settings. The main experiment still has no automatic LLM repair/retry loop.

## What changed since the October update

The October update had the complete data pipeline, semantic YAML, a 12-question seed benchmark,
a provider interface, a one-pass validator, and A/B/C/D routing. The missing part was the actual
evaluation machinery after generation.

Phase 2 now implements that missing layer:

1. **50-question benchmark.** The benchmark increased from 12 to 50 questions. Forty-two are
   answerable with reviewed gold SQL and eight are deliberately unsupported. Each record now
   includes question family, difficulty, whether project semantics are required, whether output
   order matters, and a numeric tolerance.
2. **Read-only generated-SQL execution.** Model SQL can now be run through a shared runtime safety
   check and executed on a read-only DuckDB connection. The runtime gate rejects writes, commands,
   multiple statements, and external file/table scans. It is deliberately separate from the C/D
   experimental validator so the independent variable is preserved.
3. **Result scoring.** Gold and generated result sets are compared automatically. The scorer
   normalizes column names, permits column reordering when the same columns are returned, ignores
   row order unless the benchmark marks a question as order-sensitive, and uses a fixed numeric
   tolerance for floating-point values.
4. **Executable A/B/C/D runner.** The runner now performs generation, optional C/D validation,
   shared runtime safety, execution, scoring, and structured logging for every configuration.
   Each record stores generated SQL or abstention, validator status, execution status, correctness,
   latency, and a failure category.
5. **Experiment reporting.** A reporting module aggregates overall accuracy, answerable accuracy,
   unsupported-question accuracy, semantic-question accuracy, median latency, validator rejection
   counts, execution errors, and failure-category distributions.
6. **Expanded tests and CI.** Phase 2 added tests for scorer behavior, numeric tolerance,
   order-sensitive results, execution safety, full four-cell routing, correct abstention, and the
   distinction between the shared runtime guard and the C/D experimental validator.

## Verified technical evidence

The final Phase 2 verification succeeded in GitHub Actions.

| Check | Verified result |
|---|---|
| Ruff | Pass |
| Non-integration pytest | 52 passed, 1 deselected |
| Official TLC download | All 7 frozen sources downloaded successfully |
| Canonical database rebuild | 11,199,059 trip rows |
| Expanded benchmark | 50 questions |
| Answerable gold SQL | 42 / 42 executed successfully on the real database |
| Unsupported cases | 8 / 8 intentionally not executed |
| Real-data integration test | 1 passed, 52 deselected |

CI also caught two implementation mistakes during development: an import-order lint error and a
malformed semantic gold-query construction. Both were fixed before the final green run. This is
useful evidence that the update is being tested rather than only documented.

## Current architecture status

**Implemented:** official source freezing, schema inspection, canonicalization, DuckDB storage,
quality analysis, semantic YAML, Text-to-SQL provider interface, A/B/C/D routing, SQLGlot
experimental validator, 50-question benchmark, read-only execution safety, result scoring,
experiment logging, aggregated reporting, automated tests, and real-data benchmark verification.

**Remaining:** live model smoke test, complete live A/B/C/D run, repeated runs where output is
nondeterministic, quantitative comparison of the four cells, statistical comparison where
appropriate, and deeper qualitative failure analysis.

## What is not claimed yet

No live model has been called in this repository and no comparative A/B/C/D accuracy or latency
numbers exist yet. The code requires `OPENAI_API_KEY` and `OPENAI_MODEL` to be supplied securely
at runtime. Phase 2 makes the full experiment executable once those credentials are available, but
the progress update should not report fabricated model results.

## Next milestone

1. Run a five-question live smoke test covering a simple aggregation, a geographic query, a
   semantic-definition question, a difficult/invalid-SQL case, and an unsupported question.
2. Freeze the selected live model and settings.
3. Run all 50 questions under A/B/C/D for 200 primary model calls.
4. Generate the configuration summary and failure-category report.
5. Repeat selected or all runs if nondeterminism is material, then perform paired comparison and
   qualitative analysis.
6. If time permits, expand the benchmark beyond 50 before the final study.
