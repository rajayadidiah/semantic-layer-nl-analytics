PYTHON ?= .venv/bin/python
.PHONY: install download-data inspect-data build-db verify-benchmark test lint smoke-llm \
	run-experiment summarize-experiment
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
test:
	$(PYTHON) -m pytest -q
lint:
	.venv/bin/ruff check .
