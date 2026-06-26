# ICODEX

这是面向 Codex App 的 ICODE 风格 Root Cause Analysis 工作流。它基于 `ayukyo/icode-skill` 的根因优先思想，改成：

- Codex App 负责诊断、实现、自审和审计
- 同模型自审强制执行
- 异模型终审可选，默认使用 Claude CLI
- 适用于任何项目开发，尤其适合需要严格根因分析、自审和验证闭环的变更

## 安装

将本仓库的 `codex` 分支安装到 Codex skills 目录：

```bash
git clone -b codex https://github.com/yaozc/icode-skill.git ~/.codex/skills/icodex
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

## 使用场景

当任务涉及以下内容时使用：

- 非平凡 bug fix 或 regression fix
- risky refactor
- async、lifecycle、state machine、resource ownership 问题
- 任何需要更严格根因分析、自审和验证闭环的项目开发任务
- 需要 root-cause-first diagnosis
- 需要 mandatory same-model self review
- 需要 optional cross-model final review

## 工作流

1. Diagnose：先复现、观察、提出假设、反证，最后确认 Root Cause。
2. Plan：让修复策略直接对应根因，并列出风险、替代方案和验证命令。
3. Implement：做最小精确修改。
4. Self Review：以 Senior Reviewer 角色复读 RCA、Plan 和 diff，找具体缺陷。
5. Self Audit：以 Principal Engineer 角色假设实现是错的，逆推攻击方案。
6. Verify：运行最相关检查，无法运行时说明原因和残余风险。
7. External Review：仅当显式开启时调用 Claude CLI 或其他异模型终审。

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
- `EXTERNAL_REVIEW.md`，仅在请求异模型终审时生成或记录跳过原因

小任务只在对话中给出简短 RCA、自审和验证结果，避免污染仓库。

## 异模型终审

当用户或配置开启 external review 时，默认使用 Claude CLI 做只读终审。命令模板见 [references/external-review.md](references/external-review.md)。

简化示例：

```bash
claude -p "Review .ai/icode/{run_dir}/RCA.md, PLAN.md, IMPLEMENT.md, SELF_REVIEW.md, AUDIT.md and the current git diff. Output EXTERNAL_REVIEW.md with PASS or FIX_REQUIRED."
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
