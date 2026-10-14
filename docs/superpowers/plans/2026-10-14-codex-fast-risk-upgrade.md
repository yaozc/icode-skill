# Codex fast 风险升级实施计划

**Goal:** 复杂业务在原工单自动执行 start 等价的 staged 全流程。

**Architecture:** 在现有 icode_state 原子状态工具内添加风险评估与只读分派；步骤文档使用同一风险合同，避免上游 requested mode 与旧下游 mode 判定冲突。

**Tech Stack:** Python 标准库、pytest、现有 Bash 契约。

## 任务与验证

- [x] 添加 test_fast_risk.py：九类触发、低风险、非法输入、幂等、晚升级、同工单全链及 CLI 回归。
- [x] 添加 assess-fast-risk/workflow-plan；在 validate_metadata、update-metadata 和重跑产物发布中执行风险合同。
- [x] 更新 fast、plan、review、merge、code、deepcheck、audit、SKILL 和共享 metadata/runtime 规则；补齐 lint 防回归，帮助及中英文 README 同步。
- [x] 验证风险自动分派与 full 重跑产物不覆盖旧文件；运行全量 pytest、所有 shell 契约和 Codex lint，检查 diff。

此前选择性移植仍保留在工作区，本任务不撤销或混改它们；本次同样不提交或推送，也不修改实际全局技能安装。

## 验证记录

- 新增风险回归在旧实现上失败：缺少 assess-fast-risk/workflow-plan 和风险合同。
- 九类上游风险分别升级 full；低风险保留 fast；缺评估的历史 fast 执行被拒绝，但历史只读 validate 兼容。
- 两个独立进程并发评估，风险在同一 .ico.lock 下合并，不丢失命中项。
- 晚升级在同工单保留入口前缀与身份，回流2→6；模拟逐步发布完整流程产物，验证旧文件不变、映射指向新版本、完成态仍通过 Codex 原生工单校验。
- 旧 fast 映射直接冒充 full 完成被拒绝；升级不可降回 fast；原低风险 review N 单步增强仍可使用。
- 全量 Python：155 passed；全部6个既有 shell 契约通过；Codex contract lint 与 git diff --check 通过。
- 风险业务语义仍由技能代理基于代码/需求证据判断；测试验证确定性升级、状态/发布门禁和执行分派，不将格式校验称为自动语义分析。
