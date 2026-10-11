# Artifact-aware quantum compiler benchmark analysis

Code and experimental results for *Artifact-Aware Performance Analysis of Quantum Compiler Benchmarks Across SDK Versions and Topologies*, by Nguyen The-Vinh.

This package reanalyses pinned public compiler outputs. It reconstructs outcomes, comparison keys, distributions, paired changes, clustered intervals, enrichment coverage, and numerical figures and tables. Historical compiler binaries are not re-executed.

## Install and reproduce

Use Python 3.11 and a fresh environment:

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
sh reproduce.sh
```

The workflow downloads approximately 544 MB across 300 upstream inputs, verifies every SHA-256 hash, rebuilds the analysis and presentation, and runs both scientific validators. Paths are relative to this checkout. If verified inputs are already cached, use `sh reproduce.sh --offline`. To check existing results without rerunning analysis, use `sh reproduce.sh --verify-only`.

Individual entry points are `scripts/run_analysis.py`, `scripts/render_full_manuscript.py`, `scripts/render_workflow_evidence.py`, `scripts/validate.py`, and `scripts/validate_full_release.py`; run each with the environment's Python interpreter.

## Outputs and exclusions

- `results/`: normalized outcomes and source-preserving summaries.
- `tables/`: 39 complete derived analysis tables.
- `full_manuscript_assets/`: eight analytical vector figures and one empirical workflow-accounting figure. Rendering also generates thirteen numerical table fragments locally; these fragments are excluded from Git.
- `verification/`: source provenance, scientific checks, workflow accounting, and regeneration hashes.

Static notation and method-description tables are authoring material. Manuscript sources and PDFs, journal templates, cover letters, reviewer responses, local notes, environments, caches, and build products are excluded. Versioned vector PDFs contain individual data plots, not manuscript pages.

## Inputs and provenance

| Source | Pinned commit | Inputs |
|---|---|---:|
| [Benchpress](https://github.com/Qiskit/benchpress) | `58b52b17fcf4e0ebb9c2a9afc56b89fc8a89c39f` | 16 result artifacts |
| [qiskit-metriq](https://github.com/qiskit-community/qiskit-metriq) | `a79d8a66d19e8b7a4e5035f32004017252c06cfa` | 30 historical result files |
| [QASMBench](https://github.com/pnnl/QASMBench) | `357b942396d5c2b7cbc1c229c585a6ef5ccaebac` | 254 circuit inputs |

`data/source_manifest.json` identifies source roles. `data/source_file_manifest.csv` records each input, byte size, and hash. Downloaded inputs are excluded from Git and retain their upstream terms. They are also preserved in the [archived analysis release](https://doi.org/10.5281/zenodo.23150707). Upstream attribution and notices are under `third_party/`. This package's MIT license applies to original code, not to upstream inputs.

## Parameters and interpretation

The manifest fixes the source snapshots. Workload keys retain test path, class, name, and parameters; only the SDK root and terminal topology tokens are normalized. Duplicate condition keys fail validation.

The analysis retains 15,652 outcomes and 15,318 successful measurements. Qiskit endpoint matching retains 1,032 cells and 363 logical-workload clusters. Structural percentages exclude sixteen zero baselines, retaining 1,016 cells. Adjacent matching yields 9,288 comparisons; cross-SDK matching yields 928 shared cells.

Ordinary medians average the two central values for even support. Upper percentiles use nearest rank. Bootstrap intervals use 2,000 replicates and random seed 20260716. Qiskit resamples logical workloads with their topology observations; historical qiskit-metriq resamples 100 seed identifiers with both backends. One-percent trimmed summaries are sensitivity diagnostics. The definitions are in `scripts/build_expanded_analytics.py` and checked by the validators.

Runtime summaries aggregate original per-record mean timing. Total-circuit and two-qubit measurements remain separate. Cross-SDK estimates are descriptive because release, interpreter, defaults, and execution-path effects remain confounded. Enrichment is an exact-unique identity audit; fallback features are diagnostics, not explanatory covariates. Top-forty runtime ranking identifies expensive recorded cases without testing statistical outlier status.

## Citation

Primary research references are [Benchpress](https://doi.org/10.1038/s43588-025-00792-y) and [QASMBench](https://doi.org/10.1145/3550488). The pinned qiskit-metriq commit identifies the historical observations used. Software citation metadata is in `CITATION.cff`.

Nguyen The-Vinh, Thai Nguyen University of Information and Communication Technology. Contact: vinhnt@ictu.edu.vn.
