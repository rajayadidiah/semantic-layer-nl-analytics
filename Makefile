PYTHON ?= .venv/bin/python
.PHONY: install download-data inspect-data build-db verify-benchmark test lint
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
test:
	$(PYTHON) -m pytest -q
lint:
	.venv/bin/ruff check .
