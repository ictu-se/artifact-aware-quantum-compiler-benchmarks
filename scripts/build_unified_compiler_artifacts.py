#!/usr/bin/env python3
"""Build the provenance-preserving artifact table used by Paper 11.

Benchpress is parsed from the original pytest-benchmark JSON files so failed,
skipped, and xfailed transpilation attempts remain visible. qiskit-metriq rows
are parsed from the historical pipe-delimited CSV files. Total-circuit and
two-qubit metrics remain separate throughout the schema.
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median


ROOT = Path(__file__).resolve().parents[1]
PAPER = Path(__file__).resolve().parents[1]
BENCHPRESS_ROOT = ROOT / "data/benchpress_public"
METRIQ_DIR = ROOT / "data/qiskit_metriq/benchmarking/results"

SOURCE_COMMITS = {
    "benchpress_public": "58b52b17fcf4e0ebb9c2a9afc56b89fc8a89c39f",
    "qiskit_metriq": "a79d8a66d19e8b7a4e5035f32004017252c06cfa",
}

FIELDNAMES = [
    "artifact_id",
    "source",
    "source_file",
    "source_repo_commit",
    "sdk",
    "sdk_version",
    "compiler_environment",
    "benchpress_version",
    "run_datetime",
    "machine_cpu",
    "machine_system",
    "machine_release",
    "python_version",
    "benchmark_suite",
    "benchmark_group",
    "benchmark_name",
    "benchmark_fullname",
    "benchmark_family",
    "circuit_name",
    "workload_id_raw",
    "workload_id_normalized",
    "topology",
    "backend_or_device",
    "optimization_level",
    "seed",
    "input_num_qubits",
    "output_num_qubits",
    "output_depth",
    "output_depth_2q",
    "output_gate_count",
    "output_gate_count_2q",
    "runtime_mean_s",
    "runtime_median_s",
    "runtime_min_s",
    "runtime_max_s",
    "runtime_stddev_s",
    "rounds",
    "attempt_duration_s",
    "status",
    "failure_summary",
    "timeout_flag",
]


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def as_float(value: object) -> str:
    if value in (None, ""):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if math.isnan(number):
        return ""
    return f"{number:.17g}"


def as_int(value: object) -> str:
    if value in (None, ""):
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return ""


def version_from_name(name: str) -> str:
    match = re.search(r"(\d+\.\d+(?:\.\d+)?(?:\.?rc\d+)?)", name, re.I)
    if not match:
        return "unknown"
    return match.group(1).replace(".rc", "rc")


def canonical_version(value: object) -> str:
    return str(value or "unknown").replace(".rc", "rc")


def infer_sdk(path: Path, data: dict) -> tuple[str, str, dict]:
    parts = [part.lower() for part in path.parts]
    if "qiskit" in parts:
        info = data.get("qiskit_info") or {}
        return (
            "qiskit",
            canonical_version(info.get("qiskit") or version_from_name(path.name)),
            info,
        )
    if "qpanda" in parts:
        info = data.get("qpanda_info") or {}
        return "qpanda", version_from_name(path.name), info
    if "tket" in parts:
        info = data.get("pytket_info") or {}
        match = re.search(r"tket[\\/](\d+\.\d+\.\d+)", str(path).replace("\\", "/"))
        return (
            "tket",
            match.group(1)
            if match
            else str(info.get("pytket") or version_from_name(path.name)),
            info,
        )
    return "unknown", version_from_name(path.name), {}


def node_param(nodeid: str) -> str:
    match = re.search(r"\[([^\]]+)\]$", nodeid)
    return match.group(1) if match else ""


def node_test_name(nodeid: str) -> str:
    return nodeid.split("::")[-1]


def topology_from_text(param: str, nodeid: str, source_file: Path) -> str:
    combined = " ".join([param, nodeid, source_file.stem]).lower()
    for topology in ["all-to-all", "heavy-hex", "linear", "square", "device"]:
        if topology in combined:
            return topology
    return "unspecified"


def topology_from_benchmark(benchmark: dict, source_file: Path) -> str:
    params = benchmark.get("params") or {}
    circ_and_topo = params.get("circ_and_topo")
    if isinstance(circ_and_topo, list) and len(circ_and_topo) >= 2:
        return str(circ_and_topo[1])
    param = str(benchmark.get("param") or "")
    fullname = str(benchmark.get("fullname") or "")
    return topology_from_text(param, fullname, source_file)


def family_from_values(param: str, name: str, extra: dict | None = None) -> str:
    extra = extra or {}
    for key in [
        "ham_category",
        "ham_primary_type",
        "benchmark_family",
        "algorithm_family",
    ]:
        if extra.get(key) not in (None, ""):
            return str(extra[key])
    value = param or name
    token = re.split(r"[_\-\[]", value, maxsplit=1)[0]
    return token or "unknown"


def normalize_family(family: str, group: str, param: str) -> str:
    if re.fullmatch(r"\d+", family) and "abstract" in group.lower():
        return f"abstract_qasmbench_{family}q"
    if re.fullmatch(r"\d+", family) and re.match(
        r"^\d+-(all-to-all|heavy-hex|square|linear|device|unspecified)$", param
    ):
        return f"abstract_qasmbench_{family}q"
    return family


def normalized_workload_id(fullname: str, name: str, param: str) -> str:
    raw = fullname or name or param
    raw = raw.replace("\\", "/")
    raw = re.sub(r"^(qiskit|tket|qpanda)_gym/", "sdk_gym/", raw)
    raw = re.sub(
        r"[-_](all-to-all|heavy-hex|linear|square|device|unspecified)(?=\])",
        "",
        raw,
        flags=re.I,
    )
    raw = re.sub(
        r"[-_](all-to-all|heavy-hex|linear|square|device|unspecified)$",
        "",
        raw,
        flags=re.I,
    )
    return raw


def machine_fields(data: dict) -> dict[str, str]:
    machine = data.get("machine_info") or {}
    cpu = machine.get("cpu") or {}
    return {
        "machine_cpu": str(cpu.get("brand_raw") or machine.get("processor") or ""),
        "machine_system": str(machine.get("system") or ""),
        "machine_release": str(machine.get("release") or ""),
        "python_version": str(
            machine.get("python_version") or cpu.get("python_version") or ""
        ),
    }


def base_benchpress_row(
    path: Path, data: dict, sdk: str, version: str, env: dict
) -> dict:
    rel = path.relative_to(BENCHPRESS_ROOT).as_posix()
    row = {field: "" for field in FIELDNAMES}
    row.update(
        {
            "source": "benchpress_public",
            "source_file": rel,
            "source_repo_commit": SOURCE_COMMITS["benchpress_public"],
            "sdk": sdk,
            "sdk_version": version,
            "compiler_environment": json.dumps(
                env, sort_keys=True, separators=(",", ":")
            ),
            "benchpress_version": str(data.get("version") or ""),
            "run_datetime": str(data.get("datetime") or ""),
            "benchmark_suite": "benchpress",
        }
    )
    row.update(machine_fields(data))
    return row


def exception_summary(value: object) -> str:
    text = str(value or "").strip()
    if text in ("", "None"):
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    # The final line generally contains the exception class/message; keep the
    # compact summary and provenance pointer instead of embedding full traces.
    final = lines[-1]
    # Pytest skip tuples include upstream developer paths; retain the reason only.
    if "Skipped:" in final:
        final = "Skipped:" + final.split("Skipped:", 1)[1].rstrip("\"') ")
    final = re.sub(r"/(?:home|Users|private|tmp)/[^\s\"']+", "<source-path>", final)
    return final[:1000]


def build_benchpress_rows() -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    audits: list[dict] = []
    artifact_counter = 0
    for path in sorted(BENCHPRESS_ROOT.rglob("*.json")):
        data = read_json(path)
        sdk, version, env = infer_sdk(path, data)
        base = base_benchpress_row(path, data, sdk, version, env)
        successful_by_fullname: dict[str, dict] = {}
        for benchmark in data.get("benchmarks", []):
            group = str(benchmark.get("group") or "")
            if "transpile" not in group.lower():
                continue
            fullname = str(benchmark.get("fullname") or "")
            successful_by_fullname[fullname] = benchmark

        dumps = data.get("test_dumps") or {}
        filtered_counts: Counter[str] = Counter()
        used_successes: set[str] = set()
        for status in ["passed", "failed", "xfailed", "skipped"]:
            for nodeid, outcome in (dumps.get(status) or {}).items():
                if "transpile" not in nodeid.lower():
                    continue
                filtered_counts[status] += 1
                benchmark = (
                    successful_by_fullname.get(nodeid) if status == "passed" else None
                )
                if benchmark is not None:
                    used_successes.add(nodeid)
                param = str((benchmark or {}).get("param") or node_param(nodeid))
                name = str((benchmark or {}).get("name") or node_test_name(nodeid))
                group = str((benchmark or {}).get("group") or nodeid.split("::", 1)[0])
                fullname = str((benchmark or {}).get("fullname") or nodeid)
                extra = (benchmark or {}).get("extra_info") or {}
                stats = (benchmark or {}).get("stats") or {}
                topology = (
                    topology_from_benchmark(benchmark, path)
                    if benchmark
                    else topology_from_text(param, nodeid, path)
                )
                family = normalize_family(
                    family_from_values(param, name, extra), group, param
                )
                artifact_counter += 1
                row = dict(base)
                row.update(
                    {
                        "artifact_id": f"bp_attempt_{artifact_counter:05d}",
                        "benchmark_group": group,
                        "benchmark_name": name,
                        "benchmark_fullname": fullname,
                        "benchmark_family": family,
                        "circuit_name": param,
                        "workload_id_raw": fullname or name or param,
                        "workload_id_normalized": normalized_workload_id(
                            fullname, name, param
                        ),
                        "topology": topology,
                        "backend_or_device": topology,
                        "input_num_qubits": as_int(extra.get("input_num_qubits")),
                        "output_num_qubits": as_int(extra.get("output_num_qubits")),
                        "output_depth_2q": as_float(extra.get("output_depth_2q")),
                        "output_gate_count_2q": as_float(
                            extra.get("output_gate_count_2q")
                        ),
                        "runtime_mean_s": as_float(stats.get("mean")),
                        "runtime_median_s": as_float(stats.get("median")),
                        "runtime_min_s": as_float(stats.get("min")),
                        "runtime_max_s": as_float(stats.get("max")),
                        "runtime_stddev_s": as_float(stats.get("stddev")),
                        "rounds": as_int(stats.get("rounds")),
                        "attempt_duration_s": as_float((outcome or {}).get("duration")),
                        "status": status,
                        "failure_summary": exception_summary(
                            (outcome or {}).get("exception")
                        ),
                        "timeout_flag": "1"
                        if "timeout"
                        in str((outcome or {}).get("exception", "")).lower()
                        else "0",
                    }
                )
                rows.append(row)

        missing_success_dumps = sorted(set(successful_by_fullname) - used_successes)
        for fullname in missing_success_dumps:
            benchmark = successful_by_fullname[fullname]
            param = str(benchmark.get("param") or "")
            name = str(benchmark.get("name") or node_test_name(fullname))
            group = str(benchmark.get("group") or "")
            extra = benchmark.get("extra_info") or {}
            stats = benchmark.get("stats") or {}
            topology = topology_from_benchmark(benchmark, path)
            family = normalize_family(
                family_from_values(param, name, extra), group, param
            )
            artifact_counter += 1
            row = dict(base)
            row.update(
                {
                    "artifact_id": f"bp_attempt_{artifact_counter:05d}",
                    "benchmark_group": group,
                    "benchmark_name": name,
                    "benchmark_fullname": fullname,
                    "benchmark_family": family,
                    "circuit_name": param,
                    "workload_id_raw": fullname or name or param,
                    "workload_id_normalized": normalized_workload_id(
                        fullname, name, param
                    ),
                    "topology": topology,
                    "backend_or_device": topology,
                    "input_num_qubits": as_int(extra.get("input_num_qubits")),
                    "output_num_qubits": as_int(extra.get("output_num_qubits")),
                    "output_depth_2q": as_float(extra.get("output_depth_2q")),
                    "output_gate_count_2q": as_float(extra.get("output_gate_count_2q")),
                    "runtime_mean_s": as_float(stats.get("mean")),
                    "runtime_median_s": as_float(stats.get("median")),
                    "runtime_min_s": as_float(stats.get("min")),
                    "runtime_max_s": as_float(stats.get("max")),
                    "runtime_stddev_s": as_float(stats.get("stddev")),
                    "rounds": as_int(stats.get("rounds")),
                    "status": "passed",
                    "timeout_flag": "0",
                }
            )
            rows.append(row)

        normalized_counts = Counter(
            row["status"] for row in rows if row["source_file"] == base["source_file"]
        )
        audits.append(
            {
                "source_file": base["source_file"],
                "sdk": sdk,
                "sdk_version": version,
                "raw_transpile_passed": filtered_counts["passed"],
                "raw_transpile_failed": filtered_counts["failed"],
                "raw_transpile_xfailed": filtered_counts["xfailed"],
                "raw_transpile_skipped": filtered_counts["skipped"],
                "benchmark_success_rows": len(successful_by_fullname),
                "successful_benchmarks_missing_from_dumps": len(missing_success_dumps),
                "normalized_passed": normalized_counts["passed"],
                "normalized_failed": normalized_counts["failed"],
                "normalized_xfailed": normalized_counts["xfailed"],
                "normalized_skipped": normalized_counts["skipped"],
            }
        )
    return rows, audits


def parse_metriq_filename(path: Path) -> dict:
    match = re.match(
        r"(?P<circuit>.+)-qiskit(?P<version>[0-9.]+)-(?P<device>.+)\.csv$", path.name
    )
    return (
        match.groupdict()
        if match
        else {"circuit": path.stem, "version": "", "device": ""}
    )


def build_metriq_rows(start_index: int) -> list[dict]:
    rows = []
    counter = start_index
    for path in sorted(METRIQ_DIR.glob("*.csv")):
        meta = parse_metriq_filename(path)
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter="|")
            for raw in reader:
                counter += 1
                circuit = raw.get("Qasm file") or meta["circuit"]
                row = {field: "" for field in FIELDNAMES}
                row.update(
                    {
                        "artifact_id": f"metriq_attempt_{counter:05d}",
                        "source": "qiskit_metriq",
                        "source_file": str(path.relative_to(ROOT)),
                        "source_repo_commit": SOURCE_COMMITS["qiskit_metriq"],
                        "sdk": "qiskit",
                        "sdk_version": meta["version"],
                        "benchmark_suite": "qiskit-metriq",
                        "benchmark_group": "ex1_226",
                        "benchmark_name": raw.get("Method", ""),
                        "benchmark_fullname": circuit,
                        "benchmark_family": "metriq_ex1",
                        "circuit_name": circuit,
                        "workload_id_raw": circuit,
                        "workload_id_normalized": circuit,
                        "backend_or_device": raw.get("Platform") or meta["device"],
                        "optimization_level": as_int(raw.get("Opt level")),
                        "seed": as_int(raw.get("Seed")),
                        "output_depth": as_float(raw.get("Circuit depth")),
                        "output_gate_count": as_float(raw.get("Gate count")),
                        "status": "passed",
                        "timeout_flag": "0",
                    }
                )
                rows.append(row)
    return rows


def numeric(row: dict, key: str) -> float | None:
    value = row.get(key, "")
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize_groups(rows: list[dict], keys: list[str], out_path: Path) -> None:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(key, "") for key in keys)].append(row)
    out_rows = []
    for group_key, group_rows in sorted(groups.items()):
        successful = [row for row in group_rows if row["status"] == "passed"]
        out = {key: value for key, value in zip(keys, group_key)}
        out.update(
            {
                "n_attempted": len(group_rows),
                "n_passed": sum(row["status"] == "passed" for row in group_rows),
                "n_failed": sum(row["status"] == "failed" for row in group_rows),
                "n_xfailed": sum(row["status"] == "xfailed" for row in group_rows),
                "n_skipped": sum(row["status"] == "skipped" for row in group_rows),
            }
        )
        out["pass_rate_pct"] = (
            f"{100 * out['n_passed'] / out['n_attempted']:.6g}"
            if out["n_attempted"]
            else ""
        )
        for metric in [
            "runtime_mean_s",
            "output_depth",
            "output_depth_2q",
            "output_gate_count",
            "output_gate_count_2q",
        ]:
            values = [
                value
                for row in successful
                if (value := numeric(row, metric)) is not None
            ]
            out[f"{metric}_n"] = len(values)
            out[f"{metric}_mean"] = f"{mean(values):.6g}" if values else ""
            out[f"{metric}_median"] = f"{median(values):.6g}" if values else ""
        out_rows.append(out)
    write_csv(out_path, out_rows)


def top_version_changes(rows: list[dict], out_path: Path) -> None:
    metriq = [
        row
        for row in rows
        if row["source"] == "qiskit_metriq" and row["status"] == "passed"
    ]
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in metriq:
        groups[(row["sdk_version"], row["backend_or_device"])].append(row)
    summary = []
    for (version, device), group_rows in groups.items():
        depths = [
            v for row in group_rows if (v := numeric(row, "output_depth")) is not None
        ]
        gates = [
            v
            for row in group_rows
            if (v := numeric(row, "output_gate_count")) is not None
        ]
        summary.append(
            {
                "sdk_version": version,
                "backend_or_device": device,
                "n": len(group_rows),
                "depth_mean": mean(depths),
                "gate_count_mean": mean(gates),
            }
        )
    by_device: dict[str, list[dict]] = defaultdict(list)
    for row in summary:
        by_device[row["backend_or_device"]].append(row)
    out_rows = []
    for device, device_rows in by_device.items():
        device_rows.sort(
            key=lambda row: tuple(int(x) for x in row["sdk_version"].split("."))
        )
        for prev, cur in zip(device_rows, device_rows[1:]):
            out_rows.append(
                {
                    "backend_or_device": device,
                    "from_version": prev["sdk_version"],
                    "to_version": cur["sdk_version"],
                    "n_from": prev["n"],
                    "n_to": cur["n"],
                    "depth_mean_delta": f"{cur['depth_mean'] - prev['depth_mean']:.6g}",
                    "gate_count_mean_delta": f"{cur['gate_count_mean'] - prev['gate_count_mean']:.6g}",
                    "depth_mean_from": f"{prev['depth_mean']:.6g}",
                    "depth_mean_to": f"{cur['depth_mean']:.6g}",
                    "gate_count_mean_from": f"{prev['gate_count_mean']:.6g}",
                    "gate_count_mean_to": f"{cur['gate_count_mean']:.6g}",
                }
            )
    write_csv(out_path, out_rows)


def validate_unique_success_keys(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for row in rows:
        if row["source"] != "benchpress_public" or row["status"] != "passed":
            continue
        key = (
            row["source"],
            row["sdk"],
            row["sdk_version"],
            row["workload_id_normalized"],
            row["topology"],
        )
        groups[key].append(row)
    collisions = []
    for key, vals in groups.items():
        if len(vals) <= 1:
            continue
        for row in vals:
            collisions.append(
                {
                    "source": key[0],
                    "sdk": key[1],
                    "sdk_version": key[2],
                    "workload_id_normalized": key[3],
                    "topology": key[4],
                    "artifact_id": row["artifact_id"],
                    "benchmark_fullname": row["benchmark_fullname"],
                }
            )
    return collisions


def main() -> None:
    benchpress_rows, status_audit = build_benchpress_rows()
    rows = benchpress_rows + build_metriq_rows(len(benchpress_rows))
    results = PAPER / "results"
    tables = PAPER / "tables"
    write_csv(results / "unified_compiler_artifacts.csv", rows, FIELDNAMES)
    write_csv(tables / "benchpress_status_reconciliation.csv", status_audit)
    collisions = validate_unique_success_keys(rows)
    write_csv(
        tables / "workload_id_collision_audit.csv",
        collisions,
        [
            "source",
            "sdk",
            "sdk_version",
            "workload_id_normalized",
            "topology",
            "artifact_id",
            "benchmark_fullname",
        ],
    )
    if collisions:
        raise SystemExit(
            f"Workload-ID collision audit failed with {len(collisions)} rows"
        )

    summarize_groups(rows, ["source"], tables / "coverage_by_source.csv")
    summarize_groups(
        rows, ["source", "sdk", "sdk_version"], tables / "coverage_by_sdk_version.csv"
    )
    summarize_groups(
        rows,
        ["source", "benchmark_suite", "benchmark_family"],
        tables / "coverage_by_family.csv",
    )
    summarize_groups(rows, ["source", "topology"], tables / "coverage_by_topology.csv")
    summarize_groups(
        rows,
        ["source", "backend_or_device"],
        tables / "coverage_by_backend_or_device.csv",
    )
    top_version_changes(rows, tables / "qiskit_metriq_version_deltas.csv")

    summary = {
        "rows": len(rows),
        "benchpress_attempt_rows": len(benchpress_rows),
        "benchpress_passed_rows": sum(
            row["source"] == "benchpress_public" and row["status"] == "passed"
            for row in rows
        ),
        "benchpress_failed_rows": sum(
            row["source"] == "benchpress_public" and row["status"] == "failed"
            for row in rows
        ),
        "benchpress_xfailed_rows": sum(
            row["source"] == "benchpress_public" and row["status"] == "xfailed"
            for row in rows
        ),
        "benchpress_skipped_rows": sum(
            row["source"] == "benchpress_public" and row["status"] == "skipped"
            for row in rows
        ),
        "qiskit_metriq_rows": sum(row["source"] == "qiskit_metriq" for row in rows),
        "workload_id_collision_rows": len(collisions),
        "source_commits": SOURCE_COMMITS,
    }
    (results / "unified_compiler_artifacts_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
