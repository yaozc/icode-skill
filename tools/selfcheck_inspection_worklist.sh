#!/usr/bin/env bash
# Temporary repository fixtures only; never reads or mutates live ticket history.
set -euo pipefail
cd "$(dirname "$0")/.."
rounds="${1:-3}"
if [[ ! "$rounds" =~ ^[1-9][0-9]*$ ]]; then
  echo "rounds must be a positive integer" >&2
  exit 2
fi
for ((round=1; round<=rounds; round++)); do
  python3 - <<'PY'
from pathlib import Path
path = Path('tools/inspection_worklist.py')
compile(path.read_text(encoding='utf-8'), str(path), 'exec')
PY
  for script in tests/*.sh; do bash -n "$script"; done
  bash tests/test_inspection_worklist_contract.sh
  python3 -m pytest -p no:anyio tests/test_inspection_worklist.py -q
  printf '[round %02d] PASS syntax/dependencies/logic/errors/association/compatibility/runtime\n' "$round"
done
printf 'PASS: %s isolated inspection-worklist rounds\n' "$rounds"
