#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
"$ROOT/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
"$ROOT/.venv/bin/python" -m pip install -e .

mkdir -p "$HOME/.local/bin"
ln -sfn "$ROOT/.venv/bin/job" "$HOME/.local/bin/job"
ln -sfn "$ROOT/.venv/bin/company" "$HOME/.local/bin/company"
mkdir -p "$ROOT/data/Applications"

echo "Installed: $HOME/.local/bin/job and company"
echo "Run: job"
