from datetime import datetime
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from semantic_analytics.database.build import build_database
from semantic_analytics.transforms.canonical import mapping

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fixture_sources(tmp_path):
    sources = []
    for service in ("yellow", "green"):
        data = {}
        for canonical, (source, kind) in mapping(service).items():
            if kind == "TIMESTAMP":
                value = datetime(2026, 1, 1, 12 if canonical == "pickup_at" else 13)
                data[source] = pa.array([value, value, None], type=pa.timestamp("us"))
            elif kind == "INTEGER":
                data[source] = pa.array([1, 999, None], type=pa.int32())
            else:
                data[source] = pa.array([2.0, -1.0, None], type=pa.float64())
        path = tmp_path / f"{service}.parquet"
        pq.write_table(pa.table(data), path)
        sources.append((service, path))
    zones = tmp_path / "zones.csv"
    zones.write_text("LocationID,Borough,Zone,service_zone\n1,Manhattan,Example,Yellow Zone\n")
    return sources, zones


@pytest.fixture
def con(fixture_sources, tmp_path):
    sources, zones = fixture_sources
    path = tmp_path / "fixture.duckdb"
    build_database(sources, zones, path)
    with duckdb.connect(str(path)) as connection:
        yield connection
