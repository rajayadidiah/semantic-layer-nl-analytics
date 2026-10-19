"""Versioned project conventions, deliberately separate from the raw database."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    rule: str
    required_fields: list[str]
    applicable_service_types: list[str]
    exclusions: list[str]
    default_time_dimension: str | None
    version: str


def load_definitions(directory=Path("semantic")) -> dict[str, Definition]:
    definitions = {}
    for path in sorted(directory.glob("*.yaml")):
        for item in yaml.safe_load(path.read_text())["definitions"]:
            definition = Definition.model_validate(item)
            if definition.name in definitions:
                raise ValueError(f"Duplicate semantic name: {definition.name}")
            definitions[definition.name] = definition
    if not definitions:
        raise ValueError("No semantic definitions loaded")
    return definitions
