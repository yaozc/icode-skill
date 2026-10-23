# Codex 与 external-review 第二批选择性移植

用户已接受本轮 fork-sync-review 的建议。本次在两个现有 worktree 实施，不提交、推送或同步安装副本；main 保持 c07d4b0。保留 external-review 原有 .DS_Store。

## 范围与设计

- Codex API/ABI：只对实际受影响的公共库边界启用；区分声明、符号、布局/所有权、外部编译链接和旧二进制运行，挂接现有 review/deepcheck/audit。不新增 metadata 字段或技能分发层。
- Crosscheck：`start --max-files N` 冻结正整数文件预算，恢复和新轮默认继承已保存预算；旧轮无新增字段时从既有工作清单读取。`inspection --phase read --paths-json '<数组>'` 在原锁内整批预验并一次原子保存，仍支持原单 path 接口。数组限定 1–256 个唯一规范相对路径、64KiB；可选 request-id 绑定本轮批次成员及源码哈希，精确重放不抹后续进度，同 ID 不得换成员。声明登记不证明实际阅读；不放宽覆盖债务或零回写门禁。
- 冗余 related：仅在新鲜重建证明文件集合、单元、哈希、检查规则、scope/基线/预算和排除完全等价时，接受同轮重复声明；保留原声明和进度。新消费者、未知或截断覆盖不复用；新轮仍清空阅读和批次回执。
- MCP：安装/卸载共用真实输出探针解析 Python argv，用户显式单可执行文件覆盖优先；Windows Node transport 接入真实 Codex adapter，选中的 npm 服务才解析所需运行时，保留非 Windows 行为、dry-run、配置冲突拒绝和本地配置保护。
- 外审：只增加现有合同/报告中的授权来源、无序成员与有序历史、原始预算与派生内存/软时限、平台观测边界。当前 schema1 不要求上游 stage/provider 字段，不引入执行目标代码或回写能力。

## 实施与验证

- [x] API/ABI 规则、调用点及文档合同回归。
- [x] MCP Python/Node 适配与失败/覆盖/平台模拟回归。
- [x] 文件预算的恢复、旧轮、中断、新轮、错误输入和清单漂移回归。
- [x] 批量 Read 的逐项预验、幂等、同键冲突、原子失败、冻结/跨轮与目标零回写回归。
- [x] related 冗余等价、范围扩张与未读债务回归。
- [x] 外审规则变异、报告接口、历史兼容与 CLI 只读回归。
- [x] 合并审查并修复有效发现；保存执行前源码基线和真实 stdout/stderr/退出码；运行 Codex 全部 tests、相关 shell 合同、Codex lint，以及外审 unittest/lint。

验证环境以当前 macOS 为准；Windows 模拟结果不能冒充 Windows 原生通过。文档 linter 只证明静态规则存在，不认证 AI 已实际正确执行审查。

## 本轮结果

Codex 全部 279 项 pytest、external-review 全部 31 项 unittest 通过；两个文档 linter、MCP/crosscheck/inspection shell 检查及 diff 检查通过。独立审查发现并修复源码漂移新轮预算、清单发布中断和 Python 探针挂起三个边界。清单发布前中断需重传原显式范围参数，探针仅保证约 3 秒截止和直接子进程回收；Windows 原生运行仍未验证。

执行证据保存在 `/private/tmp/icode-selective-port-20261022-evidence/`，包含执行前后源码哈希、真实 JUnit、原始输出和退出码；执行无关的本计划复选框不参与源码指纹。两个目标分支未暂存/提交/推送，main 与既有 `.DS_Store` 未改变。
