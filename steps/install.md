# 步骤 install — Codex MCP 安全安装（独立步骤）

> **Codex 持久化前置**：执行本步骤前必须完整读取 [references/codex_runtime.md](../references/codex_runtime.md)；路径、状态、锁、合并读取、迁移和 artifact_map 与旧文字冲突时以该文件和 `~/.codex/skills/icodex/tools/icode_state.py` 为准。

**命令**：`$icodex install [--dry-run] [--no-auto-install] [name]`

**产出**：不创建工单或 metadata；只允许通过 Codex CLI 注册 MCP，并在确有缺失时准备本 skill 内的本地 Python MCP 环境。

## 执行

1. 定位当前 skill 根目录，确认 `mcp/install-codex.sh` 与 `mcp/codex_adapter.py` 存在。
2. 先执行 dry-run 并向用户展示结果：

   ```bash
   bash mcp/install-codex.sh --dry-run [name]
   ```

3. 用户已请求安装即视为授权执行同一范围的实际命令：

   ```bash
   bash mcp/install-codex.sh [--no-auto-install] [name]
   ```

4. 用 `codex mcp list --json` 与 `codex mcp get <name> --json` 验证结果；不得直接编辑 `~/.codex/config.toml`。

安装器必须遵守以下边界：

- 已有配置与期望配置完全一致：跳过，不下载、不重装。
- 同名配置不同：整体预检返回退出码 2；不得 remove、覆盖、下载或先安装依赖。
- 缺失配置：只有全部冲突预检通过后才准备依赖并调用 `codex mcp add`。
- `--no-auto-install`：依赖缺失时报告失败，不联网下载。
- 批量安装中单项失败必须返回非零并列出失败项，不得把部分成功报告成全部成功。
- 不读取、记录或输出 API key。`vision-bridge` 与 `cheap-research` 的 `config.json` 由用户自行填写。
- 活动 Codex 路径绝不执行任何 `mcp/*/install.sh` legacy installer，也不写 Claude 配置。

## 卸载

卸载只使用：

```bash
bash mcp/uninstall-codex.sh --dry-run [name]
bash mcp/uninstall-codex.sh --yes [name]
```

非交互环境没有 `--yes` 时必须拒绝；脚本只调用 `codex mcp remove`，不删除 venv、缓存、配置或用户数据。

## 验收

- dry-run 无 `add/remove` 副作用。
- 相同配置跳过；不同配置退出 2；缺失配置才 add。
- 全程只出现 `codex mcp list|get|add|remove`，没有 Claude 写入或 legacy installer 调用。
- 本步骤不创建 `.ai/icode/` 工单，也不更新 `~/.codex/icode_data/index.json`。
