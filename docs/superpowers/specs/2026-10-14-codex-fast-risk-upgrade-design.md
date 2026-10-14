# Codex fast 风险自动升级

## 需求与适配

移植 main 的九类风险与 requested/effective 模式区分。风险判断由执行技能的代理基于需求、计划、实际模块关系和执行中新增证据完成，不以关键词命中替代业务语义。工具负责确定性升级和持久化校验。

`risk_profile.requested_mode` 保留最初请求；`risk_profile.effective_mode`、`metadata.mode`、`workflow_kind` 同步为实际模式。命中任一风险就升级 full，不自动降回 fast。继续使用原 ticket_id、目录、代码与索引身份。

## 状态与恢复

- 九类 risk_flags 都必须是明确布尔值，每项 evidence 都包含判断依据；未知或未评估项不能默认为 false。
- `icode_state.py assess-fast-risk` 使用现有工单锁和原子写入，合并历史已命中风险；`workflow-plan` 只读返回真实下一步、审查轮数、对抗开关和深检阶段。
- 新工单先按原发布合同发布计划，再评估风险；步骤2之前、每次转换或恢复以及执行中出现新风险时重新评估。
- 如果此前已完成 fast 审查，或 fast 审查正在进行，首次升级保存旧状态/产物映射快照，回到同工单 plan_done，保留计划与入口前缀，从步骤2按 full 重跑至步骤6。已实现源码保留，不能用旧 fast 审查或 Reverse 结果跳过完整检查。
- 重跑已有产物时发布到工单内带升级轮次和内容哈希的 full/ 修订路径；即使内容相同也另行发布，旧文件保留，artifact_map 指向新版。状态校验拒绝用旧 fast 映射计为 full 完成，下游只读 artifact_map，不读取旧固定文件。
- 历史 metadata 缺 risk_profile 仍可只读验证；fast 执行入口 workflow-plan 则必须先补齐风险评估，不能因字段缺失默认低风险。

## 边界

不引入 main 的 Claude 控制面、workflow MCP 或新技能入口。完整流程仍是 staged 1→6，不转换成 concise Codex full mode。当前需求要求复杂业务自动升级，不导入上游人工强制保留高风险 fast 的 override 绕过项。

## 验收

九类风险分别触发 full；全部低风险保持 fast；恢复及重复评估不能降级或反复回退；晚发现风险必须补跑完整审查；工单身份与旧文件不变；新产物映射可完成 full 全链。非法类型、未知标志、缺评估、未升级高风险及普通 metadata 更新绕过均被拒绝。原 full/concise 状态合同与既有测试保持通过。
