# Evaluating Semantic Layers for Reliable Natural-Language Analytics

Northeastern University · CS 5130 master's course project  
Team: Raja Yadidiah Dakey and Karthik Barma

LLMs can produce syntactically plausible analytics SQL while choosing the wrong business
meaning. We study whether explicit semantic definitions and SQL validation improve reliability
on NYC Taxi and Limousine Commission trip records.

## Fixed research design

| Configuration | Semantic definitions | SQL validator |
|---|---|---|
| A | No | No |
| B | Yes | No |
| C | No | Yes |
| D | Yes | Yes |

All cells use identical base instructions and can return `UNSUPPORTED`. Semantics are added only
to B/D. The validator runs once in C/D; there is no LLM repair/retry loop. This is a simple
Text-to-SQL experiment, with no agents, RAG, vector database, frontend, or web service.
`configs/experiment.yaml` freezes this design.

## Phase 2 status (November 18, 2026)

Phase 1 established the frozen official-source pipeline, canonical DuckDB model, data-quality
reporting, versioned semantic conventions, provider interface, SQL validator, and A/B/C/D scaffold.
Phase 2 turns that scaffold into an executable evaluation system and completes the first live
50-question A/B/C/D run.

Implemented and verified in Phase 2:

- The benchmark is expanded from 12 to **50 questions**: 42 answerable gold-SQL cases and
  8 intentionally unsupported cases. Questions carry family, difficulty, order-sensitivity, and
  numeric-tolerance metadata.
- Generated SQL passes through a shared read-only runtime safety gate, executes against DuckDB,
  and returns structured execution outcomes without changing the A/B/C/D experimental validator.
- Result scoring compares generated outputs with gold outputs while handling cosmetic aliases,
  column reordering, optional row-order sensitivity, floating-point tolerance, nulls, and
  result-size limits.
- The A/B/C/D runner records model output, validator status, execution status, correctness,
  latency, and failure category as structured JSONL.
- The reporting module aggregates overall, answerable, unsupported, and semantic accuracy,
  median latency, validator rejections, execution errors, and failure categories.
- An offline rescorer can re-execute saved generated SQL against the gold queries without making
  another model API call.
- CI passes Ruff and **55 non-integration tests**. A dedicated real-data verification run
  downloaded the seven official Q1 files, rebuilt all **11,199,059** trip rows, executed all
  **42 answerable gold queries**, intentionally skipped the 8 unsupported questions, and passed
  the real-data integration test.

### First live 200-run result

The first live experiment ran all 50 questions under A/B/C/D for **200 model calls**. After a
scorer correction described below, the same saved model outputs were re-executed and re-scored
offline.

| Config | Accuracy | Answerable | Unsupported | Semantic | Median ms |
|---|---:|---:|---:|---:|---:|
| A | 74.0% | 69.0% | 100.0% | 0.0% | 2931.6 |
| B | 96.0% | 95.2% | 100.0% | 100.0% | 3227.7 |
| C | 74.0% | 69.0% | 100.0% | 0.0% | 2776.5 |
| D | 92.0% | 90.5% | 100.0% | 81.8% | 3060.3 |

In this run, explicit semantic definitions produced the main accuracy improvement. Adding the
validator alone did not change overall accuracy: A and C both scored 74%. B achieved the highest
accuracy at 96%. D remained high at 92%, but did not outperform B in this single run. This does
not establish that validation is harmful; the validator is intentionally non-repairing and checks
SQL structure/schema rather than business meaning.

All four configurations correctly abstained on all eight unsupported questions.

### Scoring correction

The first summary from the same 200 saved model outputs reported A/B/C/D accuracy of
64% / 90% / 64% / 88%. Manual failure review showed that the scorer could treat equivalent result
sets as different when the model changed both column aliases and SELECT-column order. The scorer
was corrected to test equivalent column permutations for compact result sets, and regression tests
were added. The **same saved model outputs** were then re-executed and re-scored locally with
`make rescore-experiment`; no new model calls were made and the raw model responses were not
changed. The corrected results above are the primary results for this run.

See [failure analysis](docs/failure_analysis.md) for the remaining errors and
[the November progress update](docs/progress_update_nov18.md) for implementation evidence.

## Dataset

