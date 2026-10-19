"""One question under a fixed experimental cell; does not execute untrusted SQL."""

from pathlib import Path

import yaml

from semantic_analytics.llm.baseline import generate
from semantic_analytics.validation.sql import validate


def run_question(
    configuration, question, schema, provider, config_path=Path("configs/experiment.yaml")
):
    config = yaml.safe_load(config_path.read_text())
    if config["validator_passes"] != 1 or config["llm_retries"] != 0:
        raise ValueError("Only single-pass validation without LLM retries is supported")
    cell = config["configurations"][configuration]
    response = generate(question, schema, provider, semantics=cell["semantics"])
    validation = None
    if cell["validator"] and response.status == "SQL":
        validation = validate(response.sql, schema)
    return {"response": response, "validation": validation}
