# Codex 业务流程合同

本合同移植 main 的五项流程到现有 Codex 状态工具。机器真源是 `tools/workflow_contract.py` 与 `tools/icode_state.py`；所有活动步骤先读取本文。业务含义由代理按需求、代码和用户已授权决策填写，工具不做关键词判断。

## 创建和恢复

首次 `publish-artifact --metadata-seed` 默认初始化 `workflow_contract_version=1`、semantic_decisions、requirement_deltas、replan_state、acceptance_contract、verification_contract、verification_runs。显式版本1缺字段拒绝；无版本历史票只读兼容，不视为验证通过。进入新版执行时先用 configure-workflow 显式迁移，staged 再按当前代码调用 assess-fast-risk；concise 按其阶段合同推进；迁移不会推断旧任务已通过验收。不可用 update-metadata 改合同、验证记录或 delivery_verdict。

每步先 `workflow-plan`；staged 使用 next_step，concise 使用 next_phase/remaining_phases（重大增量回计划仅 staged）。blocking_reasons 非空先解决阻断。`replan_pending=true` 时 next_step=1 优先，保留原 ticket_id/目录；start/fast/plan 必须复用当前回流工单，不能套用“带参新建”规则。所有 Read 和发布通过 artifact_map，原固定编号文件仅为历史。

## 语义决策

涉及允许/拒绝、保留/迁移等外部行为且证据不能唯一决定时，先登记：

```json
{"id":"conflict-policy","status":"open","question":"冲突时保留哪个身份？","evidence":"需求第二段尚未定义"}
```

保存 JSON 并调用 `record-decision --run-dir <run> --input-json <json>`。open 阻断 plan、定稿、编码及实施补丁；diagnosis-only 分析可以继续。用户已授权或可唯一证实时，以同 id 提交 status=resolved，并填非空 decision/evidence；不得用“最安全”替代用户选择。resolved 不得覆写，行为变更走 requirement delta。

## 重大增量回计划

```json
{"id":"delta-1","severity":"major","needs_replan":true,"summary":"新增恢复后外部投影要求","evidence":"用户补充的恢复要求"}
```

`record-delta --input-json` 原子保存旧映射/状态/审查假设，强制 full、审查至少3轮，回到步骤1。minor 必须 needs_replan=false；重大增量不得由轻量 patch 吸收。更新范围、解决语义、更新验收矩阵；发布新完整 plan 后 `accept-replan --run-dir <run>`。未发布新计划或仍有语义/验收缺口拒绝接受。

helper 发布到 `replan/<revision>/`，接受后重新执行2→6，每步需新映射；旧文件和源码不回滚。保留 pending_verification（审查假设）原义，不能用重计划顺带清空。本回流只支持 staged；concise 明确拒绝，保留旧阶段合同。

## 生命周期验收

身份/持久化/重启重放风险或权威状态变化时，acceptance_contract.required=true。matrix 必须覆盖四阶段 immediate/converged/restart/replay × 四消费者 direct_query/aggregate_selector/persistent_reference/external_projection，16项期望均有实际语义；无关消费者写具体“不受影响”理由，不能留空。缺预期阻断 code/实施 patch。使用 configure-workflow 配置完整合同；已 required 不得关闭。

书面预期只证明需求明确，不证明验证完成。verification_contract 的 required_cells 还须覆盖16项 phase/consumer，并有对应当前运行证据；不会仅凭矩阵非空给出 verified。

## 分层验证与债务

```json
{"verification_contract":{"required":true,"requirements_pending":false,"required_cells":[{"layer":"unit","consumer":"direct_query","scenario":"conflict-retry","environment":"host"}]}}
```

configure-workflow 配置稀疏 required_cells，层来自 static/unit/build/host/deploy/delivery/consumption/settings_preview/operation_view/closed_client/physical；可按业务选择必需单元。environment=host/simulated/physical 严格区分，physical 层必须 physical 环境。生命周期单元额外 phase 字段。`real_env_verification` 风险自动开启 required；无明确单元时 requirements_pending=true，且必须有 physical 单元才能验证完整。宿主或模拟通过不能替代实机；此移植不自动连接/部署设备。

1. 用 verification-context 只读取得执行前 baseline（声明 code_files 的 SHA、合同 SHA、重计划 revision、patch_count），保存为 JSON。
2. 在已授权环境执行实际验证，保存非空项目相对证据文件。baseline 不得在执行后重新生成来套旧结果。
3. 用 record-verification --input-json 登记：

```json
{"id":"verify-1","cell":{"layer":"unit","consumer":"direct_query","scenario":"conflict-retry","environment":"host"},"outcome":"pass","baseline":{"ticket_id":"由verification-context原样提供"},"evidence":[".ai/icode/icode_1/unit.log"],"summary":"实际执行命令与可观察结果"}
```

上例 baseline 仅示意，必须填 verification-context 的完整对象。outcome 可 pass/fail/inconclusive/skipped；记录为追加历史，同 id 同内容幂等，不同内容拒绝。记录前必须 staged 已 code_done 或后续状态，或 concise 已完成 implement，baseline 与当前源码/合同完全一致，否则拒绝。证据必须项目内普通非空文件，拒绝绝对路径、逃逸、符号链接。

`verification-pending`/`verification-plan` 只读派生结果，不写 metadata 或索引。每单元取最新记录，失败、跳过、缺证据、源码/合同/patch/revision/证据变化都保留债务。delivery_verdict=blocked/verification_pending/verified/not_assessed，与实现 implemented 和步骤 status=completed、方向 verdict 分开；旧票及未要求验证的任务为 not_assessed。review pending_verification 与交付验证债务不可混用。

绑定范围仅为声明 code_files，代理须补齐所有相关文件。工具能校验摘要与单元匹配，不能自行证明业务语义、设备身份、记录真实性或完整 Git 构建部署来源；实机证据应附目标唯一身份、构建/部署版本和观察结果，不得声称本工具已自动核实设备。

## 补丁诊断

实施使用 reserve-patch 默认 intent=implementation；分析使用 `--intent analysis_only`，发布 patches 时必须 `--patch-number <N>`，finalize 只能 analysis_only，不得转 completed/issues。已有预留续跑在发布和收口处重验 gate，不能绕过重大增量/语义/验收阻断。首个预留到发布之间是既有补丁暂态，专用事实登记及 workflow-plan 可读取严格限定的连续 in_progress 预留；不要求先完成实施才记录重大增量。最终 validate/completed/crosscheck 仍要求实际补丁映射，不手工改计数。
