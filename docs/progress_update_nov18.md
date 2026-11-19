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
policy, and model settings. The main experiment has no automatic LLM repair/retry loop.

## What changed since the October update

The October update had the complete data pipeline, semantic YAML, a 12-question seed benchmark,
a provider interface, a one-pass validator, and A/B/C/D routing. The missing part was the actual
evaluation machinery after generation.

Phase 2 now implements and exercises that missing layer:

1. **50-question benchmark.** The benchmark increased from 12 to 50 questions. Forty-two are
   answerable with reviewed gold SQL and eight are deliberately unsupported. Each record includes
   question family, difficulty, whether project semantics are required, whether output order
   matters, and a numeric tolerance.
2. **Read-only generated-SQL execution.** Model SQL runs through a shared runtime safety check and
   executes on a read-only DuckDB connection. The runtime gate rejects writes, commands, multiple
   statements, and external file/table scans. It remains separate from the C/D experimental
   validator so the independent variable is preserved.
3. **Result scoring.** Gold and generated result sets are compared automatically. The scorer
   tolerates cosmetic aliases, equivalent column reordering, row reordering for non-order-sensitive
   questions, and fixed numeric tolerance.
4. **Executable A/B/C/D runner.** The runner performs generation, optional C/D validation, shared
   runtime safety, execution, scoring, and structured logging for every configuration. Each record
   stores generated SQL or abstention, validator status, execution status, correctness, latency,
   and a failure category.
5. **Offline rescoring.** Saved model outputs can be re-executed and re-scored without another LLM
   API call. This was used after identifying a scorer issue during manual failure review.
6. **Experiment reporting.** A reporting module aggregates overall accuracy, answerable accuracy,
   unsupported-question accuracy, semantic-question accuracy, median latency, validator rejection
   counts, execution errors, and failure-category distributions.
7. **Expanded tests and CI.** The current CI run passes Ruff and 55 non-integration tests.

## Verified technical evidence

| Check | Verified result |
|---|---|
| Ruff | Pass |
| Non-integration pytest | 55 passed, 1 deselected |
| Official TLC download | All 7 frozen sources downloaded successfully |
| Canonical database rebuild | 11,199,059 trip rows |
| Expanded benchmark | 50 questions |
| Answerable gold SQL | 42 / 42 executed successfully on the real database |
| Unsupported cases | 8 / 8 intentionally not executed |
| Real-data integration test | Passed |
| Live experiment | 200 model calls completed |
| Corrected offline rescore | 200 / 200 saved outputs re-scored without new model calls |

## Corrected live experiment result

| Config | Accuracy | Answerable | Unsupported | Semantic | Median ms |
|---|---:|---:|---:|---:|---:|
| A | 74.0% | 69.0% | 100.0% | 0.0% | 2931.6 |
| B | 96.0% | 95.2% | 100.0% | 100.0% | 3227.7 |
| C | 74.0% | 69.0% | 100.0% | 0.0% | 2776.5 |
| D | 92.0% | 90.5% | 100.0% | 81.8% | 3060.3 |

The largest change is associated with semantic definitions. A to B improves overall accuracy by
22 percentage points, while A to C is unchanged. The semantic subset is especially clear:
A and C score 0%, B scores 100%, and D scores 81.8%.

The validator alone did not improve overall result correctness in this run. This is consistent
with its intentionally limited role: it can reject structurally unsafe or schema-invalid SQL but
does not know whether a valid query represents the intended business definition. Because the
experiment has no repair loop, validation also does not trigger automatic correction.

All four configurations scored 100% on the deliberately unsupported questions.

## Scoring correction

The first live summary reported overall A/B/C/D accuracy of 64% / 90% / 64% / 88%. Manual
inspection showed false negatives when the generated query returned equivalent values while
changing both column aliases and SELECT-column order.

The scorer was updated to compare compact result sets across equivalent column permutations when
column names cannot reliably align the outputs. Tests were added for that case. The existing 200
saved model responses were then re-executed and re-scored offline. No model response was edited or
regenerated and no additional API call was made for the corrected result.

The corrected 74% / 96% / 74% / 92% figures are therefore the primary results for this run.

## Qualitative failure analysis

The remaining errors fall into four main groups:

1. **Missing project semantics in A/C.** On business-semantic questions, these cells often abstain
   because the required project convention is intentionally not provided, or they execute a raw
   interpretation without the required validity rules.
2. **Semantic over-application in B/D.** q31 and q35 explicitly ask for recorded/raw Q1 data, but
   the semantics-enabled configurations apply the full `valid_trip` population and answer a
   narrower question.
3. **Ordinary query mistakes.** q25 C adds an extra output column, q26 A omits the zone name, and
   q33 A/C use month/quarter predicates that do not constrain the year to 2026.
4. **Grounded but incorrectly implemented semantics.** q38 D retains an extra raw-population group
   through a filtered aggregate, and q44 D adds a `payment_type IS NOT NULL` condition that is not
   part of the convention.

The detailed review is in [failure_analysis.md](failure_analysis.md).

## Current architecture status

**Implemented and exercised:** official source freezing, schema inspection, canonicalization,
DuckDB storage, quality analysis, semantic YAML, Text-to-SQL provider interface, A/B/C/D routing,
SQLGlot experimental validator, 50-question benchmark, read-only execution safety, result scoring,
experiment logging, offline rescoring, aggregated reporting, automated tests, real-data benchmark
verification, a live 200-call experiment, and qualitative failure review.

## What is not claimed yet

This is one complete live run, not a repeated-measures study. B had the highest observed accuracy
in this run, but the 96% vs 92% B/D difference should not be treated as proof that validation is
harmful. LLM output can vary across runs.

The exact live API model identifier was supplied through `OPENAI_MODEL` at runtime rather than
stored in each result record. It should be confirmed and recorded explicitly in the final methods
section before submission.

## Next milestone

1. Confirm and document the exact live model identifier and relevant API settings.
2. Perform paired/statistical comparison of the configurations where appropriate.
3. Decide whether one repeated run or targeted reruns are needed to assess nondeterminism.
4. Turn the corrected summary and qualitative failures into final charts and report findings.
5. Prepare the final presentation and limitations/discussion sections.
6. If time permits, expand the benchmark beyond 50 questions.
