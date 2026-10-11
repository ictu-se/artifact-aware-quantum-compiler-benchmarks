#!/usr/bin/env python3
"""Build expanded analysis tables and figures for Paper 11."""

from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, pstdev

from packaging.version import Version


PAPER = Path(__file__).resolve().parents[1]
UNIFIED = PAPER / "results/unified_compiler_artifacts.csv"


def read_rows() -> list[dict]:
    with UNIFIED.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def num(row: dict, key: str) -> float | None:
    value = row.get(key, "")
    if value == "":
        return None
    try:
        value = float(value)
    except ValueError:
        return None
    if math.isnan(value):
        return None
    return value


def fmt(value: float | None, digits: int = 17) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}g}"


def version_key(version: str) -> Version:
    return Version(version.replace(".rc", "rc"))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def quantile(values: list[float], q: float) -> float | None:
    """Nearest-rank empirical quantile used by the manuscript equations."""
    if not values:
        return None
    values = sorted(values)
    rank = max(1, math.ceil(q * len(values)))
    return values[rank - 1]


def group_summary(
    rows: list[dict], keys: list[str], metrics: list[str], out_path: Path
) -> list[dict]:
    groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(key, "") for key in keys)].append(row)

    out_rows: list[dict] = []
    for group_key, group_rows in sorted(groups.items()):
        out = {key: value for key, value in zip(keys, group_key)}
        out["n"] = str(len(group_rows))
        for metric in metrics:
            vals = [v for row in group_rows if (v := num(row, metric)) is not None]
            out[f"{metric}_n"] = str(len(vals))
            out[f"{metric}_mean"] = fmt(mean(vals) if vals else None)
            out[f"{metric}_median"] = fmt(median(vals) if vals else None)
            out[f"{metric}_p90"] = fmt(quantile(vals, 0.90))
            out[f"{metric}_p95"] = fmt(quantile(vals, 0.95))
            out[f"{metric}_max"] = fmt(max(vals) if vals else None)
        out_rows.append(out)

    write_csv(out_path, out_rows)
    return out_rows


def benchpress_runtime_tables(rows: list[dict]) -> None:
    bench = [
        row
        for row in rows
        if row["source"] == "benchpress_public" and row["status"] == "passed"
    ]
    tables = PAPER / "tables"

    group_summary(
        bench,
        ["sdk", "sdk_version"],
        [
            "runtime_mean_s",
            "runtime_median_s",
            "runtime_max_s",
            "output_depth_2q",
            "output_gate_count_2q",
        ],
        tables / "benchpress_sdk_version_distribution.csv",
    )
    group_summary(
        bench,
        ["benchmark_family"],
        [
            "runtime_mean_s",
            "runtime_median_s",
            "output_depth_2q",
            "output_gate_count_2q",
        ],
        tables / "benchpress_family_distribution.csv",
    )
    group_summary(
        bench,
        ["topology"],
        [
            "runtime_mean_s",
            "runtime_median_s",
            "output_depth_2q",
            "output_gate_count_2q",
        ],
        tables / "benchpress_topology_distribution.csv",
    )
    group_summary(
        bench,
        ["benchmark_family", "topology"],
        ["runtime_mean_s", "output_depth_2q", "output_gate_count_2q"],
        tables / "benchpress_family_topology_distribution.csv",
    )

    enriched = []
    for row in bench:
        runtime = num(row, "runtime_mean_s")
        runtime_median = num(row, "runtime_median_s")
        runtime_max = num(row, "runtime_max_s")
        if runtime is None:
            continue
        skew_ratio = (
            runtime / runtime_median if runtime_median and runtime_median > 0 else None
        )
        burst_ratio = (
            runtime_max / runtime_median
            if runtime_max and runtime_median and runtime_median > 0
            else None
        )
        enriched.append(
            {
                "artifact_id": row["artifact_id"],
                "sdk": row["sdk"],
                "sdk_version": row["sdk_version"],
                "benchmark_family": row["benchmark_family"],
                "topology": row["topology"],
                "circuit_name": row["circuit_name"],
                "input_num_qubits": row["input_num_qubits"],
                "output_num_qubits": row["output_num_qubits"],
                "runtime_mean_s": fmt(runtime),
                "runtime_median_s": fmt(runtime_median),
                "runtime_max_s": fmt(runtime_max),
                "mean_to_median_ratio": fmt(skew_ratio),
                "max_to_median_ratio": fmt(burst_ratio),
                "output_depth_2q": row["output_depth_2q"],
                "output_gate_count_2q": row["output_gate_count_2q"],
            }
        )

    by_runtime = sorted(
        enriched, key=lambda row: float(row["runtime_mean_s"]), reverse=True
    )[:40]
    write_csv(tables / "benchpress_top_runtime_outliers.csv", by_runtime)

    by_skew = [
        row
        for row in enriched
        if row["mean_to_median_ratio"] not in ("", "nan")
        and float(row["mean_to_median_ratio"]) > 1
    ]
    by_skew = sorted(
        by_skew, key=lambda row: float(row["mean_to_median_ratio"]), reverse=True
    )[:40]
    write_csv(tables / "benchpress_top_skew_outliers.csv", by_skew)


