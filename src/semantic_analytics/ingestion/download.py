"""Discover official links, download safely, and freeze observed source metadata."""

import hashlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pyarrow.csv as csv
import pyarrow.parquet as pq

from semantic_analytics.contracts.manifest import Column, load_manifest, save_manifest


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(value for key, value in attrs if key == "href" and value)


def open_url(url):
    # urllib keeps normal TLS certificate verification enabled.
    return urlopen(Request(url, headers={"User-Agent": "CS5130-TLC-research/0.1"}), timeout=120)


def discover(page_url: str) -> dict[str, str]:
    with open_url(page_url) as response:
        parser = Links()
        parser.feed(response.read().decode("utf-8"))
    result = {}
    for href in parser.links:
        url = urljoin(page_url, href)
        if url.startswith("https://d37ci6vzurychx.cloudfront.net/"):
            name = url.rsplit("/", 1)[-1]
            if name in result and result[name] != url:
                raise ValueError(f"Ambiguous official links for {name}")
            result[name] = url
    return result


def metadata(path: Path, suffix: str | None = None) -> dict:
    if (suffix or path.suffix) == ".parquet":
        parquet = pq.ParquetFile(path)
        schema = parquet.schema_arrow
        count = parquet.metadata.num_rows
    else:
        table = csv.read_csv(path)
        schema, count = table.schema, table.num_rows
    return {
        "sha256": checksum(path),
        "size_bytes": path.stat().st_size,
        "row_count": count,
        "schema_fields": [
            Column(name=f.name, type=str(f.type), nullable=f.nullable) for f in schema
        ],
    }


def verify_file(source, path: Path):
    if not path.is_file() or checksum(path) != source.sha256:
        raise ValueError(f"Missing or checksum-mismatched frozen source: {path}")
    if path.stat().st_size != source.size_bytes:
        raise ValueError(f"File size mismatch: {path}")


def download(manifest_path=Path("data/manifest.yaml"), raw=Path("data/raw")):
    manifest = load_manifest(manifest_path)
    raw.mkdir(parents=True, exist_ok=True)
    links = discover(manifest.source_page) if manifest.status == "planned" else {}
    observed = []
    for source in manifest.files:
        if manifest.status == "planned":
            if source.filename not in links:
                raise ValueError(
                    f"Official TLC page does not link {source.filename}; cannot freeze"
                )
            if source.sha256 and source.url != links[source.filename]:
                raise ValueError(f"Official URL changed during freeze: {source.filename}")
            source.url = links[source.filename]
        target = raw / source.filename
        if target.exists():
            if source.sha256 and checksum(target) == source.sha256:
                verify_file(source, target)
                observed.append(source)
                print(f"Verified existing {source.filename}")
                continue
            if manifest.status == "frozen":
                raise ValueError(f"Checksum mismatch: {target}; preserve/remove it explicitly")
            raise ValueError(f"Untracked existing {target}; preserve/remove it explicitly")
        temporary = raw / (source.filename + ".part")
        try:
            with open_url(source.url) as response, temporary.open("wb") as out:
                expected_length = response.headers.get("Content-Length")
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            if expected_length and temporary.stat().st_size != int(expected_length):
                raise ValueError(f"Incomplete download: {source.filename}")
            if source.sha256 and checksum(temporary) != source.sha256:
                raise ValueError(f"Official source changed: {source.filename}; lock is immutable")
            details = metadata(temporary, suffix=target.suffix)
            if manifest.status == "frozen":
                if details != {k: getattr(source, k) for k in details}:
                    raise ValueError(f"Frozen metadata mismatch: {source.filename}")
            else:
                source = source.model_copy(update=details)
            temporary.replace(target)
            observed.append(source)
            # Checkpoint actual observations for safe resume of an interrupted initial freeze.
            manifest.files = [
                source if s.filename == source.filename else s for s in manifest.files
            ]
            save_manifest(manifest, manifest_path)
            print(f"Downloaded {source.filename}: {source.row_count} rows")
        finally:
            temporary.unlink(missing_ok=True)
    manifest.files = observed
    manifest.status = "frozen"
    # Revalidate after mutable updates.
    manifest = type(manifest).model_validate(manifest.model_dump())
    save_manifest(manifest, manifest_path)


def main():
    try:
        download()
    except Exception as exc:
        raise SystemExit(f"TLC download failed: {exc}") from exc


if __name__ == "__main__":
    main()
