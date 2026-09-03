# ICODEX Review

这是 ICODEX v2.17 的只读异模型终审 skill。它用于另一个 AI 完成 `$icodex` 实现、自审、自审计和验证之后，对 `.ai/icode/<run-name>/` 产物和当前 `git diff` 做独立终审。

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
$icodex-review 审查当前 git diff 和 .ai/icode/{run_dir} 产物，只输出 EXTERNAL_REVIEW.md，不要修改代码
```

## 输入

优先读取 `.ai/icode/<run-name>/.ico_metadata.json`，根据 `artifact_layout` 和 `artifact_map` 解析产物；不得猜测文件名或修复 metadata。

- Codex full / `concise`：`root_cause`、`plan`、`implementation`、`deepcheck`、`audit`（通常为 `RCA.md`、`PLAN.md`、`IMPLEMENT.md`、`SELF_REVIEW.md`、`AUDIT.md`）
- staged：按映射读取 `requirement`、`root_cause`、`plan`、`plan_review`、`final_plan`、`implementation`、`deepcheck`、`audit`（通常为 `00_init.md` 至 `06_audit.md`）
- 当前 `git diff` 与可用验证输出

入口未使用或未执行的 staged 可选产物可以缺失；关键产物、映射或验证证据不足时，明确记录缺口并输出 `SKIPPED`，不写入或修改任何文件。

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
