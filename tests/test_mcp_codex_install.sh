#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

FAKE_CODEX="$TMP_DIR/codex"
FAKE_NPX="$TMP_DIR/npx"
LOG_FILE="$TMP_DIR/calls.log"

cat > "$FAKE_CODEX" <<'FAKE'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$FAKE_CODEX_LOG"
if [ "${1:-}" != "mcp" ]; then exit 9; fi
case "${2:-}" in
  list)
    if [ "${FAKE_EXISTING:-absent}" = "absent" ]; then
      printf '[]\n'
    else
      printf '[{"name":"memory"}]\n'
    fi
    ;;
  get)
    if [ "${FAKE_EXISTING:-absent}" = "identical" ]; then
      printf '{"name":"memory","transport":{"type":"stdio","command":"%s","args":["-y","@modelcontextprotocol/server-memory"],"env":null,"cwd":null}}\n' "$ICODEX_NPX_BIN"
    elif [ "${FAKE_EXISTING:-absent}" = "equivalent" ]; then
      printf '{"name":"memory","transport":{"type":"stdio","command":"npx","args":["-y","@modelcontextprotocol/server-memory"],"env":null,"cwd":""}}\n'
    elif [ "${FAKE_EXISTING:-absent}" = "different" ]; then
      printf '{"name":"memory","transport":{"type":"stdio","command":"other-npx","args":[],"env":null,"cwd":null}}\n'
    else
      exit 1
    fi
    ;;
  add)
    if [ "${FAKE_FAIL_NAME:-}" ] && [ "${3:-}" = "$FAKE_FAIL_NAME" ]; then exit 7; fi
    ;;
  remove) ;;
  *) exit 8 ;;
esac
FAKE
chmod +x "$FAKE_CODEX"
touch "$FAKE_NPX"
chmod +x "$FAKE_NPX"

export ICODEX_CODEX_BIN="$FAKE_CODEX"
export ICODEX_NPX_BIN="$FAKE_NPX"
export ICODEX_PYTHON_BIN="/fake/python"
export FAKE_CODEX_LOG="$LOG_FILE"
export PATH="$TMP_DIR:$PATH"

clear_log() { : > "$LOG_FILE"; }
assert_no_mutation() {
  if grep -Eq 'mcp (add|remove)' "$LOG_FILE"; then
    echo "unexpected mutation" >&2
    exit 1
  fi
}

clear_log
FAKE_EXISTING=absent "$ROOT/mcp/install-codex.sh" --dry-run memory >/dev/null
assert_no_mutation

clear_log
FAKE_EXISTING=identical "$ROOT/mcp/install-codex.sh" memory >/dev/null
assert_no_mutation

clear_log
FAKE_EXISTING=equivalent "$ROOT/mcp/install-codex.sh" memory >/dev/null
assert_no_mutation

clear_log
set +e
conflict_output=$(FAKE_EXISTING=different "$ROOT/mcp/install-codex.sh" memory 2>&1)
conflict_status=$?
set -e
[ "$conflict_status" -eq 2 ]
printf '%s' "$conflict_output" | grep -q '"existing"'
printf '%s' "$conflict_output" | grep -q '"candidate"'
assert_no_mutation

clear_log
FAKE_EXISTING=absent "$ROOT/mcp/install-codex.sh" --no-auto-install memory >/dev/null
grep -q 'mcp add memory' "$LOG_FILE"

clear_log
set +e
FAKE_EXISTING=absent FAKE_FAIL_NAME=sequential-thinking \
  "$ROOT/mcp/install-codex.sh" --no-auto-install >/dev/null 2>&1
batch_status=$?
set -e
[ "$batch_status" -ne 0 ]
grep -q 'mcp add sequential-thinking' "$LOG_FILE"

clear_log
set +e
FAKE_EXISTING=identical "$ROOT/mcp/uninstall-codex.sh" memory </dev/null >/dev/null 2>&1
confirmation_status=$?
set -e
[ "$confirmation_status" -ne 0 ]
assert_no_mutation

clear_log
FAKE_EXISTING=identical "$ROOT/mcp/uninstall-codex.sh" --yes memory >/dev/null
grep -q 'mcp remove memory' "$LOG_FILE"

echo "PASS: Codex MCP adapters"
