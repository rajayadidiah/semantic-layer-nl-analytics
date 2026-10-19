from io import BytesIO

import pytest

from semantic_analytics.contracts.manifest import load_manifest, save_manifest
from semantic_analytics.ingestion.download import download
from semantic_analytics.ingestion.inspect import inspect


def test_download_freeze_resume_and_verify(tmp_path, fixture_sources, monkeypatch):
    import semantic_analytics.ingestion.download as module

    sources, zones = fixture_sources
    manifest = load_manifest()
    manifest.status = "planned"
    for source in manifest.files:
        source.url = None
        source.sha256 = None
        source.size_bytes = None
        source.row_count = None
        source.schema_fields = []
    lock = tmp_path / "manifest.yaml"
    save_manifest(manifest, lock)
    payloads = {}
    links = {}
    for source in manifest.files:
        url = "https://d37ci6vzurychx.cloudfront.net/" + source.filename
        links[source.filename] = url
        payloads[url] = (
            zones if source.service == "zones" else dict(sources)[source.service]
        ).read_bytes()
    calls = []

    def fake_open(url):
        calls.append(url)
        stream = BytesIO(payloads[url])
        stream.headers = {"Content-Length": str(len(payloads[url]))}
        return stream

    monkeypatch.setattr(module, "discover", lambda url: links)
    monkeypatch.setattr(module, "open_url", fake_open)
    raw = tmp_path / "raw"
    download(lock, raw)
    frozen = load_manifest(lock)
    assert frozen.status == "frozen"
    assert len(calls) == 7
    assert all(s.row_count == (1 if s.service == "zones" else 3) for s in frozen.files)
    before = lock.read_bytes()
    download(lock, raw)
    assert len(calls) == 7
    assert lock.read_bytes() == before
    report = tmp_path / "schemas.md"
    inspect(lock, raw, report)
    assert "tpep_pickup_datetime" in report.read_text()
    assert "lpep_pickup_datetime" in report.read_text()
    target = raw / frozen.files[0].filename
    target.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        download(lock, raw)
    assert target.read_bytes() == b"tampered"


def test_download_http_failure(tmp_path, monkeypatch):
    from urllib.error import HTTPError

    import semantic_analytics.ingestion.download as module

    manifest = load_manifest()
    manifest.status = "planned"
    for source in manifest.files:
        source.sha256 = None
    lock = tmp_path / "manifest.yaml"
    save_manifest(manifest, lock)
    monkeypatch.setattr(
        module,
        "discover",
        lambda url: {
            s.filename: "https://d37ci6vzurychx.cloudfront.net/" + s.filename
            for s in manifest.files
        },
    )

    def fail(url):
        raise HTTPError(url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(module, "open_url", fail)
    with pytest.raises(HTTPError):
        download(lock, tmp_path / "raw")
    assert load_manifest(lock).status == "planned"
    assert not list((tmp_path / "raw").glob("*.part"))


def test_discover_only_official_links(monkeypatch):
    import semantic_analytics.ingestion.download as module

    page = b"""<a href="https://d37ci6vzurychx.cloudfront.net/trip-data/a.parquet">a</a>
    <a href="https://unofficial.example/a.parquet">mirror</a>"""
    monkeypatch.setattr(module, "open_url", lambda _: BytesIO(page))
    links = module.discover("https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page")
    assert links == {"a.parquet": "https://d37ci6vzurychx.cloudfront.net/trip-data/a.parquet"}
