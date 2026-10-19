import json

import pytest

from semantic_analytics.evaluation.run import run_question
from semantic_analytics.llm.baseline import (
    BASE_INSTRUCTIONS,
    FakeProvider,
    OpenAIProvider,
    SQLResponse,
    generate,
)
from semantic_analytics.validation.sql import database_schema, validate


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT service_type, COUNT(*) FROM canonical_trips GROUP BY service_type",
        "WITH t AS (SELECT fare_amount FROM canonical_trips) SELECT AVG(fare_amount) FROM t",
        "SELECT t.pickup_zone_id, z.zone_name FROM canonical_trips t "
        "LEFT JOIN taxi_zones z ON t.pickup_zone_id=z.zone_id",
        "SELECT * FROM canonical_trips UNION ALL SELECT * FROM canonical_trips",
    ],
)
def test_valid_sql(con, sql):
    assert validate(sql, database_schema(con)).valid


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE canonical_trips",
        "DELETE FROM canonical_trips",
        "CREATE TABLE x AS SELECT 1",
        "INSERT INTO canonical_trips SELECT * FROM canonical_trips",
        "COPY canonical_trips TO '/tmp/leak.csv'",
        "SELECT * INTO x FROM canonical_trips",
        "SELECT 1; SELECT 2",
        "SELECT * FROM nonexistent",
        "SELECT salary FROM canonical_trips",
        "SELECT t.salary FROM canonical_trips t",
        "SELECT zone_id FROM canonical_trips",
        "SELECT * FROM read_parquet('other.parquet')",
        "SELECT * FROM information_schema.tables",
        "SELECT (",
    ],
)
def test_invalid_sql(con, sql):
    result = validate(sql, database_schema(con))
    assert not result.valid
    assert result.errors


def fake_sql(sql="SELECT COUNT(*) FROM canonical_trips"):
    return FakeProvider(SQLResponse(status="SQL", sql=sql, reason=None))


def test_fake_provider(con):
    provider = fake_sql()
    response = generate("Count trips", database_schema(con), provider)
    assert response.status == "SQL"
    assert len(provider.calls) == 1
    assert BASE_INSTRUCTIONS in provider.calls[0][0]
    assert "Schema:" in provider.calls[0][0]


def test_shared_instructions_and_no_retry(con):
    prompts = []
    for config in "ABCD":
        provider = fake_sql("SELECT salary FROM canonical_trips")
        result = run_question(config, "Salary?", database_schema(con), provider)
        assert len(provider.calls) == 1
        assert (result["validation"] is not None) == (config in "CD")
        if result["validation"]:
            assert not result["validation"].valid
        prompts.append(provider.calls[0][0])
    assert prompts[0] == prompts[2]
    assert prompts[1] == prompts[3]
    assert all(p.startswith(BASE_INSTRUCTIONS) for p in prompts)
    assert "Project semantic conventions:" not in prompts[0]
    assert "Project semantic conventions:" in prompts[1]


@pytest.mark.parametrize("config", list("ABCD"))
def test_abstention_all_cells(con, config):
    provider = FakeProvider(SQLResponse(status="UNSUPPORTED", sql=None, reason="No salaries"))
    result = run_question(config, "Driver salary?", database_schema(con), provider)
    assert result["response"].status == "UNSUPPORTED"
    assert result["validation"] is None
    assert len(provider.calls) == 1


def test_missing_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-value-not-a-credential")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with pytest.raises(ValueError, match="OPENAI_MODEL"):
        OpenAIProvider()


def test_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "test-only")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIProvider()


def test_live_provider_protocol_without_network(monkeypatch):
    import semantic_analytics.llm.baseline as baseline

    monkeypatch.setenv("OPENAI_API_KEY", "test-value-not-a-credential")
    monkeypatch.setenv("OPENAI_MODEL", "test-only")
    calls = []

    def response(request, timeout):
        from io import BytesIO

        calls.append(json.loads(request.data))
        return BytesIO(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {"status": "UNSUPPORTED", "sql": None, "reason": "Missing data"}
                                )
                            }
                        }
                    ]
                }
            ).encode()
        )

    monkeypatch.setattr(baseline, "urlopen", response)
    result = generate("Salary?", {}, OpenAIProvider())
    assert result.status == "UNSUPPORTED"
    assert calls[0]["model"] == "test-only"
    assert len(calls) == 1
