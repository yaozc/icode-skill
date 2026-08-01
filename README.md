# ICODEX

这是面向 Codex App 的 ICODE 风格 Root Cause Analysis 工作流。它基于 `ayukyo/icode-skill` 的根因优先思想，改成：

- Codex App 负责诊断、实现、自审和审计
- 同模型自审强制执行
- 异模型终审拆到独立 `$icodex-review` skill，默认可由 Claude CLI / Claude Code 执行
- 适用于任何项目开发，尤其适合需要严格根因分析、自审和验证闭环的变更

## 安装

将实现和内部自审 skill 安装到 Codex skills 目录：

```bash
git clone -b codex https://github.com/yaozc/icode-skill.git ~/.codex/skills/icodex
```

如需异模型终审，再把外部审查 skill 安装到另一个 AI 的 skills 目录：

```bash
git clone -b external-review https://github.com/yaozc/icode-skill.git ~/.claude/skills/icodex-review
```

如果已经克隆过：

```bash
cd ~/.codex/skills/icodex
git fetch origin
git checkout codex
git pull
```

显式调用：

```text
使用 $icodex 按根因分析流程处理这个问题
```

## 大型任务：阶段模式

`$icodex` 同时保留原 ICODE 的七阶段流程。Codex 不把 `/icode` 识别为内置斜杠命令，因此使用 `stage=` 选择阶段：

```text
$icodex stage=00_init 修复当前数据同步问题
$icodex stage=01_plan
$icodex stage=02_review rounds=3
$icodex stage=03_merge
$icodex stage=04_code
$icodex stage=05_deepcheck
$icodex stage=06_audit
```

也可以使用自然语言：

```text
使用 $icodex 执行 00_init，先和我多轮讨论需求，不要写代码
使用 $icodex 继续执行 01_plan
```

`00_init` 开始后，同一会话中的补充信息会持续更新当前 `00_init.md`，不需要每轮重新调用。每个阶段默认完成后暂停，等待确认再进入下一阶段；如果希望自动串联全部阶段，可以明确说：

```text
$icodex 请按 00_init → 06_audit 完整执行，每个阶段完成后自动进入下一阶段
```

所有阶段共用同一个 `.ai/icode/{timestamp}-{short-task}/` 目录，不会为每个阶段创建新目录。旧版 `/icode init`、`/icode plan` 等写法仅作为兼容文档，不应当视为 Codex 的内置命令。

## 使用场景

当任务涉及以下内容时使用：

- 非平凡 bug fix 或 regression fix
- risky refactor
- async、lifecycle、state machine、resource ownership 问题
- 任何需要更严格根因分析、自审和验证闭环的项目开发任务
- 需要 root-cause-first diagnosis
- 需要 mandatory same-model self review

## 工作流

1. Diagnose：先复现、观察、提出假设、反证，最后确认 Root Cause。
2. Plan：让修复策略直接对应根因，并列出风险、替代方案和验证命令。
3. Implement：做最小精确修改。
4. Self Review：以 Senior Reviewer 角色复读 RCA、Plan 和 diff，找具体缺陷。
5. Self Audit：以 Principal Engineer 角色假设实现是错的，逆推攻击方案。
6. Verify：运行最相关检查，无法运行时说明原因和残余风险。
7. Handoff：如需异模型终审，把产物目录和 git diff 交给 `$icodex-review`。

阶段模式会保留以下原有能力：

```text
00_init  需求初稿与多轮讨论
01_plan  正式计划
02_review 多轮计划审查
03_merge 采纳审查意见并定稿
04_code  严格实施编码
05_deepcheck 三阶段深度复检
06_audit 终审、修复和验证
```

## 产物策略

重大任务会把产物保存到：

```text
.ai/icode/{timestamp}-{short-task}/
```

例如：

```text
.ai/icode/20260626-1430-fix-ble-timeout/
```

包含：

- `RCA.md`
- `PLAN.md`
- `IMPLEMENT.md`
- `SELF_REVIEW.md`
- `AUDIT.md`

阶段模式额外保留编号产物：`00_init.md`、`01_plan.md`、`02_review.md`、`03_plan_final.md`、`05_reverse.json`、`05_review_rounds.json`、`06_audit.md`、`06_fixes.log` 和 `.ico_metadata.json`。它们与当前运行共用同一个目录。

小任务只在对话中给出简短 RCA、自审和验证结果，避免污染仓库。

## 异模型终审

异模型终审由独立 skill 负责：

```text
$icodex-review 审查当前 git diff 和 .ai/icode/{run_dir} 产物，只输出 EXTERNAL_REVIEW.md，不要修改代码
```

## 结构

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    └── domain-checklists.md
```

## 许可证

MIT
