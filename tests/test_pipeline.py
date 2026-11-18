import hashlib
from pathlib import Path

import duckdb
import pytest
from pydantic import ValidationError

from semantic_analytics.contracts.manifest import Manifest, Source, load_manifest
from semantic_analytics.database.build import build_database, quality
from semantic_analytics.evaluation.benchmark import Question, load_questions, verify
from semantic_analytics.ingestion.download import checksum, metadata
from semantic_analytics.semantics.loader import load_definitions
from semantic_analytics.transforms.canonical import canonical_select, mapping


def test_manifest():
    manifest = load_manifest()
    assert len(manifest.files) == 7
    assert {s.service for s in manifest.files} == {"yellow", "green", "zones"}
    assert Manifest.model_validate(manifest.model_dump()) == manifest


def test_manifest_not_falsely_frozen():
    manifest = load_manifest().model_dump()
    for source in manifest["files"]:
        source["sha256"] = None
    manifest["status"] = "frozen"
    with pytest.raises(ValidationError):
        Manifest.model_validate(manifest)


@pytest.mark.parametrize("filename,url", [("../escape", None), ("a", "https://example.com/a")])
def test_manifest_safety(filename, url):
    with pytest.raises(ValidationError):
        Source(filename=filename, service="zones", url=url)


def test_checksum(tmp_path):
    path = tmp_path / "bytes"
    path.write_bytes(b"abc")
    assert checksum(path) == hashlib.sha256(b"abc").hexdigest()


def test_schema_metadata(fixture_sources):
    sources, _ = fixture_sources
    observed = metadata(sources[0][1])
    assert observed["row_count"] == 3
    assert observed["size_bytes"] > 0
    assert observed["schema_fields"][0].name == "tpep_pickup_datetime"


@pytest.mark.parametrize("service,prefix", [("yellow", "tpep"), ("green", "lpep")])
def test_mapping(service, prefix):
    fields = mapping(service)
    assert fields["pickup_at"] == (prefix + "_pickup_datetime", "TIMESTAMP")
    assert fields["pickup_zone_id"][0] == "PULocationID"
    with pytest.raises(ValueError, match="required columns"):
        canonical_select(service, "fixture.parquet", set())


def test_canonical_preserves_anomalies(con):
    assert con.execute("SELECT count(*) FROM canonical_trips").fetchone()[0] == 6
    assert (
        con.execute("SELECT count(*) FROM canonical_trips WHERE fare_amount < 0").fetchone()[0] == 2
    )
    assert con.execute(
        "SELECT DISTINCT pickup_zone_id FROM canonical_trips ORDER BY 1"
    ).fetchall() == [(1,), (999,), (None,)]


def test_quality(con):
    report = quality(con)["services"]["yellow"]
    assert report["rows"] == 3
    assert report["anomalies"]["negative_fare"] == 1
    assert report["anomalies"]["unmatched_pickup_zone"] == 1
    assert report["nulls"]["pickup_at"] == {"count": 1, "rate": 1 / 3}


def test_zone_uniqueness(fixture_sources, tmp_path):
    sources, zones = fixture_sources
    zones.write_text(zones.read_text() + "1,Queens,Duplicate,Green Zone\n")
    with pytest.raises(ValueError, match="unique"):
        build_database(sources, zones, tmp_path / "bad.duckdb")
    with duckdb.connect(str(tmp_path / "bad.duckdb")) as db:
        assert db.execute("SHOW TABLES").fetchall() == []


def test_semantic_definitions(con):
    definitions = load_definitions()
    assert {
        "valid_trip",
        "trip_volume",
        "average_fare",
        "average_trip_distance",
        "pickup_geography",
        "dropoff_geography",
    } <= definitions.keys()
    valid = definitions["valid_trip"].rule
    assert con.execute("SELECT count(*) FROM canonical_trips WHERE " + valid).fetchone() == (2,)
    for name in ["trip_volume", "average_fare", "average_trip_distance"]:
        sql = "SELECT " + definitions[name].rule + " FROM canonical_trips"
        assert con.execute(sql).fetchone() == (2,)


def test_benchmark_parse_and_verify(con):
    questions = load_questions()
    assert len(questions) == 50
    assert sum(not q.answerable for q in questions) == 8
    results = verify(con, questions)
    assert sum(r["status"] == "executed" for r in results) == 42
    semantic = next(q for q in questions if q.id == "q07")
    assert con.execute(semantic.gold_sql).fetchall() == [("green", 1), ("yellow", 1)]


def test_benchmark_invalid():
    with pytest.raises(ValidationError):
        Question(
            id="x",
            question="?",
            family="x",
            answerable=True,
            requires_semantics=False,
            gold_sql=None,
            notes="",
        )


@pytest.mark.integration
def test_real_dataset():
    path = Path("data/processed/analytics.duckdb")
    if not path.exists():
        pytest.skip("Real TLC data/database not available")
    manifest = load_manifest()
    assert manifest.status == "frozen"
    with duckdb.connect(str(path), read_only=True) as db:
        assert db.execute("SELECT count(*) FROM canonical_trips").fetchone()[0] == sum(
            s.row_count for s in manifest.files if s.service != "zones"
        )
        assert sum(r["status"] == "executed" for r in verify(db, load_questions())) == 42


def test_valid_trip_boundaries_and_missing_fields(con):
    rule = load_definitions()["valid_trip"].rule
    # Mutate only one synthetic service so each convention is independently exercised.
    base = " FROM canonical_trips WHERE service_type='yellow' AND fare_amount=2"
    assert con.execute("SELECT (" + rule + ")" + base).fetchone() == (True,)
    for column, value in [
        ("dropoff_at", "TIMESTAMP '2025-12-31'"),
        ("pickup_at", "TIMESTAMP '2026-04-01'"),
        ("trip_distance", "0"),
        ("pickup_zone_id", "264"),
        ("dropoff_zone_id", "999"),
        ("fare_amount", "-1"),
        ("total_amount", "NULL"),
    ]:
        con.execute("BEGIN")
        try:
            con.execute(
                f"UPDATE canonical_trips SET {column}={value} "
                "WHERE service_type='yellow' AND fare_amount=2"
            )
            assert con.execute(
                "SELECT count(*) FROM canonical_trips "
                "WHERE service_type='yellow' AND (" + rule + ")"
            ).fetchone() == (0,)
        finally:
            con.execute("ROLLBACK")


def test_semantic_benchmark_uses_versioned_rule():
    rule = load_definitions()["valid_trip"].rule
    for question in load_questions():
        if question.requires_semantics:
            assert rule in question.gold_sql