def benchpress_paired_tables(rows: list[dict]) -> None:
    bench = [
        row
        for row in rows
        if row["source"] == "benchpress_public" and row["status"] == "passed"
    ]
    tables = PAPER / "tables"

    qiskit = [row for row in bench if row["sdk"] == "qiskit"]
    groups: dict[tuple[str, str, str, str], dict[str, dict]] = defaultdict(dict)
    for row in qiskit:
        key = (
            row["benchmark_family"],
            row["workload_id_normalized"],
            row["topology"],
            row["input_num_qubits"],
        )
        if row["sdk_version"] in groups[key]:
            raise ValueError(
                f"Duplicate Qiskit matched key/version: {key} {row['sdk_version']}"
            )
        groups[key][row["sdk_version"]] = row

    adjacent: list[dict] = []
    first_last: list[dict] = []
    for (family, base, topology, qubits), by_version in groups.items():
        versions = sorted(by_version, key=version_key)
        if len(versions) < 2:
            continue
        pairs = list(zip(versions, versions[1:]))
        if "1.3.3" in by_version and "2.5.0rc1" in by_version:
            pairs.append(("1.3.3", "2.5.0rc1"))
        for prev, cur in pairs:
            prev_row = by_version[prev]
            cur_row = by_version[cur]
            runtime_prev = num(prev_row, "runtime_mean_s")
            runtime_cur = num(cur_row, "runtime_mean_s")
            depth_prev = num(prev_row, "output_depth_2q")
            depth_cur = num(cur_row, "output_depth_2q")
            gates_prev = num(prev_row, "output_gate_count_2q")
            gates_cur = num(cur_row, "output_gate_count_2q")
            out = {
                "benchmark_family": family,
                "circuit_base": base,
                "topology": topology,
                "input_num_qubits": qubits,
                "from_version": prev,
                "to_version": cur,
                "runtime_delta_pct": fmt(
                    100 * (runtime_cur - runtime_prev) / runtime_prev
                    if runtime_prev
                    else None
                ),
                "depth_2q_delta_pct": fmt(
                    100 * (depth_cur - depth_prev) / depth_prev if depth_prev else None
                ),
                "gate_2q_delta_pct": fmt(
                    100 * (gates_cur - gates_prev) / gates_prev if gates_prev else None
                ),
                "runtime_from": fmt(runtime_prev),
                "runtime_to": fmt(runtime_cur),
                "depth_2q_from": fmt(depth_prev),
                "depth_2q_to": fmt(depth_cur),
                "gate_2q_from": fmt(gates_prev),
                "gate_2q_to": fmt(gates_cur),
            }
            if prev == "1.3.3" and cur == "2.5.0rc1":
                first_last.append(out)
            else:
                adjacent.append(out)
    write_csv(tables / "benchpress_qiskit_adjacent_version_deltas.csv", adjacent)
    write_csv(tables / "benchpress_qiskit_first_last_deltas.csv", first_last)
    largest_reg = sorted(
        [row for row in adjacent if row["runtime_delta_pct"]],
        key=lambda row: float(row["runtime_delta_pct"]),
        reverse=True,
    )[:40]
    largest_imp = sorted(
        [row for row in adjacent if row["runtime_delta_pct"]],
        key=lambda row: float(row["runtime_delta_pct"]),
    )[:40]
    write_csv(tables / "benchpress_qiskit_largest_runtime_regressions.csv", largest_reg)
    write_csv(
        tables / "benchpress_qiskit_largest_runtime_improvements.csv", largest_imp
    )

    topo_groups: dict[tuple[str, str, str, str, str], dict[str, dict]] = defaultdict(
        dict
    )
    for row in bench:
        base = row["workload_id_normalized"]
        key = (
            row["sdk"],
            row["sdk_version"],
            row["benchmark_family"],
            base,
            row["input_num_qubits"],
        )
        if row["topology"] in topo_groups[key]:
            raise ValueError(f"Duplicate topology matched key: {key} {row['topology']}")
        topo_groups[key][row["topology"]] = row
    topo_rows: list[dict] = []
    for (sdk, version, family, base, qubits), by_topology in topo_groups.items():
        reference = by_topology.get("all-to-all")
        if not reference:
            continue
        ref_runtime = num(reference, "runtime_mean_s")
        ref_depth = num(reference, "output_depth_2q")
        ref_gates = num(reference, "output_gate_count_2q")
        for topology, row in by_topology.items():
            if topology == "all-to-all":
                continue
            runtime = num(row, "runtime_mean_s")
            depth = num(row, "output_depth_2q")
            gates = num(row, "output_gate_count_2q")
            topo_rows.append(
                {
                    "sdk": sdk,
                    "sdk_version": version,
                    "benchmark_family": family,
                    "circuit_base": base,
                    "input_num_qubits": qubits,
                    "topology": topology,
                    "runtime_ratio_vs_all_to_all": fmt(
                        runtime / ref_runtime
                        if runtime is not None and ref_runtime
                        else None
                    ),
                    "depth_2q_ratio_vs_all_to_all": fmt(
                        depth / ref_depth if depth is not None and ref_depth else None
                    ),
                    "gate_2q_ratio_vs_all_to_all": fmt(
                        gates / ref_gates if gates is not None and ref_gates else None
                    ),
                    "runtime_s": fmt(runtime),
                    "all_to_all_runtime_s": fmt(ref_runtime),
                    "depth_2q": fmt(depth),
                    "all_to_all_depth_2q": fmt(ref_depth),
                }
            )
    write_csv(tables / "benchpress_topology_penalty_cells.csv", topo_rows)
    family_topo: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in topo_rows:
        family_topo[(row["benchmark_family"], row["topology"])].append(row)
    summary_rows: list[dict] = []
    for (family, topology), vals in sorted(family_topo.items()):
        runtime_ratios = [
            float(row["runtime_ratio_vs_all_to_all"])
            for row in vals
            if row["runtime_ratio_vs_all_to_all"]
        ]
        depth_ratios = [
            float(row["depth_2q_ratio_vs_all_to_all"])
            for row in vals
            if row["depth_2q_ratio_vs_all_to_all"]
        ]
        gate_ratios = [
            float(row["gate_2q_ratio_vs_all_to_all"])
            for row in vals
            if row["gate_2q_ratio_vs_all_to_all"]
        ]
        summary_rows.append(
            {
                "benchmark_family": family,
                "topology": topology,
                "n": str(len(vals)),
                "runtime_valid_n": len(runtime_ratios),
                "depth_valid_n": len(depth_ratios),
                "gate_valid_n": len(gate_ratios),
                "runtime_ratio_median": fmt(
                    median(runtime_ratios) if runtime_ratios else None
                ),
                "runtime_ratio_p90": fmt(quantile(runtime_ratios, 0.9)),
                "depth_2q_ratio_median": fmt(
                    median(depth_ratios) if depth_ratios else None
                ),
                "gate_2q_ratio_median": fmt(
                    median(gate_ratios) if gate_ratios else None
                ),
            }
        )
    write_csv(tables / "benchpress_topology_penalty_by_family.csv", summary_rows)

    cross_groups: dict[tuple[str, str, str, str], dict[str, dict]] = defaultdict(dict)
    for row in bench:
        sdk_label = f"{row['sdk']} {row['sdk_version']}"
        key = (
            row["benchmark_family"],
            row["workload_id_normalized"],
            row["topology"],
            row["input_num_qubits"],
        )
        if row["sdk"] == "qiskit" and row["sdk_version"] == "2.5.0rc1":
            cross_groups[key]["qiskit 2.5.0rc1"] = row
        elif row["sdk"] in ("qpanda", "tket"):
            cross_groups[key][sdk_label] = row
    cross_rows: list[dict] = []
    for (family, base, topology, qubits), by_sdk in cross_groups.items():
        needed = ["qiskit 2.5.0rc1", "qpanda 0.3.2", "tket 2.6.0"]
        if not all(item in by_sdk for item in needed):
            continue
        qiskit_row = by_sdk["qiskit 2.5.0rc1"]
        q_runtime = num(qiskit_row, "runtime_mean_s")
        q_depth = num(qiskit_row, "output_depth_2q")
        for label in needed:
            row = by_sdk[label]
            runtime = num(row, "runtime_mean_s")
            depth = num(row, "output_depth_2q")
            cross_rows.append(
                {
                    "benchmark_family": family,
                    "circuit_base": base,
                    "topology": topology,
                    "input_num_qubits": qubits,
                    "sdk_version": label,
                    "runtime_mean_s": fmt(runtime),
                    "depth_2q": row["output_depth_2q"],
                    "gate_2q": row["output_gate_count_2q"],
                    "runtime_ratio_vs_qiskit_250rc1": fmt(
                        runtime / q_runtime
                        if runtime is not None and q_runtime
                        else None
                    ),
                    "depth_ratio_vs_qiskit_250rc1": fmt(
                        depth / q_depth if depth is not None and q_depth else None
                    ),
                }
            )
    write_csv(tables / "benchpress_cross_sdk_matched_cells.csv", cross_rows)


