#!/usr/bin/env bash
# Static Codex path/schema agreement; behavioral assertions are Python regressions.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import importlib.util
import json
from pathlib import Path
root = Path.cwd()
json.loads((root / 'schemas/inspection-worklist.schema.json').read_text())
spec = importlib.util.spec_from_file_location('inspection_worklist', root / 'tools/inspection_worklist.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.PHASES['crosscheck'] == ['fresh']
assert module._is_control_path('.ai/icode/icode_1/01_plan.md')
assert module._is_control_path('.ai/icode/.crosscheck/icode_1/fresh.json')
assert module._is_control_path('.icode_output/.icode_output_1/01_plan.md')
assert not module._is_control_path('src/feature.py')
print('PASS inspection worklist Codex path/schema contract')
PY
