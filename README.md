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
`configs/experiment.yaml` freezes this design. No comparative accuracy results exist yet.

## Phase 1 status (October 19, 2026)

Implemented and verified: frozen official-source downloads, real schema inspection, canonical
DuckDB build (11,199,059 trip records and 265 lookup rows), raw quality reporting, versioned
semantic conventions, 12 benchmark questions, provider interface, single-pass SQL validator,
and the four experimental cells. All 10 answerable gold queries execute against the real database
and synthetic fixtures. Tests and Ruff pass, including the real-data integration test.

The **live LLM remains untested**: neither required OpenAI environment variable was present.
The provider protocol and deterministic fake are tested offline. The final comparative experiment,
advanced semantic validation, and expanded benchmark are later work. See
[the class-update evidence](docs/week1_update.md).

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
runtime/test dependency versions. No API credentials are required for data work or tests.

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

The build verifies frozen source checksums, required columns, and unique lookup IDs. Rebuilding
replaces analytical tables transactionally; it preserves all source trip rows with provenance.
The frozen manifest, generated schema report, and quality summary document are tracked in Git.

## Analytical conventions and benchmark

[Canonical model](docs/canonical_model.md) documents verified mappings and explicit zone joins.
`semantic/*.yaml` contains project conventions, **not official TLC business definitions**. The
`valid_trip` v0.1.0 rule excludes invalid/missing timestamps, nonpositive distance, negative
fare/total, out-of-Q1 pickup timestamps, unmatched zones, and zone IDs 264/265. These exclusions
apply only when a query asks for the convention. No rows are deleted from canonical storage.

`benchmark/questions.jsonl` has 10 answerable gold queries and 2 deliberately unsupported questions.
Three questions explicitly depend on project semantics. Raw-record questions have no implicit
validity filter. Salary/profit inputs are absent from the canonical model, and from all six observed source schemas and the lookup. This is an initial benchmark,
not the final 80–100-question study. No expected real answers have been fabricated.

## Baseline and validator

`semantic_analytics.llm.baseline` supplies `Provider`, `FakeProvider`, and `OpenAIProvider`.
`generate(question, schema, provider, semantics=False)` returns a validated JSON SQL/UNSUPPORTED
response. `evaluation.run.run_question` selects A/B/C/D and performs one optional validation pass;
it does not execute untrusted generated SQL. Obtain the schema with
`validation.sql.database_schema(connection)` from the built DuckDB database.

For a later live smoke test, export `OPENAI_API_KEY` and `OPENAI_MODEL` securely in your shell.
There is **no default model** and no automatic `.env` loading. `.env.example` contains names only.
The provider uses one OpenAI HTTPS request and JSON response format; the selected model must
support Chat Completions JSON output. No live provider compatibility or model quality is claimed.
Do not commit secrets or log credentials. Provider protocol and prompt behavior are tested offline.

`validation.sql.validate` uses SQLGlot to check one SELECT, reject writes/DDL, external table scans,
unknown tables and resolvable unknown columns. It supports CTEs, joins, and set queries. This is
static validation, **not an execution sandbox or advanced semantic validator**. Later execution
needs separate time/resource restrictions and a read-only database connection.

## Tests and CI

```sh
make test                         # synthetic tests plus real integration test (skips if DB absent)
make lint
.venv/bin/python -m pytest -q -m integration  # run after the real-data pipeline
```

CI installs pinned dependencies and runs Ruff and synthetic pytest checks on Python 3.11. It does
not download TLC data or contact an LLM. Tests exercise freezing/idempotency/tamper rejection,
canonical transformation and preserved anomalies, quality counts, semantics, gold queries,
static SQL rejection, shared abstention, provider protocol, and no automatic retries.
