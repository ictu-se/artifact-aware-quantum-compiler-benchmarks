"""Plot workflow accounting from the input manifest and generated observations."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "full_manuscript_assets"
BLUE = "#2166ac"
ORANGE = "#d97706"
GREEN = "#21855b"


def read_records(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def bar_panel(axis, labels, counts, title, unit, colors):
    positions = list(range(len(labels)))
    axis.barh(positions, counts, color=colors, height=0.65)
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    maximum = max(counts)
    axis.set_xlim(0, maximum * 1.26)
    axis.set_xlabel(unit)
    axis.set_title(title, loc="left", fontweight="bold", pad=12)
    axis.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
    axis.spines[["top", "right"]].set_visible(False)
    for position, count in zip(positions, counts):
        axis.text(count + maximum * 0.025, position, f"{count:,}", va="center")


def main() -> None:
    inputs = Counter(
        row["source"] for row in read_records("data/source_file_manifest.csv")
    )
    outcomes = read_records("results/unified_compiler_artifacts.csv")
    source_outcomes = Counter(row["source"] for row in outcomes)
    successful = Counter(row["source"] for row in outcomes if row["status"] == "passed")
    cross = read_records("tables/cross_sdk_descriptive_summary.csv")
    shared_cells = {int(row["matched_cells"]) for row in cross}
    if len(shared_cells) != 1:
        raise ValueError(
            "Cross-SDK summaries disagree about shared comparison support."
        )
    comparison_labels = [
        "Qiskit endpoints",
        "Adjacent versions",
        "Topology cells",
        "Cross-SDK cells",
        "Historical seed pairs",
    ]
    comparison_counts = [
        len(read_records("tables/benchpress_qiskit_first_last_deltas.csv")),
        len(read_records("tables/benchpress_qiskit_adjacent_version_deltas.csv")),
        len(read_records("tables/benchpress_topology_penalty_cells.csv")),
        shared_cells.pop(),
        len(read_records("tables/metriq_seed_level_first_last_deltas.csv")),
    ]
    enrichment = {
        row["metric"]: row["value"]
        for row in read_records("tables/qasmbench_enrichment_summary.csv")
    }
    enrichment_counts = [
        int(enrichment[key])
        for key in [
            "benchpress_matched_exact_unique_rows",
            "benchpress_ambiguous_key_rows",
            "benchpress_unmatched_rows",
        ]
    ]
    if sum(enrichment_counts) != successful["benchpress_public"]:
        raise ValueError(
            "Enrichment accounting does not partition successful Benchpress observations."
        )

    plt.rcParams.update({"font.size": 10.5, "axes.titlesize": 11, "pdf.fonttype": 42})
    figure, axes = plt.subplots(4, 1, figsize=(6.1, 8.2), layout="constrained")
    bar_panel(
        axes[0],
        ["Benchpress", "qiskit-metriq", "QASMBench"],
        [
            inputs[source]
            for source in ["benchpress_public", "qiskit_metriq", "qasmbench"]
        ],
        "(a) Inventory: pinned inputs",
        "Files",
        [BLUE, ORANGE, GREEN],
    )
    bar_panel(
        axes[1],
        [
            "Benchpress: all outcomes",
            "Benchpress: successful",
            "qiskit-metriq: recorded",
        ],
        [
            source_outcomes["benchpress_public"],
            successful["benchpress_public"],
            source_outcomes["qiskit_metriq"],
        ],
        "(b) Normalize: retained observations",
        "Outcome records",
        [BLUE, GREEN, ORANGE],
    )
    bar_panel(
        axes[2],
        comparison_labels,
        comparison_counts,
        "(c) Match: comparison support",
        "Cells or pairs (overlapping subsets)",
        BLUE,
    )
    bar_panel(
        axes[3],
        ["Exact unique", "Ambiguous", "Unmatched"],
        enrichment_counts,
        "(d) Enrich: input-identity coverage",
        "Successful Benchpress observations",
        [GREEN, ORANGE, BLUE],
    )
    OUTPUT.mkdir(exist_ok=True)
    figure.savefig(
        OUTPUT / "workflow_evidence.pdf",
        bbox_inches="tight",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(figure)
    evidence = {
        "input_files": dict(inputs),
        "outcomes": dict(source_outcomes),
        "successful_outcomes": dict(successful),
        "comparison_support": dict(zip(comparison_labels, comparison_counts)),
        "enrichment": dict(
            zip(["exact_unique", "ambiguous", "unmatched"], enrichment_counts)
        ),
        "comparison_subsets_are_not_additive": True,
    }
    (ROOT / "verification" / "workflow_evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )
    print("Rendered empirical workflow accounting from manifest and result records.")


if __name__ == "__main__":
    main()
