# 步骤 help — 命令帮助（只读）

> **Codex 持久化前置**：执行本步骤前必须完整读取 [references/codex_runtime.md](../references/codex_runtime.md)；路径、状态、锁、合并读取、迁移和 artifact_map 与旧文字冲突时以该文件和 `~/.codex/skills/icodex/tools/icode_state.py` 为准。

**命令**：`$icodex help`

只输出下列命令、模式区别和下一步示例；不得创建工单、metadata、索引或任何配置：

```text
$icodex <任务>                 Codex full mode：根因→计划→实现→自审→审计→验证
$icodex init [需求]            步骤0，需求初稿
$icodex log [日志/症状]        日志根因分析入口
$icodex plan [需求]            仅步骤1，完成后暂停
$icodex start [需求]           plan 的兼容别名，完成后暂停
$icodex review [N]             仅步骤2
$icodex merge                  仅步骤3
$icodex code                   仅步骤4
$icodex deepcheck              仅步骤5
$icodex audit                  仅步骤6
$icodex run [需求]             staged mode 自动串联步骤1→6
$icodex fast [需求]            精简 staged 全流程
$icodex patch [问题]           既有工单追加修改
$icodex doc [自然语言]         工程/模块知识库
$icodex limit [自然语言]       项目约束红线
$icodex readme                 交付报告与跨领域简报
$icodex status [选项]          状态、verdict 与产物校验
$icodex list [关键词]          跨工程工单查询
$icodex install [name]         安全注册 Codex MCP
```

明确说明：`start` 不会串联后续步骤；需要自动执行 1→6 时使用 `run`。外部独立终审由 `$icodex-review` 承担。
