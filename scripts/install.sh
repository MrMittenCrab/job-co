#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
"$ROOT/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
"$ROOT/.venv/bin/python" -m pip install -e .

mkdir -p "$HOME/bin"
ln -sfn "$ROOT/.venv/bin/job" "$HOME/bin/job"
ln -sfn "$ROOT/.venv/bin/company" "$HOME/bin/company"
mkdir -p "$HOME/Documents/Career/Applications"

echo "Installed: $HOME/bin/job"
echo "Run: job"
