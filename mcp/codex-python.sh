#!/usr/bin/env bash
# 由安装/卸载入口 source；数组保留 py -3 和含空格的显式可执行路径。
icodex_python_ok() {
  local probe_output probe_pid probe_start probe_status=1
  probe_output="$(mktemp "${TMPDIR:-/tmp}/icodex-python.XXXXXX")" || return 1
  # 普通文件不依赖后代关闭 stdout；不能用命令替换等待管道 EOF。
  "$@" -c 'import sys; sys.stdout.write("ICODEX_PYTHON_OK" if sys.version_info >= (3, 9) else "")' \
    </dev/null >"$probe_output" 2>/dev/null &
  probe_pid=$!
  probe_start=$SECONDS
  while kill -0 "$probe_pid" 2>/dev/null; do
    if [ "$((SECONDS - probe_start))" -ge 3 ]; then
      kill -TERM "$probe_pid" 2>/dev/null || :
      sleep 0.1
      kill -KILL "$probe_pid" 2>/dev/null || :
      wait "$probe_pid" 2>/dev/null || :
      rm -f "$probe_output"
      return 124
    fi
    sleep 0.1
  done
  # 与固定短输入比较，避免把失控输出整体读入 shell 内存。
  if wait "$probe_pid" 2>/dev/null && printf 'ICODEX_PYTHON_OK' | cmp -s - "$probe_output"; then
    probe_status=0
  fi
  rm -f "$probe_output"
  return "$probe_status"
}

icodex_resolve_python() {
  ICODEX_ADAPTER_PYTHON=()
  if [ -n "${ICODEX_ADAPTER_PYTHON_BIN:-}" ]; then
    if icodex_python_ok "$ICODEX_ADAPTER_PYTHON_BIN"; then
      ICODEX_ADAPTER_PYTHON=("$ICODEX_ADAPTER_PYTHON_BIN")
      return 0
    else
      local probe_status=$?
      if [ "$probe_status" -eq 124 ]; then
        echo "ICODEX_ADAPTER_PYTHON_BIN probe timed out after 3 seconds; explicit runtime was not replaced." >&2
      else
        echo "ICODEX_ADAPTER_PYTHON_BIN must name one working Python 3.9+ executable (not a command string)." >&2
      fi
      return 1
    fi
  fi

  local windows=false
  if [ -n "${MSYSTEM:-}" ]; then
    windows=true
  else
    case "$(uname -s 2>/dev/null)" in MINGW*|MSYS*) windows=true ;; esac
  fi
  if [ "$windows" = true ] && icodex_python_ok py -3; then
    ICODEX_ADAPTER_PYTHON=(py -3)
  elif icodex_python_ok python3; then
    ICODEX_ADAPTER_PYTHON=(python3)
  elif icodex_python_ok py -3; then
    ICODEX_ADAPTER_PYTHON=(py -3)
  elif icodex_python_ok python; then
    ICODEX_ADAPTER_PYTHON=(python)
  else
    echo "No working Python 3.9+ found; set ICODEX_ADAPTER_PYTHON_BIN to its executable path." >&2
    return 1
  fi
}
