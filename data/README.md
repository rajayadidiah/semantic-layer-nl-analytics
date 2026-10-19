# Official TLC source data

`manifest.yaml` freezes exactly six Q1 2026 trip files and one zone lookup, downloaded from links
on the official TLC trip-record page on October 19, 2026. It records each observed URL, SHA-256,
byte size, row count, and Arrow schema. The six trip files contain 11,199,059 rows total; the zone
lookup contains 265 rows. No downloaded files or generated databases are tracked.
Run from the repository root:

```sh
make download-data
make inspect-data
make build-db
make verify-benchmark
```

The downloader discovers official links on the TLC page, records actual metadata incrementally,
and marks the manifest frozen only after all seven files have been acquired. On interruption,
matching recorded files are verified and skipped. Unknown existing files are preserved and cause
an explicit error; move them aside deliberately before retrying. Do not edit a checksum to accept
changed remote data. A new source revision requires a separately reviewed new freeze.

The lock preserves exact bytes, including any unexpected/out-of-period rows. No raw cleaning is
performed. Arrow schema nullability is not an observed null rate. Quality reports measure actual
canonical nulls/anomalies independently of the project valid-trip rule.

`raw/` and `processed/` are gitignored. Source metadata belongs in Git; datasets, DuckDB files,
quality output, and temporary files do not. The populated manifest and schema report are version-controlled evidence.
The initial network-proxy 403 was resolved before successful downloads; no mirrors were used.
