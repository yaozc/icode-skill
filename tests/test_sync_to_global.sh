#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TARGET="$TMP_DIR/icodex"
mkdir -p "$TARGET/.git" "$TARGET/steps"
touch "$TARGET/.git/sentinel"
touch "$TARGET/steps/run.md"

GLOBAL_DIR="$TARGET" bash "$ROOT/scripts/sync-to-global.sh" --apply >/dev/null

test -d "$TARGET/.git"
test -f "$TARGET/.git/sentinel"
test ! -e "$TARGET/steps/run.md"
test -f "$TARGET/SKILL.md"

echo "PASS: sync preserves destination git metadata and removes stale skill files"

# 源端工单/缓存只在临时 fixture 创建，避免污染真实仓库和全局安装。
SOURCE="$TMP_DIR/source"
mkdir -p "$SOURCE/scripts" "$SOURCE/mcp/vision-bridge" "$SOURCE/.ai/icode/icode_1" \
  "$SOURCE/.pytest_cache" "$SOURCE/docs/private" "$SOURCE/tests" "$SOURCE/demo"
cp "$ROOT/scripts/sync-to-global.sh" "$SOURCE/scripts/"
cp "$ROOT/.gitignore" "$SOURCE/"
printf 'new skill\n' > "$SOURCE/SKILL.md"
printf 'gitdir: /fixture/source-git\n' > "$SOURCE/.git"
printf 'private ticket\n' > "$SOURCE/.ai/icode/icode_1/RCA.md"
printf 'test cache\n' > "$SOURCE/.pytest_cache/cache"
printf 'private report\n' > "$SOURCE/docs/private/report.md"
printf 'source local config\n' > "$SOURCE/mcp/vision-bridge/config.json"
printf 'new server\n' > "$SOURCE/mcp/vision-bridge/server.py"
mkdir -p "$SOURCE/mcp/vision-bridge/__pycache__"
touch "$SOURCE/mcp/vision-bridge/__pycache__/source.pyc" "$SOURCE/tests/test.py" "$SOURCE/demo/demo.py"

DEST="$TMP_DIR/destination"
mkdir -p "$DEST/mcp/vision-bridge/.venv/bin" "$DEST/mcp/vision-bridge/.cache"
mkdir -p "$DEST/.ai/icode" "$DEST/docs/local"
printf 'destination ticket\n' > "$DEST/.ai/icode/local.md"
printf 'destination notes\n' > "$DEST/docs/local/notes.md"
printf 'gitdir: /fixture/destination-git\n' > "$DEST/.git"
printf 'destination config\n' > "$DEST/mcp/vision-bridge/config.json"
printf 'destination python\n' > "$DEST/mcp/vision-bridge/.venv/bin/python"
printf 'destination cache\n' > "$DEST/mcp/vision-bridge/.cache/entry"
printf 'old skill\n' > "$DEST/SKILL.md"
printf 'obsolete\n' > "$DEST/stale.md"

GLOBAL_DIR="$DEST" bash "$SOURCE/scripts/sync-to-global.sh" >/dev/null
test "$(cat "$DEST/SKILL.md")" = 'old skill'
test -f "$DEST/stale.md"
test ! -e "$DEST/mcp/vision-bridge/server.py"

GLOBAL_DIR="$DEST" bash "$SOURCE/scripts/sync-to-global.sh" --apply --no-delete >/dev/null
test -f "$DEST/stale.md"
test "$(cat "$DEST/SKILL.md")" = 'new skill'

GLOBAL_DIR="$DEST" bash "$SOURCE/scripts/sync-to-global.sh" --apply >/dev/null
test ! -e "$DEST/stale.md"
test "$(cat "$DEST/.git")" = 'gitdir: /fixture/destination-git'
test "$(cat "$DEST/mcp/vision-bridge/config.json")" = 'destination config'
test "$(cat "$DEST/mcp/vision-bridge/.venv/bin/python")" = 'destination python'
test "$(cat "$DEST/mcp/vision-bridge/.cache/entry")" = 'destination cache'
test "$(cat "$DEST/.ai/icode/local.md")" = 'destination ticket'
test "$(cat "$DEST/docs/local/notes.md")" = 'destination notes'
test -f "$DEST/mcp/vision-bridge/server.py"
for ignored in .ai/icode/icode_1 .pytest_cache docs/private mcp/vision-bridge/__pycache__ tests demo; do
  test ! -e "$DEST/$ignored"
done
echo "PASS: dry-run, no-delete, source privacy and destination MCP runtime protection"
