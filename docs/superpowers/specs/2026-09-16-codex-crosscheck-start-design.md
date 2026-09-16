# Codex Crosscheck 与 Start 串联设计

## 目标

将上游 ICode 的持久化、多轮 `crosscheck` 复评能力适配到 `$icodex`，并将 `$icodex start` 恢复为步骤 1→6 的全流程入口，同时不破坏 Codex 专用的存储、状态和外部复核边界。

## 范围与非目标

本次只修改 `codex` 分支。

- 新增 `$icodex crosscheck`、其工具、schema、测试和使用文档。
- 将 `$icodex start` 恢复为唯一的全流程自动串联入口；不新增上游不存在的 `run` 命令。
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

### 目标校验

Crosscheck 在 `start` 和 `finish` 两个边界都必须调用 `icode_state.py` 的同一验证逻辑，完整校验 metadata、`artifact_map`、status 与 completed steps。缺少稳定键、映射不是相对路径、映射越过工单目录、映射文件不存在或完成态产物不完整，均按 L1 fail-closed。`code_files` 还必须逐项验证为项目执行根内的相对路径；绝对路径、`..` 逃逸、符号链接逃逸或目录项均拒绝，不得仅记录警告后继续。传入的原始目标目录自身不得是符号链接；`start` 恢复已有容器时，在读取或修改轮次状态前，解析后的 canonical 路径还必须与 manifest 中冻结的 `target.ticket_dir` 完全一致，防止同 ticket id 的路径重定向。

### Ticket 唯一解析

在 `tools/icode_state.py` 新增只读 `resolve-ticket --ticket <id> --project-root <root> --codex-root <root>`。解析器只读取当前项目 `.ai/icode/icode_N/` 和 `~/.codex/icode_data/index.json` 的 Codex 原生记录（`legacy_overlay` 不为 `true`；不得依赖只在 merged view 中临时添加的 `source` 字段），不读取或返回 Claude legacy 条目：

1. 以 canonical project root、ticket id 和 `status=completed` 过滤候选，并按 canonical 工单目录去重。
2. 项目目录与索引都命中时，metadata 身份、project root 与索引 out_dir 必须一致；不一致即拒绝，不静默选择其中一个。
3. 零命中或多命中都返回非零和候选证据；唯一命中才输出机器可读 JSON。
4. 解析器不得写 metadata、索引、命中次数或迁移覆盖层，也不得使用 latest 兜底。

## Crosscheck 流程

1. `start` 以 ticket id、工单目录或工单内产物路径唯一解析目标；ticket id 必须经过 `icode_state.py resolve-ticket`。无参数只允许使用显式绑定的工单上下文，禁止按 latest 猜测。
2. 解析后先执行目标校验，再冻结目标工单普通文件、`artifact_map` 解析结果、`code_files`、Git 基线和关键证据的摘要；恢复未完成轮次时输入不变则复用该轮。
3. 先进行独立 fresh review，并登记实际阅读过的文件和 finding 的行号、摘录、内容哈希。freeze 前不得读取此前 crosscheck 结论。
4. `freeze` 后才允许与前一完成轮比较，显式记录 `new`、`still_present`、`resolved`、`superseded`、`regressed` 或 `not_rechecked`。
5. `finish` 重新采样输入；若工单、代码或 Git 基线变化，当前轮标记 `stale_input`，保留草稿但不生成有效完成结论。快照统一忽略 Codex 实际锁文件 `.ico.lock`，并兼容 `.index.lock`、`.migration.lock`，避免纯锁抖动产生假漂移。
6. 只要 manifest 已存在完成轮次，任何改变 manifest 生命周期状态的操作（新一轮 `start`、`freeze`、`finish` 或 stale 标记）都同步刷新派生 Markdown/JSON 报告；因此下一轮进行中时 `validate` 仍能验证累计历史，而不会因报告落后于 manifest 误报失败。

严重度、finding 生命周期、schema 和校验逻辑沿用上游 crosscheck 的语义，但所有路径和 target 解析改为 Codex `.ai/icode` / `icode_state.py` 契约。

### 自身输出排除

目标工单文件摘要仍需覆盖 `.ai/icode/icode_N/`，但源码/Git 基线不得把任何 `.ai/icode/**` 当作实现输入。以下位置必须使用同一排除语义：

- Git status 与未跟踪文件快照过滤 `.ai/icode/**`，因此创建 crosscheck 容器不会让本轮自行漂移。
- inspection worklist 的 tracked、untracked、diff、关联文件与 scope 枚举均排除 `**/.ai/icode/**`。
- worklist 路径安全检查禁止把 `.ai/icode`、`.git` 和凭据路径登记为源码阅读单元。
- finish 只因目标工单、已声明代码文件或过滤后的 Git 基线变化而判定 `stale_input`，crosscheck 自身输出不参与摘要。

