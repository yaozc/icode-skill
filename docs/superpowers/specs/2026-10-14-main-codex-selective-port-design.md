# main 修复向 Codex 的选择性移植

## 目标与边界

将上游 `main@5be9dee` 中对现有 Codex 工作流有用的修复导入 `codex@b8ef430`，保留 `.ai/icode`、`~/.codex/icode_data`、`icode_state.py`、start/plan 路由和 crosscheck 零回写合同。

整分支合并会引入另一套控制面和安装路径；本次采用按行为移植，避免替换 Codex 已有状态机。新增 Agent/UI、发布站点、技能包、多宿主安装器及工单命令需要单独设计，不作为兼容修复导入。

## 导入项

| 上游提交 | Codex 适配 |
|---|---|
| `d328f66` | 根目录种子使用文件 scope，避免默认 `.` 枚举整个大仓；子目录种子仍用父目录，保留已有同名头文件/测试联审与漂移检测。显式 scope 优先，显式 related 始终必审。 |
| `21566a5`、`d497b45`、`29634bc` | Git 匿名管道在 Windows 使用有界线程队列；范围路径保持 POSIX 格式；拒绝 rooted 路径；crosscheck 使用平台文件锁、Windows 跳过目录 fsync，原生 CLI 输出 UTF-8。 |
| `7a6143e` 的保护原则 | 保持单 Codex rsync 同步；排除源端工单、测试缓存和私密资料，保留目标端 MCP 配置、venv、Git 元数据；修复现有 `--no-delete` 参数。macOS openrsync 的目录合并过滤会删除目标配置，改用顶层 `--exclude-from` 向两端传递保护规则。 |

不导入 `d328f66` 的覆盖债务通过门禁放宽：已阅读部分文件不能证明遗漏文件已审完，Codex 非 blocked 结论仍要求完整覆盖。旧轮恢复沿用冻结的原 scope，不重写历史声明。

## 验收

- 根目录种子遇到超过 200 个无关文件仍可生成完整的声明范围；显式 `--scope .` 继续记录预算债务，不能通过 freeze。
- 同名子目录关联文件漂移、目标身份、冻结篡改及自身输出隔离回归继续通过。
- 管道的正常输出、超限、超时和非零退出均受限；锁竞争、进入失败和退出失败均正确关闭资源。
- CLI 在非 UTF-8 stdout 下仍输出合法 UTF-8 JSON；导入模块不改宿主 stdout。
- 同步 dry-run 无写入，apply 更新有效源码但不覆盖目标 MCP 运行时，`--no-delete` 保留目标独有文件。
- 全量 Python 测试、Codex lint 与仓库已有 shell 契约通过；Windows 实机运行只能在 Windows 环境另行验证。