Only the [official TLC trip-record page](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
is used to discover download links for:

- Yellow Taxi: January, February, March 2026 (`yellow_tripdata_2026-01/02/03.parquet`).
- Green Taxi: January, February, March 2026 (`green_tripdata_2026-01/02/03.parquet`).
- `taxi_zone_lookup.csv`.

The downloader requires those exact seven basenames on the official page. It never substitutes
another quarter or an unofficial mirror. After the first successful download it records the
observed URL, SHA-256, bytes, rows, and Arrow schema for every source and marks the manifest
`frozen`. Commit that reviewed manifest to freeze the study dataset. Subsequent downloads use its
URLs and reject changed source bytes. An initial freeze cannot be called reproducible until those
actual hashes have been recorded. Downloaded data and generated databases are never committed.

## Reproduce

Use Python 3.11+ from the repository root. Development was tested with Python 3.12.14 on Linux.
Direct dependency versions are pinned in `pyproject.toml`; `requirements.lock` records all installed
runtime/test dependency versions. No API credentials are required for data work, rescoring, or tests.

```sh
git clone https://github.com/rajayadidiah/semantic-layer-nl-analytics.git
cd semantic-layer-nl-analytics
make install
make download-data
make inspect-data
make build-db
make verify-benchmark
make test
make lint
# After setting OPENAI_API_KEY and OPENAI_MODEL:
make smoke-llm
make run-experiment
make summarize-experiment
# Re-score the saved outputs without another API call:
make rescore-experiment
make summarize-rescored
```

`make install` installs the version lock and the editable package. All commands use relative paths.
Data retrieval requires HTTPS access to `www.nyc.gov` and `d37ci6vzurychx.cloudfront.net`; allow
any additional official redirect destination only after inspecting an actual response.
A blocked/missing source is an error, not permission to substitute data. The six Parquet files are
processed by DuckDB with two threads and a 1 GB memory limit; trips are not loaded into a Python
DataFrame. Available disk must accommodate both downloaded files and the materialized database.
Exact source sizes are in the manifest; generated database size depends on DuckDB storage version.

Outputs:

- `docs/schema_comparison.md`: regenerated from verified real source metadata.
- `data/manifest.yaml`: frozen version-controlled source URLs, hashes, sizes, rows, and schemas.
- `data/processed/analytics.duckdb`: `canonical_trips` and `taxi_zones` tables.
- `data/processed/quality_summary.json` and `docs/data_quality.md`: raw anomaly counts and observed
  null rates, no deletion.
- `data/processed/benchmark_verification.json`: query execution status/result row counts,
  not model accuracy or proof of semantic correctness.
- `data/processed/experiment_results.jsonl`: saved live model outputs and original scoring.
- `data/processed/experiment_results_rescored.jsonl`: same saved model outputs after offline
  re-execution and corrected scoring.
- `data/processed/experiment_summary_rescored.json`: corrected aggregate metrics.

The build verifies frozen source checksums, required columns, and unique lookup IDs. Rebuilding
replaces analytical tables transactionally; it preserves all source trip rows with provenance.
The frozen manifest, generated schema report, and quality summary document are tracked in Git.
Large generated data and experiment-output files remain local unless intentionally selected for
version control.

## Analytical conventions and benchmark

[Canonical model](docs/canonical_model.md) documents verified mappings and explicit zone joins.
`semantic/*.yaml` contains project conventions, **not official TLC business definitions**. The
`valid_trip` v0.1.0 rule excludes invalid/missing timestamps, nonpositive distance, negative
fare/total, out-of-Q1 pickup timestamps, unmatched zones, and zone IDs 264/265. These exclusions
apply only when a query asks for the convention. No rows are deleted from canonical storage.

`benchmark/questions.jsonl` has **50 reviewed questions**: 42 answerable gold-SQL cases and
8 deliberately unsupported cases. It includes aggregation, temporal, quality, geographic,
business-semantic, and unsupported families. Benchmark records also carry difficulty,
order-sensitivity, and numeric-tolerance metadata. Raw-record questions have no implicit validity
filter. Unsupported questions cover information absent from the observed TLC schemas, such as
driver salary, fuel expense, rider age, weather effects, driver identity, and dispatch time.

## Baseline and validator

`semantic_analytics.llm.baseline` supplies `Provider`, `FakeProvider`, and `OpenAIProvider`.
`generate(question, schema, provider, semantics=False)` returns a validated JSON SQL/UNSUPPORTED
response. `evaluation.run.run_question` selects A/B/C/D and performs the optional experimental
validator pass. `evaluation.execution` provides the shared runtime read-only safety gate,
`evaluation.scoring` compares executed results against gold outputs,
`evaluation.experiment` runs the complete A/B/C/D benchmark,
`evaluation.rescore` re-scores saved outputs without an LLM call, and
`evaluation.report` aggregates configuration-level metrics and failure categories.

Export `OPENAI_API_KEY` and `OPENAI_MODEL` securely in the shell for live model runs.
There is **no default model** and no automatic `.env` loading. `.env.example` contains names only.
The provider uses one OpenAI HTTPS request and JSON response format. Do not commit secrets or log
credentials.

`validation.sql.validate` uses SQLGlot to check one SELECT, reject writes/DDL, external table scans,
unknown tables and resolvable unknown columns. It supports CTEs, joins, and set queries. This is
the experimental validator used only in C/D. A separate shared runtime guard is used before
execution in every cell so A/B are still protected from writes and external file scans without
receiving the C/D schema validator. Generated SQL executes only through a read-only DuckDB
connection with an output-row limit.

## Tests and CI

```sh
make test
make lint
.venv/bin/python -m pytest -q -m integration
```

CI installs pinned dependencies and runs Ruff plus non-integration pytest checks on Python 3.11;
the current suite reports **55 passing tests** and 1 integration test deselected in ordinary CI.
Tests cover ingestion integrity, canonical transformation, quality counts, semantic definitions,
the 50-question benchmark, result normalization, alias/column-order tolerance, numeric tolerance,
read-only execution, offline rescoring, A/B/C/D routing, validator separation, abstention,
provider protocol, structured reporting, and no automatic retries. A dedicated November 18
verification run also rebuilt the real TLC database and passed the real-data integration test.
CI never contacts a live LLM or stores API credentials.
