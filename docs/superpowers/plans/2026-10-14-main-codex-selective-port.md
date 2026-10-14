# main 修复选择性移植实施计划

**Goal:** 在 codex 分支导入与既有功能兼容的 main 修复。

**Architecture:** 逐行为移植复评、Git 管道、文件锁与同步保护，不合并上游控制面。设计依据为同日期 selective-port 设计文档。

**Tech Stack:** Python 标准库、pytest、Bash、rsync、Git。

## 全局约束

- 工单、全局存储、状态机、CLI 路由及 MCP 注册保持 Codex 现有契约。
- 不改其它分支或实际全局技能安装；同步测试只使用临时目录。
- 原有子目录关联阅读与 incomplete fail-closed 语义保留。

## 任务

- [x] 建立基线：隔离 Python 3.12 环境运行 pytest 和 Codex lint。
- [x] 复评范围：修改 tools/icode_crosscheck.py，新增根文件大仓、显式范围债务及恢复不可改范围回归；更新 references/inspection_worklist.md。
- [x] 跨平台 I/O：移植 tools/inspection_worklist.py 的有界管道和 POSIX scope；移植 crosscheck 文件锁、fsync 与 UTF-8 CLI；新增超时、超限、锁资源释放及字节合同测试。
- [x] 同步保护：修复 scripts/sync-to-global.sh 的 --no-delete，更新 .gitignore；扩展 tests/test_sync_to_global.sh 验证工单/缓存排除、Git/MCP runtime 保留及 dry-run。
- [x] 运行全量 pytest、lint、全部 tests/test_*.sh；检查 diff 和源提交记录，补充验收结果。

## 验证命令

```bash
python -m pytest -q tests
python tools/lint_codex_contract.py .
for check in tests/test_*.sh; do bash "$check"; done
git diff --check
```

## 执行与验收记录

- 使用临时 Python 3.12.14 venv 和本机缓存中的 pytest 8.4.2，不安装工程运行时依赖，不修改全局技能。
- 修改前 128 项 Python 测试及 Codex lint 通过；新增回归复现旧实现的根目录全仓 scope、匿名管道缺失、Windows rooted 路径、锁资源、UTF-8 输出问题。
- 同步回归先复现 macOS 不支持 `rsync --no-delete`；移除该参数后继续暴露目标配置被删除的问题。四组临时目录对比确认 `:- .gitignore` 不保护 openrsync 接收端，`--exclude-from` 可同时排除源配置并保留目标配置。
- 修改后 `python -m pytest -q tests`：140 passed；Codex contract lint passed。
- 全部 6 个 `tests/test_*.sh` 通过：crosscheck contract/demo、inspection contract、Codex MCP installer、schema migration、sync-to-global。
- 真实独立进程验证 POSIX 锁互斥和持锁进程终止后的释放；Windows msvcrt、目录 fsync 跳过和匿名管道分支以模拟及真实本机管道验证。Windows 实机兼容性尚需 Windows 环境验证。
- README 验证入口改为 pytest，避免 unittest discovery 遗漏现有 pytest 函数测试。

后续移植继续按行为选择；不能仅凭补丁文本相近就覆盖宿主路径、放宽门禁或更换状态机。
