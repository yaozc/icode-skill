# 步骤 verify — 验证上下文、运行登记与债务查询

**命令**：`$icodex verify [--pending | --plan | --context | --record <JSON路径>]`
**范围**：既有工单，不创建工单；无参数默认 --pending。不参与1→6推进。

先读 [codex_runtime.md](../references/codex_runtime.md) 和 [workflow_contract.md](../references/workflow_contract.md)，通过 metadata/artifact_map 找当前工单。沿用安装 helper：

```bash
python3 ~/.codex/skills/icodex/tools/icode_state.py verification-pending --run-dir "${ICODE_OUT_DIR}"
python3 ~/.codex/skills/icodex/tools/icode_state.py verification-plan --run-dir "${ICODE_OUT_DIR}"
python3 ~/.codex/skills/icodex/tools/icode_state.py verification-context --run-dir "${ICODE_OUT_DIR}"
python3 ~/.codex/skills/icodex/tools/icode_state.py record-verification --run-dir "${ICODE_OUT_DIR}" --input-json <实际运行JSON>
```

--pending、--plan、--context 只读，不执行编译/部署/设备命令，不写工单、索引。--record 仅登记明确提供的真实运行证据，baseline 必须在执行前取得；不得把建议或模拟结果登记为 physical。实际外部操作只在用户授权范围内执行，查询请求不授权部署。

展示 implemented、delivery_verdict、blocking_reasons、pending 单元及缺证原因。real_env 或生命周期缺需求时先补合同，不把宿主测试成功宣传为全部验证成功。记录成功后重新查询当前债务，不以单次 pass 判断整体 verified。
