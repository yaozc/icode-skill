# fast 风险评估、自动升级与同工单恢复
> **业务流程合同前置**：先读取 [workflow_contract.md](workflow_contract.md)；新票默认 workflow_contract_version=1，旧票执行新版先 configure-workflow 显式迁移。每次推进前读取 workflow-plan；重大增量 record-delta 在原票回步骤1，更新计划后 accept-replan 再执行2→6；未决 semantic_decisions 阻断实现，生命周期预期缺失阻断编码。verification-pending 只读显示分层债务；completed 不代表 delivery_verdict=verified。


本文件和 `icode_state.py` 是 Codex fast 升级真源。`start` 等价表示 staged 步骤1→6，不能切换到 concise 布局。代理判断业务风险，工具执行模式升级、状态回流和下一步分派。

## 九类风险

| risk_flags 键 | 触发条件 |
|---|---|
| cross_component | 跨组件、跨模块、跨仓或新架构/协议边界修改 |
| persistent_identity_change | 持久化实体合并、删除、重命名、替代或身份变化 |
| dependency_migration | 依赖关系或归属需要迁移 |
| async_observer_or_cache | 异步观察者、缓存、索引、注册表或共享状态参与 |
| restart_replay_semantics | 重启、恢复、重放、幂等重试或回滚语义受影响 |
| external_consumer_change | 外部消费者行为、公开合同或安全边界变化 |
| real_env_verification | 需要真实环境、设备或部署验证 |
| unresolved_semantic_decision | 业务策略/外部行为尚未确定，存在待解决语义决策 |
| major_requirement_delta | 执行中发生重大需求增量，原计划范围发生实质变化 |

依据需求、已有计划、实际调用/模块关系和新证据逐项判断。文件数少不等于低风险；单文件缓存修改也必须升级。低风险纯计算、明确局部修复且九项都不触发才保持 fast。未知项不能默认为 false；存在未解决业务语义时标记 unresolved_semantic_decision 并按现有澄清规则解决，升级不代替业务决策。

## 评估与分派

fast 新工单首次 `publish-artifact --key plan` 后，进入步骤2之前必须评估；未完成旧 fast 恢复、每次步骤转换、review/deepcheck 单步恢复、等待结束或执行中出现新证据时，按完整上下文重新评估。评估文件由代理写到工单内 `fast_risk_assessment.json`，用户无需提供 JSON。评估结果通过 helper 写入 metadata，不直接修改 risk_profile。

评估 JSON 包含完整九项 `risk_flags`（值为布尔）和完整九项 `evidence`（每项为非空判断依据，含已检查模块/文件或需求章节）。例如局部纯计算的完整判断：

```json
{
  "risk_flags": {
    "cross_component": false,
    "persistent_identity_change": false,
    "dependency_migration": false,
    "async_observer_or_cache": false,
    "restart_replay_semantics": false,
    "external_consumer_change": false,
    "real_env_verification": false,
    "unresolved_semantic_decision": false,
    "major_requirement_delta": false
  },
  "evidence": {
    "cross_component": "计划 §3 与源码核对：仅增加既有工具内的纯计算函数，无跨组件调用变更",
    "persistent_identity_change": "源码核对：不读写持久化实体或身份",
    "dependency_migration": "计划 §3：不改变依赖关系及归属",
    "async_observer_or_cache": "源码核对：无异步调用、缓存、索引、注册表或共享状态",
    "restart_replay_semantics": "函数只依赖输入，无恢复、重放、重试或回滚合同",
    "external_consumer_change": "调用方核对：既有接口与消费者合同保持一致，不涉及安全边界",
    "real_env_verification": "验收计划：可由本地单元测试覆盖，无现场验证要求",
    "unresolved_semantic_decision": "需求与计划：输入输出和异常策略均已确定",
    "major_requirement_delta": "需求对照：当前范围与计划一致，没有新增业务合同"
  }
}
```

这只是格式示例，不能将其 false 或文字照抄为本工单判断。命中项改 true，证据写真实影响范围。

```bash
python3 ~/.codex/skills/icodex/tools/icode_state.py assess-fast-risk \
  --run-dir "${ICODE_OUT_DIR}" \
  --assessment-json "${ICODE_OUT_DIR}/fast_risk_assessment.json"
python3 ~/.codex/skills/icodex/tools/icode_state.py workflow-plan \
  --run-dir "${ICODE_OUT_DIR}"
```

任一命令失败立即停止，不能用 fast 默认值继续。`workflow-plan` 是只读执行合同，返回 `next_step`、`remaining_steps`、`review_max_rounds`、`review_adversarial` 和 `deepcheck_phases`。重新 Read metadata，按最新 next_step 执行相应步骤；不能使用评估前的状态、会话旧变量或只看最初的 fast 命令。

## 模式与历史

- `risk_profile.requested_mode` 保留最初请求，`effective_mode` 表示实际模式；metadata.mode 和 workflow_kind 与实际模式同步。
- 命中任一风险自动 full，审查默认至少3轮且恢复对抗，深检运行 Reverse/Fixed/Free；输出 `▶ fast 命中风险标志（<triggers>），自动升级 full 模式，继续原工单`。
- 升级后不自动降回 fast；历史命中项和其证据不被新的 false 判断抹除。当前移植不支持高风险 override 绕过。
- 首次升级时若 fast review 已进行或完成，保存 upgrade_snapshot，保留计划及入口标记，回到 plan_done，next_step=2，完整重跑2→6。保留 ticket_id、工单目录、源码和旧产物，不创建新工单，不恢复旧 fast 计数器。后续恢复不重复回流。
- full 重跑发布已有旧文件时，publish-artifact 自动使用工单内 full/ 升级轮次与内容哈希路径并更新 artifact_map；即使内容相同也另行发布，旧文件保留。状态门禁拒绝把旧 fast 映射直接计为 full 完成。读取、前置检查和后续发布以 artifact_map 为准，文档中的固定文件名只是逻辑名称，不能拿旧 fast 文件当最新结果。
- 历史工单缺 risk_profile 可以只读 validate；fast 真正执行前必须补评估。普通 update-metadata 不允许修改 risk_profile 或将实际模式降回 fast。
- 若升级回流导致 status 改变，按原全局索引协议更新原 ticket_id 条目，不生成新索引身份；完整流程结束后再更新 completed。
