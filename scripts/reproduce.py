"""Run the complete secondary analysis from pinned public benchmark outputs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use locally cached inputs; all source hashes are still verified.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Check existing inputs, analysis results, and generated figures/tables.",
    )
    args = parser.parse_args()
    stages = []
    if not args.verify_only:
        if not args.offline:
            stages.append(("Acquire and verify pinned inputs", "fetch_sources.py"))
        stages.extend(
            [
                ("Normalize and analyze historical outputs", "run_analysis.py"),
                (
                    "Generate numerical tables and analytical figures",
                    "render_full_manuscript.py",
                ),
                (
                    "Generate empirical workflow accounting",
                    "render_workflow_evidence.py",
                ),
            ]
        )
    stages.extend(
        [
            ("Validate scientific and source invariants", "validate.py"),
            (
                "Validate reported claims and presentation assets",
                "validate_full_release.py",
            ),
        ]
    )
    for index, (label, filename) in enumerate(stages, start=1):
        print(f"[{index}/{len(stages)}] {label}", flush=True)
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / filename)], cwd=ROOT, check=True
        )
    print("Reproduction and verification completed.")


if __name__ == "__main__":
    main()
