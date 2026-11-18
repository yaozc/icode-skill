#!/usr/bin/env bash
# 在子 shell 内借用 resolver 的变量，避免污染或读取调用方的 MCP runtime override。
ICODEX_TEST_PYTHON_BIN="$(
  source "$(dirname "${BASH_SOURCE[0]}")/../mcp/codex-python.sh" || exit 1
  ICODEX_ADAPTER_PYTHON_BIN="${ICODEX_TEST_PYTHON_BIN:-}"
  icodex_resolve_python || exit 1
  # 子 shell 只接收单个可执行路径，不需要重建 py -3 等启动器参数。
  "${ICODEX_ADAPTER_PYTHON[@]}" -c 'import sys; print(sys.executable)'
)" || {
  echo "Maintenance checks require a working Python 3.9+; set ICODEX_TEST_PYTHON_BIN to one executable path." >&2
  return 1
}
export ICODEX_TEST_PYTHON_BIN
