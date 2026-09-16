#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PASS=0
FAIL=0
ok() { printf '  PASS %s\n' "$1"; PASS=$((PASS + 1)); }
bad() { printf '  FAIL %s\n' "$1" >&2; FAIL=$((FAIL + 1)); }
contains() {
  local file="$1" text="$2" label="$3"
  if rg -qF -- "$text" "$file"; then ok "$label"; else bad "$label (missing: $text)"; fi
}

echo "=== 1. standalone schemas and controller ==="
contains schemas/crosscheck-manifest.schema.json '"additionalProperties": false' 'manifest schema is closed'
contains schemas/crosscheck-round.schema.json '"additionalProperties": false' 'round schema is closed'
contains tools/icode_crosscheck.py 'sub.add_parser("start"' 'tool supports start'
contains tools/icode_crosscheck.py 'sub.add_parser("freeze"' 'tool supports freeze'
contains tools/icode_crosscheck.py 'sub.add_parser("finish"' 'tool supports finish'
contains tools/icode_crosscheck.py 'sub.add_parser("validate"' 'tool supports validate'

echo "=== 2. Codex path and read-only target contracts ==="
python3 - "$ROOT" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
source = (root / "tools/icode_crosscheck.py").read_text(encoding="utf-8")
state = (root / "tools/icode_state.py").read_text(encoding="utf-8")

assert "resolve_with_state" in source
assert ".resolve_ticket(" in source
assert ".validate_completed_run(" in source
assert '".codex"' in source and '"icode_data"' in source
assert '".ai"' in source and '".crosscheck"' in source
assert "icode_control" not in source
assert ".claude" not in source
assert ".active_ticket.json" not in source
for forbidden in ('"transition"', '"index-write"', '"metadata-update"', '"event"'):
    assert forbidden not in source, f"crosscheck must not invoke target writer {forbidden}"
assert "def resolve_ticket(" in state
assert "def validate_completed_run(" in state
assert '"legacy_overlay"' in state
print("  PASS native Codex resolver, validator, paths and zero-writer boundary")
PY
PASS=$((PASS + 1))

echo "=== 3. syntax and JSON contracts ==="
python3 - <<'PY'
from pathlib import Path
for raw in ("tools/icode_crosscheck.py", "tests/test_crosscheck.py"):
    path = Path(raw)
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
PY
ok "Python sources compile without writing bytecode"
python3 -m json.tool schemas/crosscheck-manifest.schema.json >/dev/null
python3 -m json.tool schemas/crosscheck-round.schema.json >/dev/null
ok "crosscheck schemas are valid JSON"

printf '\nRESULT: %d passed, %d failed\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
