"""Materialize canonical tables without loading trips into Python memory."""

import json
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from semantic_analytics.contracts.manifest import load_manifest
from semantic_analytics.ingestion.download import verify_file
from semantic_analytics.transforms.canonical import canonical_select, quote


def build_database(sources, zones: Path, output: Path):
    """sources is a sequence of (service, Parquet path); also used by synthetic tests."""
    output.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(output))
    try:
        con.execute("SET threads = 2")
        con.execute("SET memory_limit = '1GB'")
        con.execute("BEGIN TRANSACTION")
        zone_columns = {
            r[0]
            for r in con.execute(
                f"DESCRIBE SELECT * FROM read_csv_auto({quote(str(zones))})"
            ).fetchall()
        }
        if not {"LocationID", "Borough", "Zone", "service_zone"} <= zone_columns:
            raise ValueError("Zone lookup lacks required columns")
        con.execute(f"""CREATE OR REPLACE TABLE taxi_zones AS SELECT
            CAST(LocationID AS INTEGER) AS zone_id, Borough AS borough, Zone AS zone_name,
            service_zone FROM read_csv_auto({quote(str(zones))})""")
        counts = con.execute("SELECT count(*), count(DISTINCT zone_id) FROM taxi_zones").fetchone()
        if counts[0] != counts[1]:
            raise ValueError("Zone IDs must be nonnull and unique; joins would multiply rows")
        selects = []
        for service, path in sources:
            select = canonical_select(service, path.name, set(pq.read_schema(path).names))
            selects.append(select + f" FROM read_parquet({quote(str(path))})")
        if not selects:
            raise ValueError("No trip sources supplied")
        con.execute("CREATE OR REPLACE TABLE canonical_trips AS " + " UNION ALL ".join(selects))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def quality(con) -> dict:
    observations = {}
    for (service,) in con.execute("SELECT DISTINCT service_type FROM canonical_trips").fetchall():
        where = f" FROM canonical_trips t WHERE service_type={quote(service)}"
        total = con.execute("SELECT count(*)" + where).fetchone()[0]
        rules = {
            "reversed_timestamps": "pickup_at > dropoff_at",
            "nonpositive_distance": "trip_distance <= 0",
            "negative_fare": "fare_amount < 0",
            "negative_total": "total_amount < 0",
            "pickup_outside_q1": "pickup_at < TIMESTAMP '2026-01-01' "
            "OR pickup_at >= TIMESTAMP '2026-04-01'",
            "unmatched_pickup_zone": "pickup_zone_id IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM taxi_zones z WHERE z.zone_id=t.pickup_zone_id)",
            "unmatched_dropoff_zone": "dropoff_zone_id IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM taxi_zones z WHERE z.zone_id=t.dropoff_zone_id)",
        }
        anomalies = {
            name: con.execute("SELECT count(*)" + where + f" AND ({rule})").fetchone()[0]
            for name, rule in rules.items()
        }
        columns = [
            "pickup_at",
            "dropoff_at",
            "passenger_count",
            "trip_distance",
            "fare_amount",
            "total_amount",
            "pickup_zone_id",
            "dropoff_zone_id",
            "payment_type",
        ]
        nulls = {}
        for col in columns:
            count = con.execute("SELECT count(*)" + where + f" AND {col} IS NULL").fetchone()[0]
            nulls[col] = {"count": count, "rate": count / total if total else None}
        observations[service] = {"rows": total, "anomalies": anomalies, "nulls": nulls}
    return {"scope": "all raw rows; no filtering or deletion", "services": observations}


def quality_markdown(report):
    lines = [
        "# Raw data-quality observations",
        "",
        "Generated from all canonical rows of the frozen source manifest. Conditions may "
        "overlap. Counts do not imply automatic deletion or erroneous source data. "
        "NULLs are counted separately from comparisons.",
        "",
        "| Observation | Yellow | Green |",
        "|---|---:|---:|",
    ]
    services = report["services"]
    lines.append(f"| Raw rows | {services['yellow']['rows']} | {services['green']['rows']} |")
    for name in services["yellow"]["anomalies"]:
        lines.append(
            f"| {name} | {services['yellow']['anomalies'][name]} | "
            f"{services['green']['anomalies'][name]} |"
        )
    lines += [
        "",
        "| Field | Yellow null count (rate) | Green null count (rate) |",
        "|---|---:|---:|",
    ]
    for name in services["yellow"]["nulls"]:
        cells = []
        for service in ["yellow", "green"]:
            item = services[service]["nulls"][name]
            rate = f"{item['rate']:.8%}" if item["rate"] is not None else "N/A"
            cells.append(f"{item['count']} ({rate})")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Project filtering is defined separately in semantic/entities.yaml. "
        "All observations above precede that filtering. Negative charges may represent "
        "adjustments; no outlier correction is inferred. Reproduce with make build-db.",
    ]
    return "\n".join(lines) + "\n"


def main():
    manifest = load_manifest()
    if manifest.status != "frozen":
        raise SystemExit("Dataset is not frozen. Run make download-data first.")
    for source in manifest.files:
        verify_file(source, Path("data/raw") / source.filename)
    build_database(
        [
            (s.service, Path("data/raw") / s.filename)
            for s in manifest.files
            if s.service != "zones"
        ],
        Path("data/raw/taxi_zone_lookup.csv"),
        Path("data/processed/analytics.duckdb"),
    )
    with duckdb.connect("data/processed/analytics.duckdb", read_only=True) as con:
        report = quality(con)
    Path("data/processed/quality_summary.json").write_text(json.dumps(report, indent=2) + "\n")
    Path("docs/data_quality.md").write_text(quality_markdown(report))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
