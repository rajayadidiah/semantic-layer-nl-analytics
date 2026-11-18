PYTHON ?= .venv/bin/python
.PHONY: install download-data inspect-data build-db verify-benchmark test lint smoke-llm \
	run-experiment summarize-experiment rescore-experiment summarize-rescored
install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.lock
	.venv/bin/pip install --no-deps -e .
download-data:
	$(PYTHON) -m semantic_analytics.ingestion.download
inspect-data:
	$(PYTHON) -m semantic_analytics.ingestion.inspect
build-db:
	$(PYTHON) -m semantic_analytics.database.build
verify-benchmark:
	$(PYTHON) -m semantic_analytics.evaluation.benchmark
smoke-llm:
	$(PYTHON) -m semantic_analytics.evaluation.experiment --limit 5
run-experiment:
	$(PYTHON) -m semantic_analytics.evaluation.experiment
summarize-experiment:
	$(PYTHON) -m semantic_analytics.evaluation.report
rescore-experiment:
	$(PYTHON) -m semantic_analytics.evaluation.rescore
summarize-rescored:
	$(PYTHON) -m semantic_analytics.evaluation.report \
		--input data/processed/experiment_results_rescored.jsonl \
		--json-output data/processed/experiment_summary_rescored.json \
		--markdown-output docs/experiment_summary_rescored.md
test:
	$(PYTHON) -m pytest -q
lint:
	.venv/bin/ruff check .
