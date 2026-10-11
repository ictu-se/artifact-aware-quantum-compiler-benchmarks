"""Regenerate secondary analyses from hash-verified historical inputs."""

from pathlib import Path
import json, hashlib, csv
import build_unified_compiler_artifacts as ingest
import build_expanded_analytics as analysis
import build_qasmbench_enrichment as enrichment

ROOT = Path(__file__).resolve().parents[1]


def main():
    for folder in ["results", "tables", "figures", "verification"]:
        (ROOT / folder).mkdir(exist_ok=True)
    for r in csv.DictReader((ROOT / "data/source_file_manifest.csv").open()):
        p = ROOT / "data" / r["source"] / r["relative_path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == r["sha256"], str(p)
    ingest.main()
    rows = analysis.read_rows()
    analysis.benchpress_runtime_tables(rows)
    analysis.benchpress_paired_tables(rows)
    analysis.missingness_tables(rows)
    analysis.metriq_tables(rows)
    analysis.statistical_validation_tables(rows)
    # Main enrichment routine also exports parser diagnostics and identity counts.
    enrichment.main()
    print("Secondary analysis complete; primary inputs remain unchanged.")


if __name__ == "__main__":
    main()
