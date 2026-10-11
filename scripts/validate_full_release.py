"""Validate claims and full-length presentation support independently of formatting."""

from pathlib import Path
import csv, json, hashlib, math
from statistics import mean, median
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    with (ROOT / name).open() as f:
        return list(csv.DictReader(f))


def checkclose(value, expected):
    assert math.isclose(value, expected, abs_tol=1e-8), (value, expected)


def main():
    u = read("results/unified_compiler_artifacts.csv")
    bp = [
        r for r in u if r["source"] == "benchpress_public" and r["status"] == "passed"
    ]
    q = read("tables/benchpress_qiskit_first_last_deltas.csv")
    m = read("tables/metriq_seed_level_first_last_deltas.csv")
    records = []

    def claim(name, value, expected, source):
        if isinstance(expected, float):
            checkclose(value, expected)
        else:
            assert value == expected, (name, value, expected)
        records.append({"claim": name, "value": value, "evidence": source})

    claim("outcome_records", len(u), 15652, "results/unified_compiler_artifacts.csv")
    claim(
        "successful_records",
        sum(r["status"] == "passed" for r in u),
        15318,
        "results/unified_compiler_artifacts.csv",
    )
    claim(
        "endpoint_cells", len(q), 1032, "tables/benchpress_qiskit_first_last_deltas.csv"
    )
    claim(
        "logical_workload_clusters",
        len({r["circuit_base"] for r in q}),
        363,
        "tables/benchpress_qiskit_first_last_deltas.csv",
    )
    for key, valid, expected, signs in [
        ("runtime_delta_pct", 1032, 46.152043772681317, [943, 0, 89]),
        ("depth_2q_delta_pct", 1016, -0.39288183480523087, [345, 390, 281]),
        ("gate_2q_delta_pct", 1016, -2.0495739716845569, [271, 391, 354]),
    ]:
        vals = [-float(r[key]) for r in q if r[key] != ""]
        claim(
            key + "_eligible_n",
            len(vals),
            valid,
            "tables/benchpress_qiskit_first_last_deltas.csv",
        )
        claim(
            key + "_mean_reduction",
            mean(vals),
            expected,
            "tables/benchpress_qiskit_first_last_deltas.csv",
        )
        claim(
            key + "_improved_tied_regressed",
            [
                sum(v > 0 for v in vals),
                sum(v == 0 for v in vals),
                sum(v < 0 for v in vals),
            ],
            signs,
            "tables/benchpress_qiskit_first_last_deltas.csv",
        )
    for key, expected in [
        ("depth_delta_pct", 66.671868220605035),
        ("gate_count_delta_pct", 74.014347369785668),
    ]:
        claim(
            "historical_" + key + "_mean_reduction",
            mean(-float(r[key]) for r in m),
            expected,
            "tables/metriq_seed_level_first_last_deltas.csv",
        )
    claim(
        "historical_shared_seed_clusters",
        len({r["seed"] for r in m}),
        100,
        "tables/metriq_seed_level_first_last_deltas.csv",
    )
    top = sorted(bp, key=lambda r: float(r["runtime_mean_s"]), reverse=True)[:40]
    groups = Counter(
        (r["sdk"], r["sdk_version"], r["benchmark_family"], r["topology"]) for r in top
    )
    claim("top40_groups", len(groups), 21, "results/unified_compiler_artifacts.csv")
    claim(
        "top20_all_TKET_2.6.0",
        all(r["sdk"] == "tket" and r["sdk_version"] == "2.6.0" for r in top[:20]),
        True,
        "results/unified_compiler_artifacts.csv",
    )
    tket = [float(r["runtime_mean_s"]) for r in bp if r["sdk"] == "tket"]
    claim(
        "TKET_runtime_median_s",
        median(tket),
        2.129773687206587,
        "results/unified_compiler_artifacts.csv",
    )
    claim(
        "TKET_runtime_mean_s",
        mean(tket),
        70.07171614922547,
        "results/unified_compiler_artifacts.csv",
    )
    tc = read("tables/benchpress_topology_penalty_cells.csv")
    claim(
        "topology_cells", len(tc), 7977, "tables/benchpress_topology_penalty_cells.csv"
    )
    for t, n in [("heavy-hex", 2623), ("linear", 2623), ("square", 2625)]:
        claim(
            t + "_eligible_depth_ratios",
            sum(
                r["topology"] == t and r["depth_2q_ratio_vs_all_to_all"] != ""
                for r in tc
            ),
            n,
            "tables/benchpress_topology_penalty_cells.csv",
        )
    cross = read("tables/benchpress_cross_sdk_matched_cells.csv")
    claim(
        "cross_sdk_observations",
        len(cross),
        2784,
        "tables/benchpress_cross_sdk_matched_cells.csv",
    )
    for sdk in ["qiskit 2.5.0rc1", "qpanda 0.3.2", "tket 2.6.0"]:
        subset = [r for r in cross if r["sdk_version"] == sdk]
        claim(
            sdk + "_cells",
            len(subset),
            928,
            "tables/benchpress_cross_sdk_matched_cells.csv",
        )
        claim(
            sdk + "_depth_support",
            sum(r["depth_ratio_vs_qiskit_250rc1"] != "" for r in subset),
            917,
            "tables/benchpress_cross_sdk_matched_cells.csv",
        )
    fig = list((ROOT / "full_manuscript_assets").glob("figure_*.pdf"))
    tex = list((ROOT / "full_manuscript_assets").glob("table_*.tex"))
    claim("analytical_figures", len(fig), 8, "full_manuscript_assets/")
    claim("generated_numerical_tables", len(tex), 13, "full_manuscript_assets/")
    workflow = ROOT / "full_manuscript_assets/workflow_evidence.pdf"
    claim(
        "empirical_workflow_figure",
        workflow.is_file(),
        True,
        "full_manuscript_assets/workflow_evidence.pdf",
    )
    evidence = json.loads((ROOT / "verification/workflow_evidence.json").read_text())
    claim(
        "workflow_input_files",
        sum(evidence["input_files"].values()),
        300,
        "data/source_file_manifest.csv",
    )
    claim(
        "workflow_endpoint_support",
        evidence["comparison_support"]["Qiskit endpoints"],
        len(q),
        "tables/benchpress_qiskit_first_last_deltas.csv",
    )
    claim(
        "workflow_enrichment_partition",
        sum(evidence["enrichment"].values()),
        len(bp),
        "tables/qasmbench_enrichment_summary.csv",
    )
    assert all(b"CreationDate" not in p.read_bytes() for p in fig + [workflow]), (
        "Figures should omit timestamps for deterministic rendering"
    )
    report = {
        "status": "PASS",
        "claims_verified": len(records),
        "claims": records,
        "asset_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(fig + tex + [workflow])
        },
    }
    (ROOT / "verification/full_release_validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        "PASS:", len(records), "full-length manuscript claims and presentation checks."
    )


if __name__ == "__main__":
    main()
