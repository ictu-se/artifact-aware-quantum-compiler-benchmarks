"""Regenerate all numerical tables and figures of the full-length manuscript."""

from pathlib import Path
import json
import numpy as np
import pandas as pd
from packaging.version import Version
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

R = Path(__file__).resolve().parents[1]
O = R / "full_manuscript_assets"
O.mkdir(exist_ok=True)
plt.rcParams.update(
    {
        "axes.labelsize": "medium",
        "xtick.labelsize": "medium",
        "ytick.labelsize": "medium",
        "legend.fontsize": "medium",
        "pdf.fonttype": 42,
    }
)
BLUE = "#2166ac"
ORANGE = "#d97706"
GREEN = "#21855b"
TOPOS = ["all-to-all", "heavy-hex", "linear", "square", "device"]


def read(n):
    return pd.read_csv(R / "tables" / (n + ".csv"))


def fmt(x, d=2):
    if pd.isna(x):
        return "--"
    x = 0 if abs(float(x)) < 0.5 * 10 ** (-d) else x
    return f"{x:,.{d}f}"


def integer(x):
    return f"{int(x):,}"


def family(x):
    return (
        str(x)
        .replace("abstract_qasmbench_", "QASMBench ")
        .replace("condensedmatter", "Condensed matter")
        .replace("binaryoptimization", "Binary opt.")
        .replace("discreteoptimization", "Discrete opt.")
        .replace(".qasm", "")
        .replace("_", " ")
    )


def esc(x):
    return str(x).replace("_", r"\_").replace("%", r"\%")


def tab(n, caption, headers, rows, spec=None):
    spec = spec or "l" + "r" * (len(headers) - 1)
    t = (
        r"\begin{center}\begin{minipage}{\linewidth}\def\@captype{table}\centering"
        + "\n"
        + r"\caption{"
        + caption
        + "}\n"
        + r"\label{tab:"
        + str(n)
        + "}\n"
        + r"\begin{tabular}{"
        + spec
        + "}\n"
        + r"\toprule"
        + "\n"
        + " & ".join(headers)
        + r" \\"
        + "\n"
        + r"\midrule"
        + "\n"
    )
    t += (
        "\n".join(" & ".join(map(str, row)) + r" \\" for row in rows)
        + "\n"
        + r"\bottomrule\end{tabular}\end{minipage}\end{center}\par"
        + "\n"
    )
    (O / (f"table_{n:02}.tex" if isinstance(n, int) else f"table_{n}.tex")).write_text(
        t
    )