## Start 命令契约

```text
$icodex start <需求>  # 创建或恢复工单，并从下一未完成步骤自动串联至步骤 6
$icodex plan <需求>   # 仅执行步骤 1，完成后停止
```

`start` 直接路由到 `steps/01_plan.md`，并依据 `completed_steps` 的连续已完成前缀，通过一个统一分派器进入下一未完成步骤，禁止恢复时固定回到步骤 2。每个转换点先校验对应 artifact、状态、`code_files` 和 `python3 ~/.codex/skills/icodex/tools/icode_state.py validate --run-dir ...`。无参数 `start` 仅恢复最新的未完成 staged 工单；没有可恢复工单且没有需求参数时必须在创建目录前报错。带需求参数时按入口态复用/新建规则处理。任一 L1 校验失败时立刻停止，绝不跳步。`plan` 使用同一文件但步骤 1 完成后停止，`fast` 行为不变。

## 文件边界

| 文件 | 责任 |
|---|---|
| `SKILL.md` | 暴露 `$icodex crosscheck` 与 start/plan 语义、目录和边界。 |
| `steps/crosscheck.md` | 对话层复评流程与零回写规则。 |
| `references/crosscheck_mode.md` | 容器、轮次、快照、恢复和发现项生命周期真源。 |
| `references/inspection_worklist.md` | fresh review 实读和 finding 定位的可审计清单。 |
| `tools/icode_crosscheck.py` | 只管理 crosscheck 容器、快照、冻结、完成和校验，并在 start/finish 调用 Codex 目标验证。 |
| `tools/inspection_worklist.py` | worklist 初始化、阅读登记、冻结与校验。 |
| `tools/icode_state.py` | 新增只读 `resolve-ticket`，统一项目目录与 Codex 索引的唯一身份解析。 |
| `schemas/crosscheck-*.schema.json` | manifest 与每轮结果的机器可校验合同。 |
| `steps/01_plan.md` | 同时承载 start 的全流程入口与 plan 的单步语义；仓库不保留 `steps/run.md`。 |
| `steps/help.md`、`steps/00_init.md`、`steps/log.md`、`steps/08_patch.md` | 更新入口提示、恢复命令和迁移文案，不再把 start 描述为 plan 别名。 |
| `references/dir_and_metadata.md`、`references/anti_laziness.md` | 将 start 纳入全流程目录复用、历史检索和串联规则。 |
| `README.md`、`README.zh-CN.md` | 同步中英文命令表和迁移说明。 |
| `tools/lint_codex_contract.py` | 断言 `start` 路由到 `steps/01_plan.md`、`plan` 保持单步，并拒绝重新引入 `$icodex run`。 |
| `tests/test_icode_state.py` | 覆盖 ticket 唯一解析、索引/metadata 不一致、Codex-only 与零写入。 |
| `tests/test_crosscheck*`、`tests/test_inspection_worklist*` | 覆盖正常、多轮、输入漂移、零回写、路径隔离、自身输出排除和 start 文档契约。 |

## 验收标准

- Crosscheck 的所有新写入均在 `.ai/icode/.crosscheck/`，且目标工单和源码摘要前后一致。
- 目标不是 completed、身份不唯一、输入漂移或 fresh 未冻结时均 fail-closed。
- metadata 缺键、artifact 越界或缺失、`code_files` 越界或符号链接逃逸时，在创建/恢复轮次前 fail-closed。
- `--ticket` 只解析当前项目 Codex 工单；零命中、多命中和索引/metadata 身份不一致均返回非零且不写文件。
- 创建 fresh、worklist、manifest 和报告不会因 `.ai/icode/**` 出现在 Git status 或候选枚举中导致自身 `stale_input`。
- 第二轮无法静默丢弃第一轮 finding。
- `$icodex start` 在 SKILL、plan/help、init/log/patch、共享 references、README 和 lint 合同中被声明为唯一 1→6 入口；不存在 `$icodex run` 或 `steps/run.md`；`$icodex plan` 明确只执行步骤 1。
- 仅 `.ico.lock` 等瞬态锁变化不造成 `stale_input`；下一轮进行中时派生报告与 manifest 一致且 `validate` 通过。
- manifest 目标不能通过工单目录符号链接或同 ticket id 的不同路径重定向。
- 新增测试通过，现有 `icode_state.py` 验证不被绕开。

## 风险与缓解

- 上游实现耦合 Claude 路径：移植时逐项替换为 `.ai/icode` 和 `~/.codex`，测试中断言不存在 `.icode_output` / `~/.claude` 写路径。
- Crosscheck 被误认为主流程步骤：容器不写 metadata，也不写索引；文档明确它不自动 patch、commit 或 push。
- start 语义变化影响旧用户：`plan` 维持单步入口；帮助与示例明确 `start` 是唯一全流程入口，避免维护上游不存在的额外命令。
