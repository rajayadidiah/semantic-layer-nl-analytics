"""One provider call, shared abstention rules, no agent or automatic SQL repair."""

import json
import os
from typing import Literal, Protocol
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, model_validator

from semantic_analytics.semantics.loader import load_definitions

BASE_INSTRUCTIONS = """Translate one analytics question into DuckDB SELECT SQL.
Use only the supplied schema. Do not invent data or columns. You may abstain in every
configuration: return UNSUPPORTED if this database cannot answer the question.
Return exactly one JSON object: {"status":"SQL","sql":"SELECT ...","reason":null}
or {"status":"UNSUPPORTED","sql":null,"reason":"why the data is insufficient"}.
Never write data, use external files, or output multiple statements.
If a question requires an undefined business convention, abstain rather than invent it."""


class SQLResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["SQL", "UNSUPPORTED"]
    sql: str | None
    reason: str | None

    @model_validator(mode="after")
    def consistent(self):
        if self.status == "SQL" and (not self.sql or self.reason is not None):
            raise ValueError("SQL response requires SQL and a null reason")
        if self.status == "UNSUPPORTED" and (self.sql is not None or not self.reason):
            raise ValueError("UNSUPPORTED requires a reason and null SQL")
        return self


class Provider(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class FakeProvider:
    """Explicit deterministic test double, never labeled as model output."""

    def __init__(self, response: SQLResponse):
        self.response = response
        self.calls = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.response.model_dump_json()


class OpenAIProvider:
    def __init__(self):
        self.key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("OPENAI_MODEL")
        if not self.key or not self.model:
            raise ValueError("Both OPENAI_API_KEY and OPENAI_MODEL must be set; no model default")

    def complete(self, system: str, user: str) -> str:
        request = Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(
                {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "response_format": {"type": "json_object"},
                }
            ).encode(),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"},
        )
        # Exactly one request. Do not log headers, secrets, or raw HTTP exception bodies.
        with urlopen(request, timeout=120) as response:
            return json.load(response)["choices"][0]["message"]["content"]


def generate(question: str, schema: dict, provider: Provider, semantics: bool = False):
    prompt = BASE_INSTRUCTIONS + "\nSchema:\n" + json.dumps(schema, sort_keys=True)
    if semantics:
        prompt += "\nProject semantic conventions:\n" + json.dumps(
            {name: d.model_dump() for name, d in load_definitions().items()}, sort_keys=True
        )
    return SQLResponse.model_validate_json(provider.complete(prompt, question))