def save(fig, n):
    fig.savefig(
        O / f"figure_{n:02}.pdf",
        bbox_inches="tight",
        pad_inches=0.06,
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


u = pd.read_csv(R / "results/unified_compiler_artifacts.csv")
bp = u[(u.source == "benchpress_public") & (u.status == "passed")]
met = u[u.source == "qiskit_metriq"]
# Count and metric meanings are kept explicit, with no shared depth/gate column across sources.
tab(
    3,
    "Source outcomes and metric-specific successful-result means. BP denotes Benchpress; QM denotes qiskit-metriq. Runtime is unavailable for QM.",
    ["Source", "Success", "Failed", "Skipped"],
    [["BP", integer(len(bp)), 70, 264], ["QM", integer(len(met)), 0, 0]],
)
f = O / "table_03.tex"
s = f.read_text()
s = s.replace(
    r"\bottomrule\end{tabular}\end{minipage}",
    r"\bottomrule\end{tabular}\par\medskip"
    + "\n"
    + r"\begin{tabular}{llr}\toprule Source & Measurement & Mean \\\midrule"
    + "\n"
    + f"BP & Runtime (seconds) & {fmt(bp.runtime_mean_s.mean(), 3)}"
    + r" \\"
    + "\n"
    + f"BP & Two-qubit depth & {fmt(bp.output_depth_2q.mean(), 2)}"
    + r" \\"
    + "\n"
    + f"BP & Two-qubit gate count & {fmt(bp.output_gate_count_2q.mean(), 2)}"
    + r" \\"
    + "\n"
    + f"QM & Total depth & {fmt(met.output_depth.mean(), 2)}"
    + r" \\"
    + "\n"
    + f"QM & Total gate count & {fmt(met.output_gate_count.mean(), 2)}"
    + r" \\\bottomrule\end{tabular}\end{minipage}",
)
f.write_text(s)
groups = {
    "Compiler/version": ["sdk", "sdk_version", "optimization_level"],
    "Workload identity": [
        "benchmark_suite",
        "benchmark_group",
        "benchmark_name",
        "benchmark_family",
        "circuit_name",
    ],
    "Target/run design": ["topology", "backend_or_device", "seed", "rounds", "status"],
    "Circuit size": ["input_num_qubits", "output_num_qubits"],
    "Circuit metrics": [
        "output_depth",
        "output_depth_2q",
        "output_gate_count",
        "output_gate_count_2q",
    ],
    "Runtime metrics": [
        "runtime_mean_s",
        "runtime_median_s",
        "runtime_min_s",
        "runtime_max_s",
        "runtime_stddev_s",
    ],
}
rows = []
for source, df in [("BP", bp), ("QM", met)]:
    for name, cols in groups.items():
        present = df[cols].notna().sum()
        rows.append(
            [
                source,
                name,
                f"{sum(present > 0)}/{len(cols)}",
                fmt(100 * present.mean() / len(df)),
            ]
        )
tab(
    4,
    "Field availability among successful observations. A field is present when at least one row records it; the final column averages row-level availability across the named fields.",
    ["Source", "Field group", "Present fields", "Mean (\\%)"],
    rows,
    "llrr",
)
e = read("qasmbench_enrichment_summary")
ed = dict(zip(e.metric, e.value))
rows = []
# Audit values are computed from inventory/key sets, not manually copied.
inv = read("qasmbench_circuit_inventory")
en = read("benchpress_qasmbench_enrichment")
rows = [
    ["QASM/QASM3 input files", int(ed["qasmbench_inventory_rows"])],
    ["Unique raw match keys", int(ed["unique_raw_match_keys"])],
    ["Ambiguous raw match keys", int(ed["ambiguous_raw_match_keys"])],
    ["Successful Benchpress rows", integer(len(bp))],
    ["Exact unique matches", integer(int(ed["benchpress_matched_exact_unique_rows"]))],
    [
        "Exact unique matches (\\%)",
        fmt(100 * int(ed["benchpress_matched_exact_unique_rows"]) / len(bp)),
    ],
    ["Ambiguous matches", integer(int(ed["benchpress_ambiguous_key_rows"]))],
    [
        "Ambiguous matches (\\%)",
        fmt(100 * int(ed["benchpress_ambiguous_key_rows"]) / len(bp)),
    ],
    ["Unmatched rows", integer(int(ed["benchpress_unmatched_rows"]))],
    ["Unmatched rows (\\%)", fmt(100 * int(ed["benchpress_unmatched_rows"]) / len(bp))],
]
tab(
    5,
    "Conservative QASMBench identity-enrichment audit. The three outcome categories partition successful Benchpress observations.",
    ["Quantity", "Value"],
    rows,
)
b = read("benchpress_sdk_version_distribution")
b = b.iloc[
    sorted(range(len(b)), key=lambda i: (b.iloc[i].sdk, Version(b.iloc[i].sdk_version)))
].reset_index(drop=True)
# Split wide tables into coordinated panels at body font size.
rows = [
    [
        esc(r.sdk + " " + r.sdk_version),
        integer(r.n),
        fmt(r.runtime_mean_s_median, 3),
        fmt(r.runtime_mean_s_p95, 3),
        fmt(r.runtime_mean_s_max, 2),
    ]
    for _, r in b.iterrows()
]
tab(
    6,
    "Benchpress SDK-version distributions. Panel (a) reports runtime in seconds; panel (b) reports two-qubit structure. Support is identical across panels.",
    ["SDK/version", "$N$", "Median", "p95", "Maximum"],
    rows,
)
f = O / "table_06.tex"
s = f.read_text()
rr = "\n".join(
    esc(r.sdk + " " + r.sdk_version)
    + " & "
    + fmt(r.output_depth_2q_median)
    + " & "
    + fmt(r.output_gate_count_2q_median)
    + r" \\"
    for _, r in b.iterrows()
)
s = s.replace(
    r"\end{tabular}\end{minipage}",
    r"\end{tabular}\par\medskip"
    + "\n"
    + r"\begin{tabular}{lrr}\toprule SDK/version & 2q depth median & 2q gates median \\\midrule"
    + "\n"
    + rr
    + "\n"
    + r"\bottomrule\end{tabular}\end{minipage}",
)
f.write_text(s)
top = bp.nlargest(40, "runtime_mean_s")
gr = (
    top.groupby(["sdk", "sdk_version", "benchmark_family", "topology"])
    .agg(
        n=("runtime_mean_s", "size"),
        runtime=("runtime_mean_s", "max"),
        depth=("output_depth_2q", "max"),
        gates=("output_gate_count_2q", "max"),
    )
    .reset_index()
    .sort_values("runtime", ascending=False)
    .head(12)
)
assert (gr.sdk == "tket").all() and (gr.sdk_version == "2.6.0").all()
tab(
    7,
    "Twelve groups with largest maxima among forty ranked runtimes; all displayed rows use TKET 2.6.0. Depth and gates are two-qubit measurements.",
    ["Family", "Topology", "$N$", "Max s", "Max depth", "Max gates"],
    [
        [
            family(r.benchmark_family),
            r.topology,
            int(r.n),
            fmt(r.runtime),
            integer(r.depth),
            integer(r.gates),
        ]
        for _, r in gr.iterrows()
    ],
    "llrrrr",
)
fam = (
    read("benchpress_family_distribution")
    .sort_values(["n", "benchmark_family"], ascending=[False, True])
    .head(14)
)
tab(
    8,
    "Fourteen highest-coverage Benchpress families. Runtime is in seconds; structure columns report two-qubit medians.",
    ["Family", "$N$", "Time med.", "Time p95", "Depth", "Gates"],
    [
        [
            family(r.benchmark_family),
            integer(r.n),
            fmt(r.runtime_mean_s_median, 3),
            fmt(r.runtime_mean_s_p95, 3),
            fmt(r.output_depth_2q_median, 1),
            fmt(r.output_gate_count_2q_median, 1),
        ]
        for _, r in fam.iterrows()
    ],
)
topo = (
    read("benchpress_topology_distribution")
    .set_index("topology")
    .loc[TOPOS]
    .reset_index()
)
tab(
    9,
    "Unpaired Benchpress summaries by recorded topology. Runtime is in seconds; depth and gates are two-qubit medians.",
    ["Topology", "$N$", "Time med.", "Time p95", "Depth", "Gates"],
    [
        [
            r.topology,
            integer(r.n),
            fmt(r.runtime_mean_s_median, 3),
            fmt(r.runtime_mean_s_p95, 3),
            fmt(r.output_depth_2q_median, 1),
            fmt(r.output_gate_count_2q_median, 1),
        ]
        for _, r in topo.iterrows()
    ],
)
p = (
    read("benchpress_topology_penalty_by_family")
    .sort_values("depth_2q_ratio_median", ascending=False)
    .head(14)
)
tab(
    10,
    "Fourteen largest family-level median depth ratios relative to all-to-all. N counts matched cells; ratios exclude zero denominators separately for each metric.",
    ["Family", "Topology", "$N$", "Time", "Depth", "Gates"],
    [
        [
            family(r.benchmark_family),
            r.topology,
            integer(r.n),
            fmt(r.runtime_ratio_median),
            fmt(r.depth_2q_ratio_median),
            fmt(r.gate_2q_ratio_median),
        ]
        for _, r in p.iterrows()
    ],
    "llrrrr",
)
adj = read("benchpress_qiskit_largest_runtime_improvements").head(12)
tab(
    11,
    "Twelve largest adjacent Qiskit runtime reductions (percent). Structural reductions use the same rows and their own positive baselines.",
    ["Family/target", "Qubits", "Versions", "Time", "Depth", "Gates"],
    [
        [
            family(r.benchmark_family) + "/" + r.topology,
            integer(r.input_num_qubits),
            r.from_version + r"$\to$" + r.to_version,
            fmt(-r.runtime_delta_pct),
            fmt(-r.depth_2q_delta_pct),
            fmt(-r.gate_2q_delta_pct),
        ]
        for _, r in adj.iterrows()
    ],
    "lrlrrr",
)
versions = sorted(met.sdk_version.unique(), key=Version)
vm = met.groupby("sdk_version")[["output_depth", "output_gate_count"]].mean()
base = vm.loc["0.18.0"]
milestones = ["0.18.0", "0.19.4", "0.34.2", "0.42.1", "0.45.2"]
rows = []
for v in milestones:
    r = vm.loc[v]
    rows.append(
        [
            v,
            fmt(r.output_depth, 3),
            fmt(r.output_gate_count, 3),
            fmt(100 * (base.output_depth - r.output_depth) / base.output_depth),
            fmt(
                100
                * (base.output_gate_count - r.output_gate_count)
                / base.output_gate_count
            ),
        ]
    )
tab(
    12,
    "Historical milestones pooled across both backends, with 200 observations at every version. Percent reductions compare pooled means with the initial version.",
    ["Version", "Depth mean", "Gate mean", "Depth (\\%)", "Gates (\\%)"],
    rows,
)
ma = read("metriq_circuit_version_changes").sort_values("depth_delta_pct").head(10)
tab(
    13,
    "Ten largest adjacent reductions in backend-specific means (percent). Each endpoint contains 100 recorded seeds.",
    ["Backend", "From", "To", "Depth", "Gates"],
    [
        [
            "Rigetti" if r.backend_or_device.startswith("rigetti") else "IBM",
            r.from_version,
            r.to_version,
            fmt(-r.depth_delta_pct),
            fmt(-r.gate_count_delta_pct),
        ]
        for _, r in ma.iterrows()
    ],
    "lllrr",
)
q = read("qiskit_first_last_paired_summary")
ms = read("metriq_seed_paired_summary")
rows = []
for frame, prefix in [(q, "BP"), (ms, "QM")]:
    for _, r in frame.iterrows():
        name = (
            r.metric.replace(" reduction (%)", "")
            .replace("two-qubit", "2q")
            .replace("total gate-count", "gates")
            .replace("total depth", "depth")
        )
        rows.append(
            [
                prefix + " " + name,
                integer(r.n),
                fmt(r["mean"]),
                fmt(r["median"]),
                fmt(r.bootstrap_median_ci_low) + "--" + fmt(r.bootstrap_median_ci_high),
            ]
        )
tab(
    "paired",
    "Endpoint paired reductions (percent) with workload-clustered (BP) or seed-clustered (QM) 95\\% intervals for the median. Positive values denote improvements.",
    ["Metric", "$N$", "Mean", "Median", "95\\% interval"],
    rows,
)
c = read("cross_sdk_descriptive_summary")
cc = c[~c.sdk_version.str.startswith("qiskit")]
rows = []
for _, r in cc.iterrows():
    for metric in ["runtime", "depth"]:
        rows.append(
            [
                r.sdk_version.split()[0].upper(),
                metric,
                int(r[metric + "_valid_n"]),
                fmt(r[metric + "_ratio_median_vs_qiskit"]),
                fmt(r[metric + "_ratio_q25"]) + "--" + fmt(r[metric + "_ratio_q75"]),
            ]
        )
tab(
    "cross",
    "Descriptive matched ratios relative to Qiskit 2.5.0rc1; comparison versions are QPanda 0.3.2 and TKET 2.6.0. Depth denotes two-qubit depth.",
    ["SDK", "Metric", "$N$", "Median", "Interquartile range"],
    rows,
    "llrrr",
)
# Each original figure's analytical role is retained, with regenerated vector graphics.
v = read("metriq_version_backend_optlevel_distribution")
for number, relative in [(1, False), (2, True)]:
    fig, axes = plt.subplots(
        2, 1, figsize=(5.1, 4.9), sharex=True, layout="constrained"
    )
    for backend, color, label in [
        ("ibm_rochester", BLUE, "IBM Rochester"),
        ("rigetti_16q_aspen", ORANGE, "Rigetti Aspen"),
    ]:
        vv = v[v.backend_or_device == backend].set_index("sdk_version").loc[versions]
        for ax, col, label_y in zip(
            axes,
            ["output_depth_mean", "output_gate_count_mean"],
            ["Total depth", "Total gate count"],
        ):
            vals = vv[col].to_numpy()
            vals = 100 * (vals[0] - vals) / vals[0] if relative else vals
            ax.plot(
                range(len(versions)), vals, "-o", color=color, label=label, markersize=3
            )
            ax.set_ylabel(label_y + (" reduction (%)" if relative else ""))
            ax.grid(alpha=0.15)
    axes[0].legend()
    axes[1].set_xticks(range(len(versions)), versions, rotation=65, ha="right")
    axes[1].set_xlabel("Qiskit version")
    save(fig, number)
fig, ax = plt.subplots(figsize=(5.1, 4.2), layout="constrained")
yy = np.arange(len(b))
for col, label, marker, color in [
    ("runtime_mean_s_median", "Median", "o", BLUE),
    ("runtime_mean_s_mean", "Mean", "s", ORANGE),
    ("runtime_mean_s_p95", "p95", "^", GREEN),
]:
    ax.scatter(b[col], yy, label=label, marker=marker, color=color, s=24)
ax.set_yticks(yy, b.sdk + " " + b.sdk_version)
ax.invert_yaxis()
ax.set_xscale("log")
ax.set_xlabel("Runtime (seconds)")
ax.legend()
ax.grid(axis="x", alpha=0.15)
save(fig, 3)
fig, ax = plt.subplots(figsize=(5.1, 4.2), layout="constrained")
vals = [
    bp[(bp.sdk == r.sdk) & (bp.sdk_version == r.sdk_version)].runtime_mean_s.to_numpy()
    for _, r in b.iterrows()
]
ax.boxplot(
    vals,
    vert=False,
    showfliers=False,
    tick_labels=(b.sdk + " " + b.sdk_version).tolist(),
    medianprops={"color": BLUE},
)
ax.invert_yaxis()
ax.set_xscale("log")
ax.set_xlabel("Runtime (seconds)")
ax.grid(axis="x", alpha=0.15)
save(fig, 4)
fig, ax = plt.subplots(figsize=(5.1, 6.9), layout="constrained")
display = top.head(20).iloc[::-1]
labels = [
    family(r.benchmark_family)
    + " / "
    + r.topology
    + " / "
    + str(int(r.input_num_qubits))
    + "q"
    for _, r in display.iterrows()
]
assert (display.sdk == "tket").all()
ax.barh(range(20), display.runtime_mean_s, color=BLUE)
ax.set_yticks(range(20), labels)
ax.set_xscale("log")
ax.set_xlabel("TKET 2.6.0 mean runtime (seconds)")
ax.grid(axis="x", alpha=0.15)
save(fig, 5)
fams = [
    "abstract_qasmbench_100q",
    "abstract_qasmbench_32q",
    "chemistry",
    "condensedmatter",
    "binaryoptimization",
    "discreteoptimization",
    "multiplier",
    "square",
    "qft",
    "qec9xz",
    "bwt",
    "adder",
]
ft = read("benchpress_family_topology_distribution")
pv = ft.pivot(
    index="benchmark_family", columns="topology", values="output_gate_count_2q_median"
).reindex(index=fams, columns=TOPOS)
arr = pv.to_numpy()
fig, ax = plt.subplots(figsize=(5.1, 4.8), layout="constrained")
cmap = plt.get_cmap("Blues").copy()
cmap.set_bad("#dddddd")
im = ax.imshow(
    np.ma.masked_invalid(arr),
    aspect="auto",
    norm=LogNorm(vmin=1, vmax=np.nanmax(arr)),
    cmap=cmap,
)
ax.set_yticks(range(len(fams)), [family(x) for x in fams])
ax.set_xticks(range(len(TOPOS)), TOPOS, rotation=40, ha="right")
fig.colorbar(im, ax=ax, label="Median two-qubit gates (log scale)")
save(fig, 6)
pfull = read("benchpress_topology_penalty_by_family")
selected = [
    "abstract_qasmbench_100q",
    "abstract_qasmbench_32q",
    "binaryoptimization",
    "qft",
    "discreteoptimization",
    "qec9xz",
    "bwt",
    "adder",
]
fig, ax = plt.subplots(figsize=(5.1, 4.4), layout="constrained")
for j, (topology, color) in enumerate(
    [("heavy-hex", BLUE), ("linear", ORANGE), ("square", GREEN)]
):
    vals = [
        pfull[
            (pfull.benchmark_family == f) & (pfull.topology == topology)
        ].depth_2q_ratio_median.iloc[0]
        for f in selected
    ]
    ax.scatter(
        vals,
        np.arange(len(selected)) + (j - 1) * 0.16,
        label=topology,
        color=color,
        s=24,
    )
ax.set_yticks(range(len(selected)), [family(x) for x in selected])
ax.invert_yaxis()
ax.set_xscale("log")
ax.axvline(1, color="#666666", linestyle="--")
ax.set_xlabel("Median matched two-qubit depth ratio")
ax.legend()
ax.grid(axis="x", alpha=0.15)
save(fig, 7)
md = read("metriq_seed_level_first_last_deltas")
fig, axes = plt.subplots(2, 1, figsize=(5.1, 4.8), sharex=True, layout="constrained")
for ax, backend, color, label in zip(
    axes,
    ["ibm_rochester", "rigetti_16q_aspen"],
    [BLUE, ORANGE],
    ["IBM Rochester", "Rigetti Aspen"],
):
    vals = -md[md.backend_or_device == backend].depth_delta_pct
    ax.hist(vals, bins=np.arange(30, 101, 5), color=color, edgecolor="white")
    ax.set_ylabel("Seed count")
    ax.set_title(label)
    ax.grid(axis="y", alpha=0.15)
axes[-1].set_xlabel("Paired total-depth reduction (%)")
save(fig, 8)
meta = {
    "baseline_analytical_figures_preserved": 8,
    "numerical_tables": len(list(O.glob("table_*.tex"))),
    "top40_groups": int(
        top.groupby(["sdk", "sdk_version", "benchmark_family", "topology"]).ngroups
    ),
    "top12_groups_cover_rows": int(gr.n.sum()),
    "top20_all_tket": True,
    "figures_are_vector": True,
}
(R / "verification/full_presentation_metadata.json").write_text(
    json.dumps(meta, indent=2) + "\n"
)
print(meta)