def missingness_tables(rows: list[dict]) -> None:
    tables = PAPER / "tables"
    fields = [
        key
        for key in rows[0].keys()
        if key not in ("artifact_id", "source", "source_file")
    ]
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["source"]].append(row)
    out_rows = []
    for source, group_rows in sorted(groups.items()):
        for field in fields:
            present = sum(1 for row in group_rows if row.get(field, "") != "")
            out_rows.append(
                {
                    "source": source,
                    "field": field,
                    "present": str(present),
                    "missing": str(len(group_rows) - present),
                    "present_pct": fmt(100 * present / len(group_rows)),
                }
            )
    write_csv(tables / "unified_missingness_by_source.csv", out_rows)


def metriq_tables(rows: list[dict]) -> None:
    metriq = [row for row in rows if row["source"] == "qiskit_metriq"]
    tables = PAPER / "tables"
    group_summary(
        metriq,
        ["sdk_version", "backend_or_device", "optimization_level"],
        ["output_depth", "output_gate_count"],
        tables / "metriq_version_backend_optlevel_distribution.csv",
    )
    group_summary(
        metriq,
        ["backend_or_device", "optimization_level"],
        ["output_depth", "output_gate_count"],
        tables / "metriq_backend_optlevel_distribution.csv",
    )

    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in metriq:
        key = (
            row["backend_or_device"],
            row["optimization_level"],
            row["circuit_name"],
            row["sdk_version"],
        )
        groups[key].append(row)

    version_means: dict[tuple[str, str, str], dict[str, dict[str, float]]] = (
        defaultdict(dict)
    )
    seed_rows: list[dict] = []
    for (backend, opt, circuit, version), group_rows in groups.items():
        depths = [
            v for row in group_rows if (v := num(row, "output_depth")) is not None
        ]
        gates = [
            v for row in group_rows if (v := num(row, "output_gate_count")) is not None
        ]
        if not depths or not gates:
            continue
        version_means[(backend, opt, circuit)][version] = {
            "depth": mean(depths),
            "gate_count": mean(gates),
            "depth_sd": pstdev(depths) if len(depths) > 1 else 0.0,
            "gate_count_sd": pstdev(gates) if len(gates) > 1 else 0.0,
            "n": len(group_rows),
        }
        seed_rows.append(
            {
                "backend_or_device": backend,
                "optimization_level": opt,
                "circuit_name": circuit,
                "sdk_version": version,
                "n": str(len(group_rows)),
                "depth_mean": fmt(mean(depths)),
                "depth_sd": fmt(pstdev(depths) if len(depths) > 1 else 0.0),
                "gate_count_mean": fmt(mean(gates)),
                "gate_count_sd": fmt(pstdev(gates) if len(gates) > 1 else 0.0),
            }
        )
    write_csv(tables / "metriq_seed_variability_by_circuit.csv", seed_rows)

    changes: list[dict] = []
    for (backend, opt, circuit), by_version in version_means.items():
        versions = sorted(by_version, key=version_key)
        for prev, cur in zip(versions, versions[1:]):
            prev_row = by_version[prev]
            cur_row = by_version[cur]
            depth_delta = cur_row["depth"] - prev_row["depth"]
            gate_delta = cur_row["gate_count"] - prev_row["gate_count"]
            changes.append(
                {
                    "backend_or_device": backend,
                    "optimization_level": opt,
                    "circuit_name": circuit,
                    "from_version": prev,
                    "to_version": cur,
                    "depth_from": fmt(prev_row["depth"]),
                    "depth_to": fmt(cur_row["depth"]),
                    "depth_delta": fmt(depth_delta),
                    "depth_delta_pct": fmt(
                        100 * depth_delta / prev_row["depth"]
                        if prev_row["depth"]
                        else None
                    ),
                    "gate_count_from": fmt(prev_row["gate_count"]),
                    "gate_count_to": fmt(cur_row["gate_count"]),
                    "gate_count_delta": fmt(gate_delta),
                    "gate_count_delta_pct": fmt(
                        100 * gate_delta / prev_row["gate_count"]
                        if prev_row["gate_count"]
                        else None
                    ),
                    "n_from": str(int(prev_row["n"])),
                    "n_to": str(int(cur_row["n"])),
                }
            )
    write_csv(tables / "metriq_circuit_version_changes.csv", changes)
    improvements = sorted(changes, key=lambda row: float(row["depth_delta"]))[:40]
    regressions = sorted(
        changes, key=lambda row: float(row["depth_delta"]), reverse=True
    )[:40]
    write_csv(tables / "metriq_largest_depth_improvements.csv", improvements)
    write_csv(tables / "metriq_largest_depth_regressions.csv", regressions)

    seed_groups: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for row in metriq:
        seed_groups[(row["backend_or_device"], row["seed"])][row["sdk_version"]] = row
    seed_deltas = []
    for (backend, seed), by_version in sorted(seed_groups.items()):
        if "0.18.0" not in by_version or "0.45.2" not in by_version:
            continue
        first = by_version["0.18.0"]
        last = by_version["0.45.2"]
        first_depth = num(first, "output_depth")
        last_depth = num(last, "output_depth")
        first_gates = num(first, "output_gate_count")
        last_gates = num(last, "output_gate_count")
        seed_deltas.append(
            {
                "backend_or_device": backend,
                "seed": seed,
                "depth_0180": fmt(first_depth),
                "depth_0452": fmt(last_depth),
                "depth_delta": fmt(
                    last_depth - first_depth
                    if first_depth is not None and last_depth is not None
                    else None
                ),
                "depth_delta_pct": fmt(
                    100 * (last_depth - first_depth) / first_depth
                    if first_depth and last_depth is not None
                    else None
                ),
                "gate_count_0180": fmt(first_gates),
                "gate_count_0452": fmt(last_gates),
                "gate_count_delta": fmt(
                    last_gates - first_gates
                    if first_gates is not None and last_gates is not None
                    else None
                ),
                "gate_count_delta_pct": fmt(
                    100 * (last_gates - first_gates) / first_gates
                    if first_gates and last_gates is not None
                    else None
                ),
            }
        )
    write_csv(tables / "metriq_seed_level_first_last_deltas.csv", seed_deltas)


