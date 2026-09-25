#!/usr/bin/env bash
# One-click test: chay toan bo pytest suite voi LLM mock va coverage gate 80%.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python )}"
LLM_PROVIDER=mock LLM_MODEL=mock "$PYTHON" -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80 "$@"
