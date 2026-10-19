# Raw data-quality observations

Generated from all canonical rows of the frozen source manifest. Conditions may overlap. Counts do not imply automatic deletion or erroneous source data. NULLs are counted separately from comparisons.

| Observation | Yellow | Green |
|---|---:|---:|
| Raw rows | 11077206 | 121853 |
| reversed_timestamps | 5 | 2 |
| nonpositive_distance | 370198 | 4106 |
| negative_fare | 86908 | 336 |
| negative_total | 88580 | 341 |
| pickup_outside_q1 | 10 | 5 |
| unmatched_pickup_zone | 0 | 0 |
| unmatched_dropoff_zone | 0 | 0 |

| Field | Yellow null count (rate) | Green null count (rate) |
|---|---:|---:|
| pickup_at | 0 (0.00000000%) | 0 (0.00000000%) |
| dropoff_at | 0 (0.00000000%) | 0 (0.00000000%) |
| passenger_count | 3057123 (27.59832218%) | 17493 (14.35582218%) |
| trip_distance | 0 (0.00000000%) | 0 (0.00000000%) |
| fare_amount | 0 (0.00000000%) | 0 (0.00000000%) |
| total_amount | 0 (0.00000000%) | 0 (0.00000000%) |
| pickup_zone_id | 0 (0.00000000%) | 0 (0.00000000%) |
| dropoff_zone_id | 0 (0.00000000%) | 0 (0.00000000%) |
| payment_type | 0 (0.00000000%) | 17493 (14.35582218%) |

Project filtering is defined separately in semantic/entities.yaml. All observations above precede that filtering. Negative charges may represent adjustments; no outlier correction is inferred. Reproduce with make build-db.
