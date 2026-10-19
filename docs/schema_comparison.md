# Observed TLC schemas

Generated from checksum-verified local files. Arrow nullable is schema metadata, not an observed null count; see the separate quality report for actual null rates.

## yellow_tripdata_2026-01.parquet

Rows: 3724889; bytes: 64165080

| Column | Arrow type | Nullable metadata |
|---|---|---|
| VendorID | int32 | True |
| tpep_pickup_datetime | timestamp[us] | True |
| tpep_dropoff_datetime | timestamp[us] | True |
| passenger_count | int64 | True |
| trip_distance | double | True |
| RatecodeID | int64 | True |
| store_and_fwd_flag | large_string | True |
| PULocationID | int32 | True |
| DOLocationID | int32 | True |
| payment_type | int64 | True |
| fare_amount | double | True |
| extra | double | True |
| mta_tax | double | True |
| tip_amount | double | True |
| tolls_amount | double | True |
| improvement_surcharge | double | True |
| total_amount | double | True |
| congestion_surcharge | double | True |
| Airport_fee | double | True |
| cbd_congestion_fee | double | True |

## yellow_tripdata_2026-02.parquet

Rows: 3399866; bytes: 58683353

| Column | Arrow type | Nullable metadata |
|---|---|---|
| VendorID | int32 | True |
| tpep_pickup_datetime | timestamp[us] | True |
| tpep_dropoff_datetime | timestamp[us] | True |
| passenger_count | int64 | True |
| trip_distance | double | True |
| RatecodeID | int64 | True |
| store_and_fwd_flag | large_string | True |
| PULocationID | int32 | True |
| DOLocationID | int32 | True |
| payment_type | int64 | True |
| fare_amount | double | True |
| extra | double | True |
| mta_tax | double | True |
| tip_amount | double | True |
| tolls_amount | double | True |
| improvement_surcharge | double | True |
| total_amount | double | True |
| congestion_surcharge | double | True |
| Airport_fee | double | True |
| cbd_congestion_fee | double | True |

## yellow_tripdata_2026-03.parquet

Rows: 3952451; bytes: 67891249

| Column | Arrow type | Nullable metadata |
|---|---|---|
| VendorID | int32 | True |
| tpep_pickup_datetime | timestamp[us] | True |
| tpep_dropoff_datetime | timestamp[us] | True |
| passenger_count | int64 | True |
| trip_distance | double | True |
| RatecodeID | int64 | True |
| store_and_fwd_flag | large_string | True |
| PULocationID | int32 | True |
| DOLocationID | int32 | True |
| payment_type | int64 | True |
| fare_amount | double | True |
| extra | double | True |
| mta_tax | double | True |
| tip_amount | double | True |
| tolls_amount | double | True |
| improvement_surcharge | double | True |
| total_amount | double | True |
| congestion_surcharge | double | True |
| Airport_fee | double | True |
| cbd_congestion_fee | double | True |

## green_tripdata_2026-01.parquet

Rows: 40272; bytes: 991656

| Column | Arrow type | Nullable metadata |
|---|---|---|
| VendorID | int32 | True |
| lpep_pickup_datetime | timestamp[us] | True |
| lpep_dropoff_datetime | timestamp[us] | True |
| store_and_fwd_flag | large_string | True |
| RatecodeID | int64 | True |
| PULocationID | int32 | True |
| DOLocationID | int32 | True |
| passenger_count | int64 | True |
| trip_distance | double | True |
| fare_amount | double | True |
| extra | double | True |
| mta_tax | double | True |
| tip_amount | double | True |
| tolls_amount | double | True |
| ehail_fee | double | True |
| improvement_surcharge | double | True |
| total_amount | double | True |
| payment_type | int64 | True |
| trip_type | int64 | True |
| congestion_surcharge | double | True |
| cbd_congestion_fee | double | True |

## green_tripdata_2026-02.parquet

Rows: 37373; bytes: 920753

| Column | Arrow type | Nullable metadata |
|---|---|---|
| VendorID | int32 | True |
| lpep_pickup_datetime | timestamp[us] | True |
| lpep_dropoff_datetime | timestamp[us] | True |
| store_and_fwd_flag | large_string | True |
| RatecodeID | int64 | True |
| PULocationID | int32 | True |
| DOLocationID | int32 | True |
| passenger_count | int64 | True |
| trip_distance | double | True |
| fare_amount | double | True |
| extra | double | True |
| mta_tax | double | True |
| tip_amount | double | True |
| tolls_amount | double | True |
| ehail_fee | double | True |
| improvement_surcharge | double | True |
| total_amount | double | True |
| payment_type | int64 | True |
| trip_type | int64 | True |
| congestion_surcharge | double | True |
| cbd_congestion_fee | double | True |

## green_tripdata_2026-03.parquet

Rows: 44208; bytes: 1082530

| Column | Arrow type | Nullable metadata |
|---|---|---|
| VendorID | int32 | True |
| lpep_pickup_datetime | timestamp[us] | True |
| lpep_dropoff_datetime | timestamp[us] | True |
| store_and_fwd_flag | large_string | True |
| RatecodeID | int64 | True |
| PULocationID | int32 | True |
| DOLocationID | int32 | True |
| passenger_count | int64 | True |
| trip_distance | double | True |
| fare_amount | double | True |
| extra | double | True |
| mta_tax | double | True |
| tip_amount | double | True |
| tolls_amount | double | True |
| ehail_fee | double | True |
| improvement_surcharge | double | True |
| total_amount | double | True |
| payment_type | int64 | True |
| trip_type | int64 | True |
| congestion_surcharge | double | True |
| cbd_congestion_fee | double | True |

## taxi_zone_lookup.csv

Rows: 265; bytes: 12331

| Column | Arrow type | Nullable metadata |
|---|---|---|
| LocationID | int64 | True |
| Borough | string | True |
| Zone | string | True |
| service_zone | string | True |

## Cross-service comparison

Shared names: DOLocationID, PULocationID, RatecodeID, VendorID, cbd_congestion_fee, congestion_surcharge, extra, fare_amount, improvement_surcharge, mta_tax, passenger_count, payment_type, store_and_fwd_flag, tip_amount, tolls_amount, total_amount, trip_distance

Yellow-only names: Airport_fee, tpep_dropoff_datetime, tpep_pickup_datetime

Green-only names: ehail_fee, lpep_dropoff_datetime, lpep_pickup_datetime, trip_type

Type differences:
- No type differences among shared column names in these files.

Monthly missing fields:
- yellow_tripdata_2026-01.parquet: []
- yellow_tripdata_2026-02.parquet: []
- yellow_tripdata_2026-03.parquet: []
- green_tripdata_2026-01.parquet: []
- green_tripdata_2026-02.parquet: []
- green_tripdata_2026-03.parquet: []

The canonical mapping treats tpep/lpep timestamp prefixes as the same pickup/dropoff concepts, subject to required-column validation. Similar names do not establish identical business meaning. The research problem is semantic ambiguity; this report does not imply unrelated or chaotic schemas.
