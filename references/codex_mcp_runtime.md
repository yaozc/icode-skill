# Codex MCP 启动运行时

本合同只适用于 `mcp/install-codex.sh`、`mcp/uninstall-codex.sh` 和 `mcp/codex_adapter.py`。注册仍只调用 `codex mcp list|get|add|remove`，不执行 legacy 安装器，不修改 Claude 配置；同名不同配置继续拒绝，安装器不自动移除或覆盖它。

## 入口 Python

安装与卸载共用 `mcp/codex-python.sh`，通过真实 Python 输出探针拒绝 WindowsApps 这类“退出码0但无有效输出”的占位程序。Windows Git Bash/MSYS 优先尝试 argv `py -3`，其余候选依次为 `python3`、`py -3`、`python`；非 Windows 先尝试 `python3`。探针要求 Python 3.9+，不安装或升级解释器。

`ICODEX_ADAPTER_PYTHON_BIN` 指定一个可执行文件路径，可含空格，显式值优先且失败不回退。它不是 shell 命令，`py -3` 不能作为该变量的值；不要使用 eval 或字符串拆分。`ICODEX_PYTHON_BIN` 保留原有用途：仅为本地 Python MCP 新建 venv 选择解释器，不等同于 adapter 入口。

每个候选的输出探针在约 3 秒后超时：普通候选继续回退，显式覆盖报超时且不换解释器。探针只使用 Bash 3.2 内建计时/进程控制和 macOS/Linux/Git Bash 的 `mktemp`、`sleep`、`cmp`、`rm`，不依赖已选好的 Python 或 GNU timeout。stdout 写入临时普通文件，检查直接子进程退出状态及固定标记，不因后代仍占用输出管道而等待 EOF；超时先 TERM，再 KILL，并 wait 回收直接子进程。该边界不承诺终止后代树或 Windows 原生进程树，也不覆盖 OS 无法及时调度/终止进程的情况；超时仅作用于解释器探针，不给后续 adapter/MCP 操作设时限。

## Windows npm 服务

`ICODEX_NODE_BIN` 优先选择 Node；未指定时从选定 npx 所在目录优先找相邻 `node.exe`，再使用 PATH 中的 Node。实际注册使用原生 `node.exe` 和同一运行时中的 `npx-cli.js` 作为独立参数，避免客户端直接 spawn `.cmd`；Node 本身不能是 shell 垫片。npm CLI 按标准 Node/npm 安装布局查找，不下载缺失组件；缺 Node 或 npx-cli.js 时在注册前明确失败。

`ICODEX_NPX_BIN` 继续选择 npx。显式 `.cmd`/`.bat` 路径必须能与所选 Node 的同一份 npm CLI 配对，冲突时拒绝，不能悄悄换成系统中的另一套 npm。用户显式提供原生 `.exe`/`.com` 包装器时直接使用该可执行文件，包装器自己的运行环境由调用方负责，不能同时指定会被忽略的 `ICODEX_NODE_BIN`。直接选择 Node 运行时且其标准 npm CLI 存在时，不要求额外存在 npx.cmd。

Node 方案仅为 MCP 子服务设置 PATH：选中的 Node 目录加 Windows 系统目录，不继承安装期 Git Bash/MSYS 的 POSIX PATH。构造服务 env 时若已有显式 PATH/Path（不区分大小写），保留其值，不修改全局环境。环境变量通过 `codex mcp add --env` 逐个传递，无 shell 拼接；没有 `_fallback` 等 Codex CLI 不支持的字段。

macOS/Linux 保留原先 `npx -y <package>` transport 和 `ICODEX_NPX_BIN` 语义。Node 仅在安装选中的 npm 服务时解析；仅本地 Python 服务或卸载不因无关 Node/npm 缺失而失败。卸载仍需要 adapter 入口 Python，但不依赖服务本身的 Node 或 venv 存在。

## 验证边界

`tests/test_codex_mcp_runtime.py` 使用本机真实 Bash 进程、隔离的假 CLI/解释器和 Windows transport 模拟，覆盖无输出占位程序、py 参数、空格路径、显式覆盖、探针超时/直接子进程回收、后代占用 stdout、runtime 配对、PATH、dry-run、幂等与冲突零改写。POSIX 测试的进程组仅用于夹具收尾，不作为生产代码能终止后代树的证据。`tests/test_mcp_codex_install.sh` 继续核对既有注册/卸载行为。测试不会安装依赖、启动 npm 包或改真实 MCP 配置；macOS 上的分派模拟不证明 Windows 原生 MCP 已成功启动。
