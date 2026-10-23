#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/codex-python.sh"
icodex_resolve_python
exec "${ICODEX_ADAPTER_PYTHON[@]}" "$HERE/codex_adapter.py" uninstall "$@"
