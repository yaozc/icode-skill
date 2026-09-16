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
