# October 21 project update — verified October 19, 2026

**Evaluating Semantic Layers for Reliable Natural-Language Analytics**
Northeastern University CS 5130
Raja Yadidiah Dakey · Karthik Barma

## Implemented

The Phase 1 offline pipeline works end to end: official TLC link discovery and streaming downloads,
SHA-256 freeze, real schema inspection, canonical transformation, DuckDB materialization, raw
quality reporting, versioned semantic conventions, and executable seed benchmark. The Python
package includes pinned dependencies, a transitive version lock, Make commands, pytest, Ruff,
and synthetic-data GitHub Actions configuration. Local verification used Python 3.12.14 on Linux;
CI is configured for Python 3.11 but its hosted run has not yet been observed.

## Actual frozen data

All seven files were downloaded from links discovered on the official TLC trip-record page.
`data/manifest.yaml` records each exact HTTPS URL, SHA-256, byte size, row count, and Arrow schema.
The initial proxy 403 was resolved before the successful download; no mirrors were used.
A second download invocation checksum-verified and skipped all seven existing files.

| Downloaded file | Rows | Bytes |
|---|---:|---:|
| yellow_tripdata_2026-01.parquet | 3,724,889 | 64,165,080 |
| yellow_tripdata_2026-02.parquet | 3,399,866 | 58,683,353 |
| yellow_tripdata_2026-03.parquet | 3,952,451 | 67,891,249 |
| green_tripdata_2026-01.parquet | 40,272 | 991,656 |
| green_tripdata_2026-02.parquet | 37,373 | 920,753 |
| green_tripdata_2026-03.parquet | 44,208 | 1,082,530 |
| taxi_zone_lookup.csv | 265 | 12,331 |

There are **11,199,059 trip records**: 11,077,206 Yellow and 121,853 Green. Canonical storage
retains all of them, including records whose pickup timestamps fall outside Q1. Raw files and
DuckDB databases are gitignored; the source metadata is version-controlled.

## Real schema findings and canonical model

All three months have a stable schema within each service. Yellow has 20 columns; Green has 21.
Seventeen column names are shared, with identical Arrow types. Pickup/dropoff timestamp names
use `tpep_` for Yellow and `lpep_` for Green; both are timestamp[us]. Yellow-specific `Airport_fee`
and Green-specific `ehail_fee`/`trip_type` remain outside the common core. There are no type
differences among shared names or monthly missing fields in these files. Arrow nullable flags
are true throughout, which does not mean every field actually has nulls.

The canonical model maps timestamps, service/provenance, passenger count, distance, zone IDs,
payment code, and common monetary fields. Pickup/dropoff zone relationships use separate
many-to-one left joins against a unique, nonnull zone key. The model and mapping are documented
in `docs/canonical_model.md`; full observed schemas are in `docs/schema_comparison.md`.
The schemas are substantially similar; the research difficulty is semantic ambiguity.

## Observed quality versus project conventions

`docs/data_quality.md` is generated from the real database. Examples (raw rows, before filtering):

| Observation | Yellow | Green |
|---|---:|---:|
| Pickup later than dropoff | 5 | 2 |
| Nonpositive trip distance | 370,198 | 4,106 |
| Negative base fare | 86,908 | 336 |
| Negative total amount | 88,580 | 341 |
| Pickup outside Q1 | 10 | 5 |
| Nonnull pickup/dropoff keys absent from lookup | 0 / 0 | 0 / 0 |
| Missing passenger_count | 3,057,123 (27.59832218%) | 17,493 (14.35582218%) |
| Missing payment_type | 0 | 17,493 (14.35582218%) |

Anomaly categories overlap. Negative charges may reflect adjustments; they are observations,
not a license to erase records. No cleaning or automatic deletion is performed.

Four semantic YAML files define six analytical concepts: valid_trip, trip_volume, average_fare,
average_trip_distance, pickup_geography, dropoff_geography, plus a relationship definition.
Each includes name, description, rule, required fields, services, exclusions, time dimension,
and version. These are **project conventions, not official TLC definitions**.

Version 0.1.0 valid_trip requires ordered nonnull timestamps, pickup in Q1, positive distance,
nonnegative base fare/total, and matched zone IDs excluding 264/265. The actual lookup labels
those IDs N/A (Unknown borough) and Outside of NYC. Missing passenger/payment codes are not
exclusions for these metrics. The rule admits 10,560,806 Yellow and 116,354 Green records;
these are deterministic project-filter counts, not model results. Canonical storage remains unfiltered.

