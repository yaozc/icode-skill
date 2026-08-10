#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${ICODEX_ADAPTER_PYTHON_BIN:-python3}"
exec "$PYTHON_BIN" "$HERE/codex_adapter.py" install "$@"
