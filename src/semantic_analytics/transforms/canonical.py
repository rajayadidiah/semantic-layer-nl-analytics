"""Mappings verified against all six frozen Q1 2026 schemas.

Required-column checks prevent silent schema drift.
"""

COMMON = {
    "passenger_count": "DOUBLE",
    "trip_distance": "DOUBLE",
    "PULocationID": "INTEGER",
    "DOLocationID": "INTEGER",
    "fare_amount": "DOUBLE",
    "extra": "DOUBLE",
    "mta_tax": "DOUBLE",
    "tip_amount": "DOUBLE",
    "tolls_amount": "DOUBLE",
    "improvement_surcharge": "DOUBLE",
    "total_amount": "DOUBLE",
    "payment_type": "INTEGER",
}
RENAMES = {"PULocationID": "pickup_zone_id", "DOLocationID": "dropoff_zone_id"}


def mapping(service: str) -> dict[str, tuple[str, str]]:
    if service not in {"yellow", "green"}:
        raise ValueError(f"Unknown service: {service}")
    prefix = "tpep" if service == "yellow" else "lpep"
    return {
        "pickup_at": (f"{prefix}_pickup_datetime", "TIMESTAMP"),
        "dropoff_at": (f"{prefix}_dropoff_datetime", "TIMESTAMP"),
        **{RENAMES.get(name, name): (name, kind) for name, kind in COMMON.items()},
    }


def quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def canonical_select(service: str, filename: str, columns: set[str]) -> str:
    fields = mapping(service)
    missing = {source for source, _ in fields.values()} - columns
    if missing:
        raise ValueError(f"{service}: required columns missing: {sorted(missing)}")
    expressions = [f"{quote(service)} AS service_type", f"{quote(filename)} AS source_file"]
    expressions += [
        f'CAST("{source}" AS {kind}) AS "{target}"' for target, (source, kind) in fields.items()
    ]
    return "SELECT " + ", ".join(expressions)