## Benchmark, baseline, validator, and fixed experiment

The seed benchmark contains **12 questions**: 10 answerable gold SQL queries and 2 unsupported
questions. All 10 gold queries execute on both synthetic fixtures and the real canonical database.
Three questions explicitly depend on project conventions. All six observed raw schemas and the
zone lookup lack driver identifiers/salaries and fuel, insurance, or wage expense inputs; salary
and operating-profit questions therefore cannot be answered from this dataset. Gold execution
establishes SQL operability, not final adjudication of scientific correctness.

The baseline supplies a provider protocol, deterministic fake, strict SQL/UNSUPPORTED JSON
response validation, and an OpenAI HTTP adapter using only OPENAI_API_KEY and OPENAI_MODEL.
There is no model default. **No live LLM call was made** because neither variable was present.
Tests exercise the fake and mocked HTTP protocol, shared instructions, abstention in all cells,
and exactly one provider call. No live model compatibility or baseline accuracy is claimed.

The SQLGlot validator performs one parse/check pass and returns structured errors for non-SELECT,
writes/DDL, multiple statements, external table scans, unknown tables, and resolvable unknown columns.
CTEs, joins, and UNION are tested. It is not an execution sandbox or an advanced semantic checker.
Generated model SQL is not automatically executed. No LLM retry/repair or agent framework exists.

| Configuration | Semantics | Validator |
|---|---|---|
| A | No | No |
| B | Yes | No |
| C | No | Yes |
| D | Yes | Yes |

`configs/experiment.yaml` encodes the unchanged 2 × 2 design. All four cells receive identical
base instructions and permission to abstain. Only B/D receive semantic definitions; only C/D
run the single-pass validator. No comparative accuracy, cost, latency, or significance results exist.

## Validation evidence

| Command | Observed outcome |
|---|---|
| `make install` | Successful, including reinstall from requirements.lock |
| `make download-data` | Seven downloaded; repeat verified/skipped all seven |
| `make inspect-data` | Observed schemas compared and report generated |
| `make build-db` | Successful; all 11,199,059 trip rows retained; quality summary generated |
| `make verify-benchmark` | 10 gold queries executed; 2 unsupported records intentionally not executed |
| `make test` | 47 passed, no failures or skips, including real integration |
| `.venv/bin/python -m pytest -q -m 'not integration'` | 46 passed, 1 deselected |
| `make lint` | All Ruff checks passed |
| `.venv/bin/pip check` | No broken requirements |

The integration test checks canonical row count against the frozen manifest and executes all
answerable gold queries. Ordinary CI uses synthetic data and never downloads TLC files or calls
an LLM. A source-data freeze, database build, and gold-query execution are not an LLM evaluation.

## Limitations and next milestone

- Live provider/model compatibility and live Text-to-SQL output remain untested. Configure the two
  OpenAI environment variables securely and the API network destination for one labeled smoke test.
- The 12-question benchmark is intentionally small. Expand later toward the planned 80–100 questions,
  review gold SQL independently, and freeze scoring/abstention rules before comparative runs.
- Static validation is initial; advanced semantic checks and restricted generated-query execution
  remain later work. The full A/B/C/D evaluation has not been run.
- Analytical conventions are versioned choices. Discuss zero fares/durations, missingness, outliers,
  and geographic exclusions before freezing the final study protocol. No official TLC interpretation
  is implied by our metric definitions.

## Suggested three-slide outline (five minutes)

**Slide 1 — Problem + data (one minute).** Plausible SQL can answer the wrong business question.
Show the official Q1 2026 Yellow/Green dataset and zone lookup: 11.2 million trip records.
Emphasize substantial schema overlap and genuine semantic ambiguity.

**Slide 2 — Method + actual implementation (two minutes).** Show the fixed 2 × 2 table, shared
abstention, and one validator pass. Show the working freeze → canonical DuckDB → semantic YAML →
12-question gold verification pipeline, with 47 passing tests. State that the live LLM and final
comparative results are later work.

**Slide 3 — Open question + feedback (two minutes).** Should business-semantic questions be
scored separately from questions with one objectively determined database answer? How should
principled abstention be scored when a configuration lacks the needed convention? Next: independent
gold review, a labeled live smoke test, and an expanded benchmark/scoring protocol.
