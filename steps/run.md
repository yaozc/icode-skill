# 步骤 start / run — staged 1→6 自动编排

> **Codex 持久化前置**：执行本步骤前必须完整读取 [references/codex_runtime.md](../references/codex_runtime.md)；路径、状态、锁、合并读取、迁移和 artifact_map 与旧文字冲突时以该文件和 `~/.codex/skills/icodex/tools/icode_state.py` 为准。

**命令**：`$icodex start [需求]` / `$icodex run [需求]`

`start` 是与上游一致的 staged 标准全流程入口，`run` 是 Codex 兼容别名；二者行为完全一致。它们复用 [01_plan.md](01_plan.md) 的目录选择与需求解析，并依据 metadata 从下一未完成步骤严格推进至步骤 6：

```text
01_plan → 02_review → 03_merge → 04_code → 05_deepcheck → 06_audit
```

执行约束：

1. 创建或复用同一个 `.ai/icode/<run-name>/`，初始化全部稳定 `artifact_map` 键为 `null`；不得为后续步骤另建目录。恢复时先验证 `completed_steps` 是 1→6 的有序前缀（可带前置 `0` 或 `log`），从下一未完成步骤继续；已完成工单只校验并报告，不重复执行。
2. 每个步骤开始前完整读取对应 step 文件；步骤结束后用 `publish-artifact` 发布该步产物并更新 `completed_steps`。
3. 每次转换都校验对应 artifact 存在、status、`completed_steps`、必要的 `code_files`，并运行 `python3 ~/.codex/skills/icodex/tools/icode_state.py validate --run-dir "${ICODE_OUT_DIR}"`。校验非零、L1 前置失败、未解决的阻塞问题或用户决策缺失时立即停止，报告当前状态和 `$icodex start` 恢复命令。
4. 普通 L2/L3 发现按各步骤既有规则记录和处理；不得为了“自动串联”跳过 review、code review fix、deepcheck 或 audit 的修复闭环。
5. 步骤6完成且状态校验通过后才可报告 staged run 完成。需要外部独立终审时，把当前目录、git diff 和验证证据交给 `$icodex-review`。

`$icodex plan` 不路由到本文件；它只执行 [01_plan.md](01_plan.md) 并在步骤1后停止。
