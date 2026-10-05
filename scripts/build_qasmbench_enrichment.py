#!/usr/bin/env python3
"""Conservative QASMBench enrichment for Paper 11.

The script intentionally uses exact normalized keys only. Ambiguous keys are
reported but not attached to Benchpress rows.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = Path(__file__).resolve().parents[1]
QASMBENCH = ROOT / "data/qasmbench"
UNIFIED = PAPER / "results/unified_compiler_artifacts.csv"


TOPOLOGY_SUFFIXES = ("all-to-all", "heavy-hex", "square", "linear", "device", "unspecified")


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def normalize_key(text: str) -> str:
    key = text.strip().lower()
    key = key.replace(".qasm3", "").replace(".qasm", "")
    key = re.sub(r"_transpiled$", "", key)
    key = re.sub(r"^ghz_state_", "ghz_", key)
    key = key.replace("swap_test_", "swap_")
    key = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return key


def circuit_base(name: str, topology: str = "") -> str:
    base = name.strip()
    for suffix in TOPOLOGY_SUFFIXES + tuple([topology] if topology else []):
        for sep in ("-", "_"):
            token = f"{sep}{suffix}"
            if base.endswith(token):
                base = base[: -len(token)]
    return normalize_key(base)


def parse_qasm(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""
    qubits = 0
    for match in re.finditer(r"\bqreg\s+\w+\[(\d+)\]", text):
        qubits += int(match.group(1))
    for match in re.finditer(r"\bqubit(?:\[(\d+)\])?\s+\w+", text):
        qubits += int(match.group(1) or 1)
    clean_lines = []
    for line in text.splitlines():
        line = line.split("//", 1)[0].strip()
        if line:
            clean_lines.append(line)
    gate_lines = [
        line
        for line in clean_lines
        if not line.startswith(("OPENQASM", "include", "qreg", "creg", "bit", "qubit"))
        and not line.startswith(("gate ", "opaque ", "def "))
        and not line in ("{", "}")
    ]
    two_qubit_ops = 0
    for line in gate_lines:
        if re.match(r"\b(cx|cz|swap|rzz|crx|cry|crz|cu1|cu3|cp|ecr)\b", line):
            two_qubit_ops += 1
    result = {
        "qasm_qubits": str(qubits) if qubits else "",
        "qasm_ops_approx": str(len(gate_lines)),
        "qasm_two_qubit_ops_approx": str(two_qubit_ops),
        "qasm_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "parser_status": "fallback_static",
        "parser_error": "",
    }
    if path.suffix.lower() == ".qasm" and not path.stem.lower().endswith("_transpiled"):
        try:
            from qiskit import qasm2  # type: ignore

            circuit = qasm2.loads(text)
            result["qasm_qubits"] = str(circuit.num_qubits)
            result["qasm_ops_approx"] = str(len(circuit.data))
            result["qasm_two_qubit_ops_approx"] = str(sum(len(item.qubits) == 2 for item in circuit.data))
            result["parser_status"] = "qiskit_qasm2"
        except Exception as exc:
            result["parser_error"] = str(exc)[:500]
    else:
        result["parser_error"] = "Transpiled or OpenQASM 3 file; static fallback used"
    return result


def build_inventory() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(QASMBENCH.rglob("*")):
        if path.suffix.lower() not in (".qasm", ".qasm3"):
            continue
        rel = path.relative_to(QASMBENCH)
        variant = "transpiled" if path.stem.lower().endswith("_transpiled") else "raw"
        scale = rel.parts[0] if len(rel.parts) > 1 else ""
        family_dir = rel.parts[1] if len(rel.parts) > 2 else path.parent.name
        keys = sorted({normalize_key(path.stem), normalize_key(family_dir)})
        metrics = parse_qasm(path)
        rows.append(
            {
                "qasm_path": str(rel),
                "scale": scale,
                "family_dir": family_dir,
                "file_stem": path.stem,
                "variant": variant,
                "match_keys": ";".join(keys),
                **metrics,
            }
        )
    return rows


def build_key_index(inventory: list[dict]) -> tuple[dict[str, dict], set[str]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in inventory:
        if row["variant"] != "raw":
            continue
        for key in row["match_keys"].split(";"):
            if key:
                buckets[key].append(row)
    unique = {}
    ambiguous = set()
    for key, vals in buckets.items():
        paths = {row["qasm_path"] for row in vals}
        if len(paths) == 1:
            unique[key] = vals[0]
        else:
            ambiguous.add(key)
    return unique, ambiguous


def enrich_benchpress(inventory: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    unique, ambiguous = build_key_index(inventory)
    rows = [
        row
        for row in read_csv(UNIFIED)
        if row["source"] == "benchpress_public" and row.get("status", "passed") == "passed"
    ]
    enriched: list[dict] = []
    status_counts = Counter()
    for row in rows:
        key = circuit_base(row["circuit_name"], row["topology"])
        if key in unique:
            match = unique[key]
            status = "matched_exact_unique"
        elif key in ambiguous:
            match = {}
            status = "ambiguous_key"
        else:
            match = {}
            status = "unmatched"
        status_counts[status] += 1
        enriched.append(
            {
                "artifact_id": row["artifact_id"],
                "sdk": row["sdk"],
                "sdk_version": row["sdk_version"],
                "benchmark_family": row["benchmark_family"],
                "circuit_name": row["circuit_name"],
                "topology": row["topology"],
                "input_num_qubits": row["input_num_qubits"],
                "normalized_circuit_key": key,
                "match_status": status,
                "qasm_path": match.get("qasm_path", ""),
                "qasm_scale": match.get("scale", ""),
                "qasm_family_dir": match.get("family_dir", ""),
                "qasm_qubits": match.get("qasm_qubits", ""),
                "qasm_ops_approx": match.get("qasm_ops_approx", ""),
                "qasm_two_qubit_ops_approx": match.get("qasm_two_qubit_ops_approx", ""),
                "qasm_sha256": match.get("qasm_sha256", ""),
                "parser_status": match.get("parser_status", ""),
            }
        )
    family_counts: dict[tuple[str, str], int] = Counter((row["benchmark_family"], row["match_status"]) for row in enriched)
    family_rows = [
        {"benchmark_family": family, "match_status": status, "rows": str(count)}
        for (family, status), count in sorted(family_counts.items())
    ]
    summary = [
        {"metric": "qasmbench_inventory_rows", "value": str(len(inventory))},
        {"metric": "unique_raw_match_keys", "value": str(len(unique))},
        {"metric": "ambiguous_raw_match_keys", "value": str(len(ambiguous))},
        {"metric": "benchpress_rows", "value": str(len(rows))},
    ]
    for status, count in sorted(status_counts.items()):
        pct = 100 * count / len(rows) if rows else 0
        summary.append({"metric": f"benchpress_{status}_rows", "value": str(count)})
        summary.append({"metric": f"benchpress_{status}_pct", "value": f"{pct:.2f}"})
    return enriched, family_rows, summary


def main() -> None:
    inventory = build_inventory()
    enriched, family_rows, summary_rows = enrich_benchpress(inventory)
    write_csv(PAPER / "tables/qasmbench_circuit_inventory.csv", inventory)
    write_csv(PAPER / "tables/benchpress_qasmbench_enrichment.csv", enriched)
    write_csv(PAPER / "tables/qasmbench_enrichment_by_family.csv", family_rows)
    write_csv(PAPER / "tables/qasmbench_enrichment_summary.csv", summary_rows)
    payload = {
        "qasmbench_inventory_rows": len(inventory),
        "benchpress_enriched_rows": len(enriched),
        "summary": summary_rows[-10:],
    }
    (PAPER / "results/qasmbench_enrichment_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