def rank_biserial(values: list[float]) -> tuple[float | None, float | None]:
    """Return paired rank-biserial effect and Wilcoxon p-value."""
    nonzero = [value for value in values if value != 0]
    if not nonzero:
        return 0.0, 1.0
    try:
        from scipy.stats import rankdata, wilcoxon  # type: ignore

        ranks = rankdata([abs(value) for value in nonzero], method="average")
        positive = sum(rank for rank, value in zip(ranks, nonzero) if value > 0)
        negative = sum(rank for rank, value in zip(ranks, nonzero) if value < 0)
        effect = (
            (positive - negative) / (positive + negative)
            if positive + negative
            else 0.0
        )
        p_value = float(
            wilcoxon(nonzero, alternative="two-sided", zero_method="wilcox").pvalue
        )
        return float(effect), p_value
    except Exception:
        return None, None


def clustered_bootstrap_ci(
    rows: list[dict],
    value_key: str,
    cluster_key: str,
    statistic=median,
    iterations: int = 2000,
) -> tuple[float | None, float | None]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = row.get(value_key, "")
        if value in ("", None):
            continue
        grouped[row[cluster_key]].append(float(value))
    clusters = sorted(grouped)
    if not clusters:
        return None, None
    rng = random.Random(20260716)
    estimates = []
    for _ in range(iterations):
        sampled = [rng.choice(clusters) for _ in clusters]
        values = [value for cluster in sampled for value in grouped[cluster]]
        estimates.append(float(statistic(values)))
    return quantile(estimates, 0.025), quantile(estimates, 0.975)


