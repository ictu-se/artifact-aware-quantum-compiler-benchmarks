#!/bin/sh
set -eu
cd "$(dirname "$0")"
python scripts/fetch_sources.py
python scripts/run_analysis.py
python scripts/render_manuscript_assets.py
python scripts/validate.py
