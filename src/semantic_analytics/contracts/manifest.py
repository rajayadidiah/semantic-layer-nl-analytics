"""Strict, portable dataset lock; a planned manifest is not a frozen dataset."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Column(BaseModel):
    name: str
    type: str
    nullable: bool


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    filename: str
    service: Literal["yellow", "green", "zones"]
    url: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    size_bytes: int | None = Field(default=None, gt=0)
    row_count: int | None = Field(default=None, ge=0)
    schema_fields: list[Column] = Field(default_factory=list, alias="schema")

    @model_validator(mode="after")
    def safe_paths(self):
        if Path(self.filename).name != self.filename or self.filename in {".", "..", ""}:
            raise ValueError("filename must be a plain relative basename")
        if self.url:
            parsed = urlparse(self.url)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "d37ci6vzurychx.cloudfront.net"
                or parsed.username
                or parsed.port
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("source must be the official HTTPS TLC download host")
        return self


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    version: Literal[1] = 1
    status: Literal["planned", "frozen"] = "planned"
    source_page: Literal["https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page"] = (
        "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page"
    )
    files: list[Source]

    @model_validator(mode="after")
    def complete(self):
        expected = {
            f"{service}_tripdata_2026-{month:02d}.parquet": service
            for service in ("yellow", "green")
            for month in (1, 2, 3)
        } | {"taxi_zone_lookup.csv": "zones"}
        actual = {s.filename: s.service for s in self.files}
        if actual != expected or len(self.files) != 7:
            raise ValueError("manifest must contain exactly the seven Q1 2026 sources")
        if self.status == "frozen" and any(
            s.url is None
            or s.sha256 is None
            or s.size_bytes is None
            or s.row_count is None
            or not s.schema_fields
            for s in self.files
        ):
            raise ValueError("frozen manifest requires all observed metadata")
        return self


def load_manifest(path: Path = Path("data/manifest.yaml")) -> Manifest:
    return Manifest.model_validate(yaml.safe_load(path.read_text()))


def save_manifest(manifest: Manifest, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".yaml.part")
    temporary.write_text(yaml.safe_dump(manifest.model_dump(by_alias=True), sort_keys=False))
    temporary.replace(path)