def paired_metric_summary(
    rows: list[dict],
    analysis: str,
    metric_key: str,
    metric_label: str,
    cluster_key: str,
    invert: bool = True,
) -> dict:
    prepared = []
    for row in rows:
        value = row.get(metric_key, "")
        if value == "":
            continue
        item = dict(row)
        item["analysis_value"] = -float(value) if invert else float(value)
        prepared.append(item)
    values = [row["analysis_value"] for row in prepared]
    if not values:
        return {
            "analysis": analysis,
            "metric": metric_label,
            "n": 0,
        }
    ci_low, ci_high = clustered_bootstrap_ci(prepared, "analysis_value", cluster_key)
    effect, p_value = rank_biserial(values)
    ordered = sorted(values)
    trim = max(0, int(len(ordered) * 0.01))
    trimmed = (
        ordered[trim : len(ordered) - trim]
        if trim and 2 * trim < len(ordered)
        else ordered
    )
    return {
        "analysis": analysis,
        "metric": metric_label,
        "n": len(values),
        "mean": fmt(mean(values)),
        "median": fmt(median(values)),
        "q25": fmt(quantile(values, 0.25)),
        "q75": fmt(quantile(values, 0.75)),
        "bootstrap_median_ci_low": fmt(ci_low),
        "bootstrap_median_ci_high": fmt(ci_high),
        "improved_n": sum(value > 0 for value in values),
        "tied_n": sum(value == 0 for value in values),
        "regressed_n": sum(value < 0 for value in values),
        "rank_biserial": fmt(effect),
        "wilcoxon_p": fmt(p_value),
        "trimmed_mean_1pct": fmt(mean(trimmed)),
    }


