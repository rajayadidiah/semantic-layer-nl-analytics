# Canonical trip model v0.1.0

Implementation: `src/semantic_analytics/transforms/canonical.py`. The mapping was confirmed against
all six downloaded, checksum-verified Q1 2026 schemas. Required columns are checked per file before
building. Yellow has 20 fields, Green 21; 17 names are shared with matching Arrow types. Timestamp
prefixes differ. Airport_fee is Yellow-specific; ehail_fee and trip_type are Green-specific.
All service-specific fields remain available in the raw Parquet sources.
| Canonical field | Yellow source | Green source | DuckDB type |
|---|---|---|---|
| service_type | generated yellow | generated green | VARCHAR |
| source_file | source basename | source basename | VARCHAR |
| pickup_at | tpep_pickup_datetime | lpep_pickup_datetime | TIMESTAMP |
| dropoff_at | tpep_dropoff_datetime | lpep_dropoff_datetime | TIMESTAMP |
| passenger_count | passenger_count | passenger_count | DOUBLE |
| trip_distance | trip_distance | trip_distance | DOUBLE |
| pickup_zone_id | PULocationID | PULocationID | INTEGER |
| dropoff_zone_id | DOLocationID | DOLocationID | INTEGER |
| fare_amount | fare_amount | fare_amount | DOUBLE |
| extra | extra | extra | DOUBLE |
| mta_tax | mta_tax | mta_tax | DOUBLE |
| tip_amount | tip_amount | tip_amount | DOUBLE |
| tolls_amount | tolls_amount | tolls_amount | DOUBLE |
| improvement_surcharge | improvement_surcharge | improvement_surcharge | DOUBLE |
| total_amount | total_amount | total_amount | DOUBLE |
| payment_type | payment_type | payment_type | INTEGER |

Timestamps retain recorded wall-clock values; no timezone conversion or DST inference is made.
Passenger counts use DOUBLE to preserve nulls/fractional anomalies without an integer-rounding
assumption. Financial fields use DOUBLE to preserve source analytical numeric behavior; this is
not a financial ledger. Payment codes remain uninterpreted and service-scoped. No trip primary key
or driver identity is invented. Canonical row counts must equal the sum of source trip row counts.
All rows, including negative amounts and out-of-quarter pickup dates, are retained with provenance.
Fields outside the common core remain in the raw files; see the observed schema comparison. Extra monetary fields are not assumed to exhaust all surcharges;
we do not reconstruct total_amount by summing components.

`taxi_zones` mappings: LocationID → zone_id (INTEGER), Borough → borough, Zone → zone_name,
service_zone → service_zone. The builder requires unique, nonnull zone IDs. Relationships are:

```sql
FROM canonical_trips t
LEFT JOIN taxi_zones pickup_zones ON t.pickup_zone_id = pickup_zones.zone_id
LEFT JOIN taxi_zones dropoff_zones ON t.dropoff_zone_id = dropoff_zones.zone_id
```

Each role is many-to-one and uses its own alias. Left joins preserve unmatched records. A matched
lookup key is different from a project-approved geographic key. The semantic rule
excludes IDs 264/265 as a project decision: the observed lookup labels them N/A (Unknown borough)
and Outside of NYC, respectively.
No valid_trip column/view is exposed to A/C: those cells must not receive semantic conventions
through the physical schema.

## Data quality versus filtering

`database.build.quality` reports, by service, raw rows; reversed timestamps; nonpositive distances;
negative fare and total; out-of-Q1 pickups; unmatched nonnull pickup/dropoff IDs; and count/rate of
nulls for important fields. Conditions involving NULL are measured by the separate null counters.
Anomaly counters may overlap. These are observations, not automatic exclusions or proof of error
(e.g. negative amounts may be adjustments). See [the real quality summary](data_quality.md).

`semantic/*.yaml` defines the separate project valid_trip convention. Only queries explicitly
using that convention filter rows. The rule and metric formulas are versioned project choices. Nonpositive distances occur in both
services, as do negative fares/totals and reversed timestamps. Excluding them is an analytical
convention, not a claim that those raw records are erroneous. Missing passenger counts and payment
codes do not disqualify a trip: they are unnecessary for these initial metrics. Zero fares and
zero-duration trips remain eligible; pickup alone defines quarter membership. Revise definitions
only deliberately, updating their version and dependent gold SQL together.
