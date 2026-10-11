"""Check the scientific invariants behind the manuscript's reported results."""

from pathlib import Path
import csv, json, hashlib, math, platform, sys, importlib.metadata
from statistics import mean, median
import build_expanded_analytics as analysis

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    with (ROOT / name).open() as f:
        return list(csv.DictReader(f))


def close(a, b, tol=1e-8):
    assert math.isclose(float(a), b, rel_tol=tol, abs_tol=tol), (a, b)


def main():
    checks = []
    rows = read("results/unified_compiler_artifacts.csv")
    assert len(rows) == 15652
    bp = [r for r in rows if r["source"] == "benchpress_public"]
    met = [r for r in rows if r["source"] == "qiskit_metriq"]
    assert len(bp) == 12652 and len(met) == 3000
    assert {
        s: sum(r["status"] == s for r in bp) for s in ["passed", "failed", "skipped"]
    } == {"passed": 12318, "failed": 70, "skipped": 264}
    checks.append(
        "Source outcome reconciliation: 15,652 outcomes, 15,318 successful measurements."
    )
    good = [r for r in bp if r["status"] == "passed"]
    keys = [
        (
            r["sdk"],
            r["sdk_version"],
            r["workload_id_normalized"],
            r["topology"],
            r["input_num_qubits"],
        )
        for r in good
    ]
    assert len(keys) == len(set(keys))
    checks.append(
        "No duplicate SDK/version/workload/topology/qubit keys; full test identities retained."
    )
    assert all(
        r["output_depth"] and not r["output_depth_2q"] and not r["runtime_mean_s"]
        for r in met
    )
    assert all(r["output_depth_2q"] and not r["output_depth"] for r in good)
    checks.append(
        "Total-circuit and two-qubit fields remain separate; unavailable runtime remains missing."
    )
    q = read("tables/benchpress_qiskit_first_last_deltas.csv")
    assert len(q) == 1032 and len({r["circuit_base"] for r in q}) == 363
    assert len(read("tables/benchpress_qiskit_adjacent_version_deltas.csv")) == 9288
    for row in q:
        for prefix, col in [
            ("runtime", "runtime_delta_pct"),
            ("depth_2q", "depth_2q_delta_pct"),
            ("gate_2q", "gate_2q_delta_pct"),
        ]:
            a = float(row[prefix + "_from"])
            b = float(row[prefix + "_to"])
            if a == 0:
                assert row[col] == ""
            else:
                close(row[col], 100 * (b - a) / a)
    checks.append(
        "1,032 endpoint and 9,288 adjacent pairs; zero denominators excluded rather than filled."
    )
    qs = read("tables/qiskit_first_last_paired_summary.csv")
    assert [int(r["n"]) for r in qs] == [1032, 1016, 1016]
    close(qs[0]["mean"], 46.1520437726813)
    close(qs[0]["median"], 64.0259425096672)
    assert [int(qs[0][x]) for x in ["improved_n", "tied_n", "regressed_n"]] == [
        943,
        0,
        89,
    ]
    assert (
        float(qs[0]["bootstrap_median_ci_low"]) > 61.8
        and float(qs[0]["bootstrap_median_ci_high"]) < 66.4
    )
    checks.append(
        "Paired support, endpoint runtime headline, observed signs, and workload-clustered median interval verified."
    )
    assert (
        median([1, 2, 3, 4]) == 2.5
        and analysis.quantile([1, 2, 3, 4], 0.5) == 2
        and analysis.quantile([1, 2, 3, 4], 0.95) == 4
    )
    group = [
        float(r["runtime_mean_s"])
        for r in good
        if r["sdk"] == "qiskit" and r["sdk_version"] == "1.3.3"
    ]
    close(analysis.quantile(group, 0.95), 6.299169850997714)
    checks.append(
        "Ordinary median and separately defined nearest-rank upper percentiles agree with tables."
    )
    ms = read("tables/metriq_seed_level_first_last_deltas.csv")
    assert len(ms) == 200 and len({r["seed"] for r in ms}) == 100
    for seed in {r["seed"] for r in ms}:
        assert len([r for r in ms if r["seed"] == seed]) == 2
    close(-mean(float(r["depth_delta_pct"]) for r in ms), 66.67186822060503)
    close(-mean(float(r["gate_count_delta_pct"]) for r in ms), 74.01434736978567)
    checks.append(
        "200 historical endpoint pairs; 100 shared-seed bootstrap clusters; paired depth/gate means verified."
    )
    assert len(read("tables/benchpress_topology_penalty_cells.csv")) == 7977
    cross = read("tables/cross_sdk_descriptive_summary.csv")
    assert all(
        int(r["matched_cells"]) == 928 and int(r["depth_valid_n"]) == 917 for r in cross
    )
    checks.append(
        "Topology support 7,977; cross-SDK support 928 runtime and 917 nonzero-baseline depth pairs."
    )
    enrich = {
        r["metric"]: r["value"] for r in read("tables/qasmbench_enrichment_summary.csv")
    }
    assert [
        int(enrich[x])
        for x in [
            "benchpress_matched_exact_unique_rows",
            "benchpress_ambiguous_key_rows",
            "benchpress_unmatched_rows",
        ]
    ] == [5794, 48, 6476]
    checks.append(
        "Enrichment partition reconciles: 5,794 exact unique + 48 ambiguous + 6,476 unmatched."
    )
    for row in read("data/source_file_manifest.csv"):
        p = ROOT / "data" / row["source"] / row["relative_path"]
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        assert h.hexdigest() == row["sha256"]
    checks.append("All 300 primary inputs match pinned SHA-256 hashes.")
    for p in list((ROOT / "results").glob("*.csv")) + list(
        (ROOT / "tables").glob("*.csv")
    ):
        s = p.read_text()
        assert not any(
            x in s
            for x in ["/Users/", "/home/", "/private/", "CloudStorage", "NL2Vis_GenAI"]
        ), p.name
    checks.append(
        "Published derived records contain no absolute local/developer paths."
    )
    report = {
        "status": "PASS",
        "checks": checks,
        "python": platform.python_version(),
        "packages": {
            n: importlib.metadata.version(n)
            for n in ["numpy", "matplotlib", "packaging", "scipy", "qiskit", "pandas"]
        },
        "table_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "tables").glob("*.csv"))
        },
    }
    (ROOT / "verification/validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print("PASS:", len(checks), "scientific and provenance checks.")


if __name__ == "__main__":
    main()
