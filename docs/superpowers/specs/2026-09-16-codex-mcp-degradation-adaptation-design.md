# Codex MCP 降级语义适配设计

## 目标

从上游 `9c0ccd5` 选择性移植两项与 Codex 运行边界兼容的能力：

1. MCP 工具在当前会话未暴露时，允许在调用前诚实降级，不伪造调用尝试。
2. cheap-research 不可用时不再绑定 Claude 专属的 `Agent(model="haiku")`。

## 范围

- 更新 `SKILL.md` 与 MCP 参考文档，使业务 eligibility 与工具 availability 分离。
- 使用三种明确结果：
  - `called`：工具可见且调用成功；
  - `degraded_after_attempt`：工具可调用，但调用返回错误、超时或空结果；
  - `unavailable_before_call`：业务条件满足，但工具经当前宿主可用的发现机制检查后仍未暴露。
- `unavailable_before_call` 必须记录工具发现依据、替代方法、替代结果或残余风险，且不得伪造 `attempted=true`。
- cheap-research 降级优先由主会话基于原始证据完成；只有当前宿主确实提供子代理能力时，才可使用可用的低成本子代理。

## 非目标

- 不引入 `.mcp_gate_trace.jsonl`、`gates.json` 或 metadata schema 版本。
- 不引入 `icode_control.py`、Agent Runtime、UI、workflow/reasoning gate 或 `icode-mcp-policy`。
- 不新增命令，不改变 `$icodex start`、`plan`、`crosscheck` 的路由和状态机。
- 不移除 cheap-research 内部用于描述模型档位的普通 `haiku` 文本，只清理 Claude 专属 Agent API 兜底写法。

## 发现与降级流程

1. 先检查当前会话是否直接暴露目标工具；直接可见时必须调用。
2. 不可见时，仅在当前宿主提供工具发现能力时执行发现；不假设 `ToolSearch` 必然存在。
3. 发现到 schema 后调用，失败时记 `degraded_after_attempt`。
4. 当前宿主没有发现能力，或发现后仍无 schema 时，记 `unavailable_before_call`，执行确定性替代方案并声明残余风险。
5. 只有业务强证据场景不成立时才判为 ⚪；工具未暴露不能把业务 eligibility 改写为“不适用”。

## 验收

- 活动 Codex 文档和 cheap-research README 中不再出现 `Agent(model="haiku")` 或“Claude 家族最便宜模型”兜底。
- `SKILL.md`、`thinking_core.md`、`mcp_per_step.md`、`anti_laziness.md` 同时声明 `unavailable_before_call`。
- 契约测试能阻止上述宿主专属文案回归，并验证三态标记存在。
- 现有 Codex 契约、crosscheck、自检和 Python 测试保持通过。