def statistical_validation_tables(rows: list[dict]) -> None:
    tables = PAPER / "tables"
    with (tables / "benchpress_qiskit_first_last_deltas.csv").open(
        "r", encoding="utf-8", newline=""
    ) as f:
        first_last = list(csv.DictReader(f))
    paired_rows = [
        paired_metric_summary(
            first_last,
            "Qiskit 1.3.3 to 2.5.0rc1",
            "runtime_delta_pct",
            "runtime reduction (%)",
            "circuit_base",
        ),
        paired_metric_summary(
            first_last,
            "Qiskit 1.3.3 to 2.5.0rc1",
            "depth_2q_delta_pct",
            "two-qubit depth reduction (%)",
            "circuit_base",
        ),
        paired_metric_summary(
            first_last,
            "Qiskit 1.3.3 to 2.5.0rc1",
            "gate_2q_delta_pct",
            "two-qubit gate reduction (%)",
            "circuit_base",
        ),
    ]
    write_csv(tables / "qiskit_first_last_paired_summary.csv", paired_rows)

    with (tables / "metriq_seed_level_first_last_deltas.csv").open(
        "r", encoding="utf-8", newline=""
    ) as f:
        metriq = list(csv.DictReader(f))
    for row in metriq:
        row["seed_cluster"] = f"{row['backend_or_device']}::{row['seed']}"
    metriq_rows = [
        paired_metric_summary(
            metriq,
            "qiskit-metriq 0.18.0 to 0.45.2",
            "depth_delta_pct",
            "total depth reduction (%)",
            "seed",
        ),
        paired_metric_summary(
            metriq,
            "qiskit-metriq 0.18.0 to 0.45.2",
            "gate_count_delta_pct",
            "total gate-count reduction (%)",
            "seed",
        ),
    ]
    write_csv(tables / "metriq_seed_paired_summary.csv", metriq_rows)

    with (tables / "benchpress_topology_penalty_cells.csv").open(
        "r", encoding="utf-8", newline=""
    ) as f:
        topology_cells = list(csv.DictReader(f))
    topology_groups: dict[str, list[dict]] = defaultdict(list)
    for row in topology_cells:
        topology_groups[row["topology"]].append(row)
    topology_summary = []
    for topology, group in sorted(topology_groups.items()):
        for key, label in [
            ("runtime_ratio_vs_all_to_all", "runtime ratio"),
            ("depth_2q_ratio_vs_all_to_all", "two-qubit depth ratio"),
            ("gate_2q_ratio_vs_all_to_all", "two-qubit gate ratio"),
        ]:
            vals = [float(row[key]) for row in group if row.get(key, "")]
            log_vals = [math.log(value) for value in vals if value > 0]
            effect, p_value = rank_biserial(log_vals)
            topology_summary.append(
                {
                    "topology": topology,
                    "metric": label,
                    "n": len(vals),
                    "median_ratio": fmt(median(vals) if vals else None),
                    "q25_ratio": fmt(quantile(vals, 0.25)),
                    "q75_ratio": fmt(quantile(vals, 0.75)),
                    "above_one_n": sum(value > 1 for value in vals),
                    "equal_one_n": sum(value == 1 for value in vals),
                    "below_one_n": sum(value < 1 for value in vals),
                    "rank_biserial_log_ratio": fmt(effect),
                    "wilcoxon_p_vs_one": fmt(p_value),
                }
            )
    write_csv(tables / "topology_penalty_inference_summary.csv", topology_summary)

    with (tables / "benchpress_cross_sdk_matched_cells.csv").open(
        "r", encoding="utf-8", newline=""
    ) as f:
        cross = list(csv.DictReader(f))
    cross_summary = []
    for sdk_label in sorted({row["sdk_version"] for row in cross}):
        subset = [row for row in cross if row["sdk_version"] == sdk_label]
        runtime = [
            float(row["runtime_ratio_vs_qiskit_250rc1"])
            for row in subset
            if row["runtime_ratio_vs_qiskit_250rc1"]
        ]
        depth = [
            float(row["depth_ratio_vs_qiskit_250rc1"])
            for row in subset
            if row["depth_ratio_vs_qiskit_250rc1"]
        ]
        cross_summary.append(
            {
                "sdk_version": sdk_label,
                "matched_cells": len(subset),
                "runtime_valid_n": len(runtime),
                "depth_valid_n": len(depth),
                "runtime_ratio_median_vs_qiskit": fmt(
                    median(runtime) if runtime else None
                ),
                "runtime_ratio_q25": fmt(quantile(runtime, 0.25)),
                "runtime_ratio_q75": fmt(quantile(runtime, 0.75)),
                "depth_ratio_median_vs_qiskit": fmt(median(depth) if depth else None),
                "depth_ratio_q25": fmt(quantile(depth, 0.25)),
                "depth_ratio_q75": fmt(quantile(depth, 0.75)),
            }
        )
    write_csv(tables / "cross_sdk_descriptive_summary.csv", cross_summary)

    bench_attempts = [row for row in rows if row["source"] == "benchpress_public"]
    status_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in bench_attempts:
        status_groups[(row["sdk"], row["sdk_version"])].append(row)
    status_rows = []
    for (sdk, version), group in sorted(
        status_groups.items(), key=lambda item: (item[0][0], version_key(item[0][1]))
    ):
        counts = {
            status: sum(row["status"] == status for row in group)
            for status in ["passed", "failed", "xfailed", "skipped"]
        }
        status_rows.append(
            {
                "sdk": sdk,
                "sdk_version": version,
                "attempted": len(group),
                **counts,
                "pass_rate_pct": fmt(100 * counts["passed"] / len(group)),
                "nonpass_rate_pct": fmt(
                    100 * (len(group) - counts["passed"]) / len(group)
                ),
            }
        )
    write_csv(tables / "benchpress_attempt_status_by_sdk_version.csv", status_rows)

    sensitivity = []
    for summary in paired_rows + metriq_rows:
        sensitivity.append(
            {
                "analysis": summary["analysis"],
                "metric": summary["metric"],
                "mean": summary.get("mean", ""),
                "median": summary.get("median", ""),
                "trimmed_mean_1pct": summary.get("trimmed_mean_1pct", ""),
                "conclusion_direction_consistent": str(
                    all(
                        float(summary.get(key, 0) or 0) >= 0
                        for key in ["mean", "median", "trimmed_mean_1pct"]
                    )
                ).lower(),
            }
        )
    write_csv(tables / "sensitivity_analysis_summary.csv", sensitivity)
