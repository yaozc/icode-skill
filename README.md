# ICODEX Review

这是 ICODEX 的只读异模型终审 skill。它用于另一个 AI 完成 `$icodex` 实现、自审、自审计和验证之后，对 `.ai/icode/{run_dir}` 产物和当前 `git diff` 做独立终审。

核心约束：

- 只审查，不改代码
- 不执行实现、不运行格式化、不提交、不推送
- 输出 `EXTERNAL_REVIEW.md`
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
$icodex-review 审查当前 git diff 和 .ai/icode/{run_dir} 产物，只输出 EXTERNAL_REVIEW.md，不要修改代码
```

## 输入

- `.ai/icode/{run_dir}/RCA.md`
- `.ai/icode/{run_dir}/PLAN.md`
- `.ai/icode/{run_dir}/IMPLEMENT.md`
- `.ai/icode/{run_dir}/SELF_REVIEW.md`
- `.ai/icode/{run_dir}/AUDIT.md`
- 当前 `git diff`
- 可用的验证输出

## 输出

输出 `EXTERNAL_REVIEW.md` 内容，包含：

- Root Cause Review
- Implementation Review
- Architecture and Contract Review
- Regression Review
- Security Review
- Performance Review
- Findings
- Final Decision

## 推荐流程

```text
$icodex
  ↓
RCA / PLAN / IMPLEMENT / SELF_REVIEW / AUDIT / VERIFY
  ↓
$icodex-review
  ↓
EXTERNAL_REVIEW.md
  ↓
PASS 或把 FIX_REQUIRED findings 交回 $icodex
```

## 许可证

MIT
