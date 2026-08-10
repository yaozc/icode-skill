# Codex 运行时契约

本文件是所有活动步骤的持久化真源；与旧步骤文字冲突时以这里和 `~/.codex/skills/icodex/tools/icode_state.py` 为准。

## 路径与只读兼容

- 新工单：`<project>/.ai/icode/<run-name>/`
- 新全局数据：`~/.codex/icode_data/`
- legacy 工单 `.icode_output/` 与 legacy 全局数据 `~/.claude/icode_data/` 只读。查询使用合并视图；续写前必须迁移，禁止直接修改旧源。
- 活动步骤禁止直接写 Claude 配置，禁止调用 legacy MCP installers。

## metadata 与产物发布

每个工单的 `.ico_metadata.json` 必含：`artifact_layout`、`workflow_kind`、`status`、`current_phase`、`completed_steps`、`completed_phases`、`artifact_map`、`patch_count`、`patch_history`、`code_files`。`artifact_map` 创建时包含全部稳定键且值均为 `null`：

```text
requirement root_cause plan plan_review final_plan implementation
deepcheck audit patches delivery_report delivery_brief
```

staged 布局的标准映射是 `00_init.md`、`log_analysis.md`、`01_plan.md`、`02_review.md`、`03_plan_final.md`、`04_code_review_fix.md`、`05_deepcheck.md`、`06_audit.md`、`08_patch.md`；未经过对应步骤时保持 `null`。concise 布局使用 `RCA.md`、`PLAN.md`、`IMPLEMENT.md`、`SELF_REVIEW.md`、`AUDIT.md`。

产物必须先写临时草稿，再发布：

```bash
python3 ~/.codex/skills/icodex/tools/icode_state.py publish-artifact \
  --run-dir "${ICODE_OUT_DIR}" --key <stable-key> \
  --source <verified-draft> --name <relative-name>
python3 ~/.codex/skills/icodex/tools/icode_state.py validate --run-dir "${ICODE_OUT_DIR}"
```

只有两条命令都成功才推进状态。`status`、`patch`、`readme` 与历史检索只通过 `artifact_map` 找文件，不猜编号名。patch 先用 `reserve-patch` 取得唯一编号。

普通状态字段更新写入临时 JSON 后调用 `update-metadata --patch-json <file>`；全局索引条目写入临时 JSON 后调用 `upsert-index --codex-root ~/.codex/icode_data --entry-json <file>`。不得在 Markdown 步骤里自行实现无锁的 `json.load → 修改 → write_text`。legacy overlay 只能包含来源标识和 `hit_count/last_used_at/stale/stale_reason` 可变字段。

## 状态前缀

- concise：`completed_phases` 是 `diagnose,plan,implement,self_review,audit,verify` 的精确前缀；`current_phase` 是下一阶段；完整时 `status=completed` 且 `current_phase=null`。
- staged：`completed_steps` 可由互斥的 `0` 或 `log` 开头，之后是 `1,2,3,4,5,6` 的精确前缀；状态必须与前缀匹配。
- 任意乱序、重复、跳号、状态不匹配、必需映射缺失或映射越界都停止写回。

## 合并读取与迁移

查询两侧数据时使用：

```bash
python3 ~/.codex/skills/icodex/tools/icode_state.py merged-index --codex-root ~/.codex/icode_data --claude-root ~/.claude/icode_data
python3 ~/.codex/skills/icodex/tools/icode_state.py merged-files --kind <project_docs|module_docs|limits> --codex-root ~/.codex/icode_data --claude-root ~/.claude/icode_data
```

Codex 同 key 优先；legacy-only 条目保持只读。用户要继续旧工单时：

```bash
python3 ~/.codex/skills/icodex/tools/icode_state.py migrate-legacy \
  --project-root <absolute-project> --legacy-run <absolute-legacy-run> \
  --codex-root ~/.codex/icode_data
```

迁移使用确定性目标、SHA-256 清单、`prepared→completed` 两阶段与三类锁；失败后重试同一命令，不删除 prepared 目录，不覆盖发生变化的旧源。
