# Codex Crosscheck 与 Start 串联设计

## 目标

将上游 ICode 的持久化、多轮 `crosscheck` 复评能力适配到 `$icodex`，并将 `$icodex start` 恢复为步骤 1→6 的全流程入口，同时不破坏 Codex 专用的存储、状态和外部复核边界。

## 范围与非目标

本次只修改 `codex` 分支。

- 新增 `$icodex crosscheck`、其工具、schema、测试和使用文档。
- 将 `$icodex start` 改为全流程自动串联；保留 `$icodex run` 为同义兼容入口。
- `$icodex plan` 仍然只完成步骤 1 后停止。
- 保留 `$icodex-review` 的一次性、完全无写入外部终审，不重命名、不删除、不改变其分支边界。
- 不引入上游 `.icode_output/`、`~/.claude/icode_data/`、`icode_control.py`、Agent Runtime 或 UI。

## 存储与隔离契约

Crosscheck 仅接受 `status=completed` 且 `ticket_id` 非空的 Codex 工单。目标通过 `.ico_metadata.json` 的 `artifact_map` 解析；不得按固定文件名猜测逻辑产物。

每个目标工单在项目内只有一个独立容器：

```text
<project-root>/.ai/icode/.crosscheck/icode_N/
```

容器中保存 manifest、每轮 fresh/final JSON、worklist、Markdown 报告和累计 findings。它不得包含 `.ico_metadata.json`，不得被 `list`、`status`、索引或主流程状态机视为正式工单。

Crosscheck 可以只写其自身容器；必须零回写目标工单、源码、`.ico_metadata.json`、`artifact_map`、`index.json`、anchors、patch history 和验证记录。

## Crosscheck 流程

1. `start` 以 ticket id、工单目录或工单内产物路径唯一解析目标；无参数只允许使用显式绑定的工单上下文，禁止按 latest 猜测。
2. 开始时冻结目标工单普通文件、`code_files`、Git 基线和关键证据的摘要；恢复未完成轮次时输入不变则复用该轮。
3. 先进行独立 fresh review，并登记实际阅读过的文件和 finding 的行号、摘录、内容哈希。freeze 前不得读取此前 crosscheck 结论。
4. `freeze` 后才允许与前一完成轮比较，显式记录 `new`、`still_present`、`resolved`、`superseded`、`regressed` 或 `not_rechecked`。
5. `finish` 重新采样输入；若工单、代码或 Git 基线变化，当前轮标记 `stale_input`，保留草稿但不生成有效完成结论。

严重度、finding 生命周期、schema 和校验逻辑沿用上游 crosscheck 的语义，但所有路径和 target 解析改为 Codex `.ai/icode` / `icode_state.py` 契约。

## Start / Run 命令契约

```text
$icodex start <需求>  # 创建或恢复工单，并从下一未完成步骤自动串联至步骤 6
$icodex run <需求>    # start 的兼容同义入口，行为完全一致
$icodex plan <需求>   # 仅执行步骤 1，完成后停止
```

`start` 与 `run` 复用现有 run 编排规则：依据 `completed_steps` 从下一未完成步骤恢复；每个转换点先校验对应 artifact、状态、`code_files` 和 `python3 tools/icode_state.py validate --run-dir ...`。任一 L1 校验失败时立刻停止，绝不跳步。`fast` 行为不变。

## 文件边界

| 文件 | 责任 |
|---|---|
| `SKILL.md` | 暴露 `$icodex crosscheck` 与新的 start/run/plan 语义、目录和边界。 |
| `steps/crosscheck.md` | 对话层复评流程与零回写规则。 |
| `references/crosscheck_mode.md` | 容器、轮次、快照、恢复和发现项生命周期真源。 |
| `references/inspection_worklist.md` | fresh review 实读和 finding 定位的可审计清单。 |
| `tools/icode_crosscheck.py` | 只管理 crosscheck 容器、快照、冻结、完成和校验。 |
| `tools/inspection_worklist.py` | worklist 初始化、阅读登记、冻结与校验。 |
| `schemas/crosscheck-*.schema.json` | manifest 与每轮结果的机器可校验合同。 |
| `steps/run.md` 与 `steps/01_plan.md` | 将 start 路由到 run，保留 plan 单步语义。 |
| `tests/test_crosscheck*`、`tests/test_inspection_worklist*` | 覆盖正常、多轮、输入漂移、零回写、路径隔离和 start/run 文档契约。 |

## 验收标准

- Crosscheck 的所有新写入均在 `.ai/icode/.crosscheck/`，且目标工单和源码摘要前后一致。
- 目标不是 completed、身份不唯一、输入漂移或 fresh 未冻结时均 fail-closed。
- 第二轮无法静默丢弃第一轮 finding。
- `$icodex start` 和 `$icodex run` 都声明并执行 1→6 的同一门禁链；`$icodex plan` 明确只执行步骤 1。
- 新增测试通过，现有 `icode_state.py` 验证不被绕开。

## 风险与缓解

- 上游实现耦合 Claude 路径：移植时逐项替换为 `.ai/icode` 和 `~/.codex`，测试中断言不存在 `.icode_output` / `~/.claude` 写路径。
- Crosscheck 被误认为主流程步骤：容器不写 metadata，也不写索引；文档明确它不自动 patch、commit 或 push。
- start 语义变化影响旧用户：`plan` 维持单步入口，`run` 维持全流程兼容入口，并在帮助与示例中明确迁移方式。
