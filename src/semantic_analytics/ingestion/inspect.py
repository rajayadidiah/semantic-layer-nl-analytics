"""Generate a comparison from verified Parquet metadata, never guessed schemas."""

from pathlib import Path

from semantic_analytics.contracts.manifest import load_manifest
from semantic_analytics.ingestion.download import metadata, verify_file


def inspect(
    manifest_path=Path("data/manifest.yaml"),
    raw=Path("data/raw"),
    report=Path("docs/schema_comparison.md"),
):
    manifest = load_manifest(manifest_path)
    if manifest.status != "frozen":
        raise ValueError("Real-data inspection requires a frozen manifest")
    lines = [
        "# Observed TLC schemas",
        "",
        "Generated from checksum-verified local files. "
        "Arrow nullable is schema metadata, not an observed null count; "
        "see the separate quality report for actual null rates.",
        "",
    ]
    schemas = {}
    for source in manifest.files:
        path = raw / source.filename
        verify_file(source, path)
        observed = metadata(path)
        if observed != {key: getattr(source, key) for key in observed}:
            raise ValueError(f"Observed metadata differs from lock: {source.filename}")
        lines += [
            f"## {source.filename}",
            "",
            f"Rows: {source.row_count}; bytes: {source.size_bytes}",
            "",
            "| Column | Arrow type | Nullable metadata |",
            "|---|---|---|",
        ]
        lines += [f"| {f.name} | {f.type} | {f.nullable} |" for f in source.schema_fields]
        lines += [""]
        if source.service != "zones":
            schemas[source.filename] = {f.name: f.type for f in source.schema_fields}
    yellow = {k: v for k, v in schemas.items() if k.startswith("yellow")}
    green = {k: v for k, v in schemas.items() if k.startswith("green")}
    yn = set.union(*(set(v) for v in yellow.values()))
    gn = set.union(*(set(v) for v in green.values()))
    lines += [
        "## Cross-service comparison",
        "",
        "Shared names: " + ", ".join(sorted(yn & gn)),
        "",
        "Yellow-only names: " + ", ".join(sorted(yn - gn)),
        "",
        "Green-only names: " + ", ".join(sorted(gn - yn)),
        "",
        "Type differences:",
    ]
    difference_count = 0
    for name in sorted(yn & gn):
        yt = {v[name] for v in yellow.values() if name in v}
        gt = {v[name] for v in green.values() if name in v}
        if yt != gt or len(yt) > 1 or len(gt) > 1:
            difference_count += 1
            lines.append(f"- {name}: Yellow {sorted(yt)}; Green {sorted(gt)}")
    if not difference_count:
        lines.append("- No type differences among shared column names in these files.")
    lines += ["", "Monthly missing fields:"]
    for filename, fields in schemas.items():
        names = yn if filename.startswith("yellow") else gn
        lines.append(f"- {filename}: {sorted(names - fields.keys())}")
    lines += [
        "",
        "The canonical mapping treats tpep/lpep timestamp prefixes as the same "
        "pickup/dropoff concepts, subject to required-column validation. Similar names "
        "do not establish identical business meaning. The research problem is semantic "
        "ambiguity; this report does not imply unrelated or chaotic schemas.",
    ]
    report.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    inspect()
