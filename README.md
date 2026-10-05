# Artifact-aware quantum compiler benchmark analysis

Reproducibility artifact for **Artifact-Aware Performance Analysis of Quantum Compiler Benchmarks Across SDK Versions and Topologies**.

This package reanalyses historical public compiler outputs. It reconstructs observations, matching keys, summaries, uncertainty estimates, and manuscript assets. It does not execute the historical compiler versions.

## Reproduce

Python 3.11 is the tested environment. Run these commands from a fresh checkout:

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
./reproduce.sh
```

The first command in the workflow downloads approximately 544 MB across 300 upstream files. Every file is checked against the committed SHA-256 manifest. Downloaded source files are cached under `data/` and excluded from Git. Derived data, analysis tables, vector figures, and table fragments are versioned in this repository.

`verification/validation.json` records the scientific checks and environment. `manuscript_assets/` contains publication assets, including native editable tables. `requirements-lock.txt` records the full tested dependency environment; `requirements.txt` pins the direct dependencies.

## Sources and provenance

| Source | Pinned commit | Included inputs |
|---|---|---|
| [Benchpress](https://github.com/Qiskit/benchpress) | `58b52b17fcf4e0ebb9c2a9afc56b89fc8a89c39f` | 16 benchmark result artifacts |
| [qiskit-metriq](https://github.com/qiskit-community/qiskit-metriq) | `a79d8a66d19e8b7a4e5035f32004017252c06cfa` | 30 historical circuit-result files |
| [QASMBench](https://github.com/pnnl/QASMBench) | `357b942396d5c2b7cbc1c229c585a6ef5ccaebac` | 254 circuit inputs |

`data/source_manifest.json` records source roles and upstream licensing information. `data/source_file_manifest.csv` specifies each selected relative path, size, and hash. Upstream inputs are fetched directly from their original repositories; their respective upstream terms apply. The Benchpress pinned data-only commit has no license file, as recorded in the manifest. No license for upstream inputs is inferred from this package's code license.

## Analysis conventions

- Outcome reconciliation retains 15,652 records: 12,652 Benchpress outcomes and 3,000 qiskit-metriq results. There are 15,318 successful measurements.
- Workload identities preserve test path, class, name, and parameter content; only SDK-root and terminal topology tokens are normalized. Duplicate condition keys are rejected.
- Qiskit endpoint matching retains 1,032 workload cells and 363 logical-workload clusters. Structural percentages use 1,016 nonzero-baseline pairs.
- Medians average the two central observations for even samples. Upper percentiles use nearest rank. Missing values and zero ratio denominators are excluded, never converted into zero changes.
- Runtime is the per-record mean elapsed time; reported workload distributions aggregate these means.
- Bootstrap intervals use 2,000 replicates and seed 20260716. Qiskit resamples logical workloads with their topology rows. qiskit-metriq resamples 100 seed identifiers with both backend observations together.
- Cross-SDK estimates are descriptive because release, interpreter, configuration, and execution-path effects remain confounded.
- Enrichment is an exact-key identity audit. Parser diagnostics are retained but approximate features are not used to explain runtime.

Exploratory row-level rank statistics are retained in the full derived tables for transparency. They are not the inferential basis of the manuscript because workload dependence requires the stated clustered resampling design.

## Contents

- `scripts/fetch_sources.py`: pinned source acquisition and hash verification.
- `scripts/run_analysis.py`: outcome ingestion, matching, summaries, bootstrap, and enrichment.
- `scripts/render_manuscript_assets.py`: readable vector figures and native tables.
- `scripts/validate.py`: source, key, denominator, metric, numerical, and portability checks.
- `results/`: unified outcomes and provenance-preserving summaries.
- `tables/`: full derived analyses, including observations omitted from compact manuscript displays.

## Attribution

Nguyen The-Vinh, Thai Nguyen University of Information and Communication Technology. Contact: vinhnt@ictu.edu.vn.

Primary benchmark references are [Benchpress](https://doi.org/10.1038/s43588-025-00792-y), [QASMBench](https://doi.org/10.1145/3550488), and the [Metriq technical report](https://doi.org/10.48550/arXiv.2603.08680). The qiskit-metriq source commit above identifies the historical data actually analyzed; the Metriq report is contextual documentation.
