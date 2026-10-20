# ICODEX Review

这是 ICODEX v2.17 的只读异模型终审 skill。它用于另一个 AI 完成 `$icodex` 实现、自审、自审计和验证之后，对 `.ai/icode/<run-name>/` 产物、明确的 dirty/commit/base-head 改动范围与验证证据做独立终审。

核心约束：

- 只审查，不改代码
- 不执行实现、不运行格式化、不提交、不推送
- 只返回 `EXTERNAL_REVIEW.md` 内容，由调用方决定是否保存
- 最终结论只能是 `PASS`、`FIX_REQUIRED` 或 `SKIPPED`

## 安装

安装到执行外部终审的 AI 环境。例如 Claude Code：

```bash
git clone -b external-review https://github.com/yaozc/icode-skill.git ~/.claude/skills/icodex-review
```

如果也想装到 Codex：

```bash
git clone -b external-review https://github.com/yaozc/icode-skill.git ~/.codex/skills/icodex-review
```

## 调用

```text
$icodex-review 审查 .ai/icode/{run_dir}，范围 dirty，只输出 EXTERNAL_REVIEW.md，不要修改代码
```

## 输入与审查范围

先读 [共享审查合同](references/workflow-contract.md)，再根据 `artifact_layout` 和 `artifact_map` 读取当前产物；`full/`、`replan/` 等映射路径有效，不能猜固定文件名。

已提交代码请提供 commit 或 base/head，不因工作树 diff 为空自动放行。

```text
$icodex-review 审查 .ai/icode/{run_dir}，范围 commit <commit>，只输出 EXTERNAL_REVIEW.md
$icodex-review 审查 .ai/icode/{run_dir}，范围 base <base> head <head>，只输出 EXTERNAL_REVIEW.md
```

dirty 要分别盘点暂存、未暂存和未跟踪文件，明确排除项。commit/base-head 记录解析后的 SHA，并用对应提交的源码 blob 核对 `source_hashes`；当前工作树证据不能自动替代历史候选证明。Git 读取禁用外部 diff、textconv、fsmonitor 和可选索引写入。

工作区内容使用可信内建工具与原始提交/索引 blob 比较，不运行工作区 git diff/status，避免 clean/process filter。

所有 Git 读取设置 GIT_NO_LAZY_FETCH=1 并使用 --no-pager；缺失对象作为证据缺口，不自动取回对象或执行远程 helper/pager。

不得运行待审仓库的代码或 helper。

## 新流程合同

| 检查项 | 审查要求 |
|---|---|
| 模式与产物 | 按完成前缀确定必需映射；完成步骤2必须有 `plan_review`。按 `risk_profile.effective_mode` 检查 full/fast、审查预算和深检证据，不沿用最初请求 |
| 语义与重计划 | 核对 `semantic_decisions`、`requirement_deltas`、`replan_state`；新代际不能复用旧映射，诊断结论不能冒充实施交付 |
| 生命周期 | `acceptance_contract.required` 时检查四阶段×四类消费者16项预期，并分别核对运行证明 |
| 分层证据 | 核对稀疏 `verification_contract.required_cells`、最新匹配 `verification_runs`、执行前 `baseline` 和当前证据摘要；host/simulated 不能替代 physical |
| 新旧格式 | 无 `workflow_contract_version` 的历史票保持限定范围只读审查；未知显式版本不能当历史格式，缺新版字段不得自动填充 |

已完成流程不等于业务验证通过。

报告分别说明 workflow status、implemented、`delivery_verdict`、方向 verdict 和最终外部审查结论。旧票缺新字段不自动推出 verified；未声明验证范围或缺少相关证明仍须报告缺口。

仅缺证据时返回 SKIPPED；确定违规优先返回 FIX_REQUIRED。

退出码0不单独证明测试通过；零用例/全部跳过为 inconclusive，实际失败不能降级。

可选 test_report/test_summary/test_exit_code 按共享合同核对真实报告计数、原始身份、当前候选/cell 和历史重放；旧无摘要记录不追溯补造。外审消费已有证据，不运行待审测试或 helper。

公共库按源码兼容、二进制 ABI 兼容、运行行为分别审查；Read 登记不等于实际阅读或覆盖完成。

## 输出

保留 Root Cause Review、Implementation Review、Architecture and Contract Review、Regression Review、Security Review、Performance Review、Findings 和 Final Decision，追加 Workflow Contract Review、Verification and Delivery Review，以及范围/SHA/候选匹配与债务说明。Final Decision 仍只有 `PASS`、`FIX_REQUIRED`、`SKIPPED`；PASS 限于证据足够的明确审查范围。

## 维护与契约回归

```bash
python3 -B tools/lint_review_contract.py .
python3 -B -m unittest discover -s tests -v
```

契约检查仅验证文档规则和 Git 示例，不证明 AI 已正确执行审查。

回归包含删除/反转关键规范句、报告接口和双语说明、断链接/坏文件，以及隔离 Git 仓库中的暂存/未暂存/未跟踪、提交/root commit/历史范围、候选摘要不匹配、危险 ref 和禁用配置程序实验。检查器只读技能文档，不验证或修改目标工单；测试 fixture 写入仅发生在维护者主动运行的临时目录。

## 推荐流程

```text
$icodex（full 或 staged）
  ↓
metadata + artifact_map + 产物 + VERIFY
  ↓
$icodex-review
  ↓
EXTERNAL_REVIEW.md
  ↓
PASS 或把 FIX_REQUIRED findings 交回 $icodex
```

## 许可证

MIT
