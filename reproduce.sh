#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python scripts/reproduce.py "$@"
