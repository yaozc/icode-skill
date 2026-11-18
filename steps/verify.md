# 步骤 verify — 验证上下文、运行登记与债务查询

**命令**：`$icodex verify [--pending | --plan | --context | --record <JSON路径>]`
**范围**：既有工单，不创建工单；无参数默认 --pending。不参与1→6推进。

先读 [codex_runtime.md](../references/codex_runtime.md) 和 [workflow_contract.md](../references/workflow_contract.md)，静态规则遵守 [静态 references 读取与复用合同](../references/thinking_core.md#静态-references-读取与复用合同)；通过最新 metadata/artifact_map 找当前工单。沿用安装 helper：

```bash
python3 ~/.codex/skills/icodex/tools/icode_state.py verification-pending --run-dir "${ICODE_OUT_DIR}"
python3 ~/.codex/skills/icodex/tools/icode_state.py verification-plan --run-dir "${ICODE_OUT_DIR}"
python3 ~/.codex/skills/icodex/tools/icode_state.py verification-context --run-dir "${ICODE_OUT_DIR}"
python3 ~/.codex/skills/icodex/tools/icode_state.py record-verification --run-dir "${ICODE_OUT_DIR}" --input-json <实际运行JSON>
```

--pending、--plan、--context 只读，不执行编译/部署/设备命令，不写工单、索引。--record 仅登记明确提供的真实运行证据，baseline 必须在执行前取得；不得把建议或模拟结果登记为 physical。实际外部操作只在用户授权范围内执行，查询请求不授权部署。

展示 implemented、delivery_verdict、blocking_reasons、pending 单元及缺证原因。real_env 或生命周期缺需求时先补合同，不把宿主测试成功宣传为全部验证成功。记录成功后重新查询当前债务，不以单次 pass 判断整体 verified。

实际执行与报告按以下顺序核对（查询或登记本身不计作运行测试）：

1. 先读当前 verification-plan/verification-pending，确定待验证单元和授权范围；执行前保存 verification-context 的完整 baseline。
2. 在授权环境运行选定命令，写出实际完成的阶段/步骤、环境、退出码/超时、用例计数与观察结果；保存本次 runner 原始输出和实际生成的报告。
3. 实际流程步骤、verification_runs[].id 或供应方执行标识必须与原始日志逐项对账。
4. 每次新执行必须使用新的执行标识和独立证据路径，保留独立原始日志，不覆盖旧执行。
5. 用既有 record-verification 输入中的 id/evidence/summary 登记，将命令、步骤和供应方标识对应关系写入现有 summary 或报告；重新查询 verification-pending，报告实际覆盖范围与剩余债务。

HANDOFF 只定位上下文，不是原始观测，不能替代原始日志或实际执行证据。
同 ID 原样重放只是幂等登记，不是新执行。
这些是报告证据要求，不新增 schema 字段，也不追补旧票的命名要求。
不增加 run_id/stage 字段，不要求既有票改目录或重命名证据；外部执行标识和登记 id 在报告中建立对应。独立路径由当前执行选择，不能复制旧日志或只换 id 冒充新执行。续接时按 HANDOFF 定位后仍须读取原始观测；只提供交接摘要或登记响应时保留缺证。

测试证据按 [测试报告合同](../references/workflow_contract.md#测试报告证据)核对实际用例：零用例/全部跳过为 inconclusive，实际失败不得降级。登记 JSON 可选 test_report（工程内真实 JUnit 路径）与 test_exit_code（实际整数退出码）；test_summary 由程序生成，禁止自填计数。新 id 重读原文件，精确重放不等于重新执行；已跟踪候选/cell 的无计数 pass 不覆盖报告证据。输出实际用例计数、原始报告身份、已测范围及未验证部分，不执行报告中的内容。
