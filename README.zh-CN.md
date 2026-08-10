# ICode v2.17 Codex 版

ICode 是一个“先定位根因，再实施修改”的 Codex 技能。它把 Codex 连续开发流程与上游 v2.17 分步流程合并，同时保留 Codex 存储、同模型复核、可恢复状态和安全 MCP 注册。

本移植基于 [`ayukyo/icode-skill`](https://github.com/ayukyo/icode-skill) v2.17。

## 安装

把仓库克隆或同步到：

```bash
git clone <你的 fork 地址> ~/.codex/skills/icodex
```

技能入口统一为 `$icodex`。可选 MCP 先预览、再安装：

```bash
bash ~/.codex/skills/icodex/mcp/install-codex.sh --dry-run
bash ~/.codex/skills/icodex/mcp/install-codex.sh
```

适配器只使用 `codex mcp list|get|add|remove`：配置相同就跳过；同名但配置不同则以退出码 2 拒绝，不删除、不覆盖。

## 两种执行模式

直接使用 `$icodex <任务>` 进入 Codex full mode：

```text
根因诊断 → 计划 → 实施 → Senior Reviewer 同模型自审
         → Principal Engineer 审计 → 验证
```

对应 concise 产物为 `RCA.md`、`PLAN.md`、`IMPLEMENT.md`、`SELF_REVIEW.md`、`AUDIT.md`。

显式子命令进入 staged mode：

```text
01 计划 → 02 审查 → 03 定稿 → 04 编码 → 05 深检 → 06 终审
```

`$icodex plan` 与 `$icodex start` 都只执行步骤1并暂停，`start` 是 `plan` 的兼容别名。只有 `$icodex run` 会自动串联 staged 1→6；`$icodex fast` 是精简串联。

## 命令

| 命令 | 用途 |
|---|---|
| `$icodex help` | 只读帮助 |
| `$icodex init [需求]` | 步骤0需求初稿与讨论 |
| `$icodex log [日志/症状]` | 日志根因分析入口 |
| `$icodex plan [需求]` | staged 步骤1，完成后暂停 |
| `$icodex start [需求]` | `plan` 别名，完成后暂停 |
| `$icodex review [N]` | staged 步骤2 |
| `$icodex merge` | staged 步骤3 |
| `$icodex code` | staged 步骤4 |
| `$icodex deepcheck` | staged 步骤5 |
| `$icodex audit` | staged 步骤6 |
| `$icodex run [需求]` | 自动执行 staged 1→6 |
| `$icodex fast [需求]` | 精简 staged 流程 |
| `$icodex patch [变更]` | 在既有工单上追加验证过的补丁 |
| `$icodex doc [描述]` | 工程/模块知识库 |
| `$icodex limit [描述]` | 项目约束红线 |
| `$icodex readme` | 交付报告与跨领域简报 |
| `$icodex status [选项]` | 状态、verdict 与产物校验 |
| `$icodex list [关键词]` | 跨工程只读检索 |
| `$icodex install [name]` | 安全注册 Codex MCP |

异模型独立终审仍由单独的 `$icodex-review` 承担；本地验证完成后向它交付产物目录、diff 和测试证据。

## 存储与恢复

新工程工单只写 `.ai/icode/<run-name>/`；新全局数据只写 `~/.codex/icode_data/`。

每个持久化工单都包含 `.ico_metadata.json` 和稳定 `artifact_map`。状态转换、产物发布、patch 编号、索引更新和 legacy 迁移统一使用 [`tools/icode_state.py`](tools/icode_state.py)，通过同目录原子替换和有界文件锁避免部分写入与并发覆盖。

旧 `.icode_output/` 与 `~/.claude/icode_data/` 仅作为只读兼容源。查询按 key 合并两侧数据并让 Codex 优先；继续旧工单前先执行确定性、清单校验、可恢复的 `prepared → completed` 迁移，旧源永不修改。

## 安全保证

- 活动 Codex 路径不写 `~/.claude.json`，不运行 legacy Claude installer。
- MCP 冲突在安装依赖或注册之前完成检查。
- artifact 路径不能逃逸工单目录。
- full 与 staged 状态数组必须是精确有序前缀。
- 索引、metadata、patch 编号和迁移均受锁保护。
- 索引发布失败后从已发布的 prepared 目录恢复，不重复复制。

路由规则见 [SKILL.md](SKILL.md)，持久化细节见 [Codex 运行时契约](references/codex_runtime.md)。

## 验证

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
bash tests/test_mcp_codex_install.sh
python3 tools/lint_codex_contract.py .
```

许可证：[MIT](LICENSE)。
