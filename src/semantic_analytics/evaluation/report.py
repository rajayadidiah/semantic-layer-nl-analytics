"""Aggregate experiment JSONL into configuration-level metrics."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from semantic_analytics.evaluation.experiment import ExperimentRecord


def load_records(path: Path) -> list[ExperimentRecord]:
    return [
        ExperimentRecord.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(records: list[ExperimentRecord]) -> dict:
    grouped = defaultdict(list)
    for record in records:
        grouped[record.configuration].append(record)

    summary = {}
    for configuration in sorted(grouped):
        items = grouped[configuration]
        answerable = [item for item in items if item.answerable]
        unsupported = [item for item in items if not item.answerable]
        semantic = [item for item in items if item.requires_semantics]
        latencies = [
            item.model_latency_ms + (item.execution_latency_ms or 0.0)
            for item in items
        ]
        summary[configuration] = {
            "runs": len(items),
            "accuracy": _rate(sum(item.correct for item in items), len(items)),
            "answerable_accuracy": _rate(
                sum(item.correct for item in answerable),
                len(answerable),
            ),
            "unsupported_accuracy": _rate(
                sum(item.correct for item in unsupported),
                len(unsupported),
            ),
            "semantic_accuracy": _rate(
                sum(item.correct for item in semantic),
                len(semantic),
            ),
            "validator_rejections": sum(
                item.failure_category == "validator_rejected" for item in items
            ),
            "execution_errors": sum(
                item.failure_category == "execution_error" for item in items
            ),
            "median_end_to_end_ms": median(latencies) if latencies else None,
            "failure_categories": dict(
                Counter(item.failure_category for item in items)
            ),
        }
    return summary


def markdown(summary: dict) -> str:
    lines = [
        "# Experiment summary",
        "",
        "| Config | Runs | Accuracy | Answerable | Unsupported | Semantic | Median ms |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for configuration, item in summary.items():
        def pct(value):
            return "N/A" if value is None else f"{value:.1%}"

        latency = item["median_end_to_end_ms"]
        latency_text = "N/A" if latency is None else f"{latency:.1f}"
        lines.append(
            f"| {configuration} | {item['runs']} | {pct(item['accuracy'])} | "
            f"{pct(item['answerable_accuracy'])} | "
            f"{pct(item['unsupported_accuracy'])} | "
            f"{pct(item['semantic_accuracy'])} | {latency_text} |"
        )
    lines += ["", "## Failure categories", ""]
    for configuration, item in summary.items():
        lines.append(f"**{configuration}:** {item['failure_categories']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/experiment_results.jsonl"),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("data/processed/experiment_summary.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("docs/experiment_summary.md"),
    )
    args = parser.parse_args()

    summary = summarize(load_records(args.input))
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(summary, indent=2) + "\n")
    args.markdown_output.write_text(markdown(summary))
    print(markdown(summary))


if __name__ == "__main__":
    main()
