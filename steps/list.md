# 步骤 list — 跨工程工单查找（纯查询）

> **Codex 持久化前置**：执行本步骤前必须完整读取 [references/codex_runtime.md](../references/codex_runtime.md)；路径、状态、锁、合并读取、迁移和 artifact_map 与旧文字冲突时以该文件和 `~/.codex/skills/icodex/tools/icode_state.py` 为准。

**命令**:
- `$icodex list [关键词] [--project <path>] [--status <status>] [--since <duration>] [--limit N] [--no-color] [--include-stale]`

**产出**: 默认无（只读，控制台输出表格）；不写 metadata、不写 index.json、不写工程内任何文件
**会话**: 主会话

## 定位

解决"工单目录 `icode_N` 分散在多工程，找历史工单要打开很多工程一个个点开"的痛点。`$icodex status` 模式一只看当前工程最近一个工单，**`$icodex list` 是它的跨工程增强版**：从全局索引 `~/.codex/icode_data/index.json` 的 `tickets` 数组全量读取，按需过滤+排序+格式化输出。

**与 `$icodex status` 职责分离**：
- `status`：当前工程最近一个工单的**详细状态**（含 mode/verdict/下一步推断/索引概览）
- `list`：全索引的**鸟瞰视图**（一行一个工单，便于浏览+筛选）

## 关键约定（必读）

- **只读**：不写 metadata、不写 index.json、不写工程内任何文件。**禁止**任何 `--write` 之类的破坏性扩展
- **不创建工单目录**：与 `$icodex run` / `$icodex init` / `$icodex log` 区别（那些是"创建/复用"，list 是"查找"）
- **不参与步骤1~6 推进**：与 `$icodex plan` / `$icodex review` / `$icodex merge` 等区别（那些是"推进流程"，list 是"查询"）
- **不修改全局索引**：与 `--verdict` / `--scan-verdict` 区别（那些是"标注"，list 是"只读浏览"）

## 执行步骤

读取动作先运行 `python3 ~/.codex/skills/icodex/tools/icode_state.py merged-index --codex-root ~/.codex/icode_data --claude-root ~/.claude/icode_data`，后续过滤、排序与格式化全部基于该 JSON。不得只在 Codex index 不存在时整体回退；`source=claude` 和 `legacy:*` 条目保持只读。

1. **解析命令行参数**（顺序无关）：
   - 位置参数：可选关键词（无则不过滤）
   - `--project <path>`：按 `project_path` 过滤（支持 basename 匹配，见下文）
   - `--status <status>`：按 `status` 过滤（精确匹配，支持 `,` 分隔多值如 `plan_done,code_done`）
   - `--since <duration>`：按 `last_used_at` 过滤（支持 `24h` / `7d` / `30d` / `1y`）
   - `--limit N`：限制条数（默认 50，0 = 不限）
   - `--no-color`：禁用 ANSI 颜色（管道/重定向场景）
   - `--include-stale`：包含 stale 工单（默认排除）
2. **读取全局索引**：`json.load` 全量解析上述合并视图的 `tickets` 数组（**禁止按行截断**）
3. **空索引处理**：
   - 文件不存在 → 提示"无全局索引，请先跑 `$icodex run` 或 `$icodex init` 创建工单"后退出
   - `tickets=[]` → 提示"无工单记录"后退出
4. **逐条过滤**（AND 关系，所有条件同时满足才保留）：
   - **关键词过滤**：在 `ticket_id` / `project_path` / `requirement_summary` / `keywords` 中大小写不敏感扫子串（关键词用空格分词后所有 token 都需命中，AND 关系）
   - **`--project` 过滤**：
     - 若 value 是绝对路径 → 精确匹配 `project_path`
     - 若 value 是字符串（无 `/` 开头）→ 在 `project_path` 中按 basename 模糊匹配（如 `--project <品类代号>` 匹配 `.../<品类代号>/...`）
   - **`--status` 过滤**：精确匹配 `status` 字段；多值用 `,` 分隔（OR 关系）
   - **`--since` 过滤**：
     - `24h` / `7d` / `30d` / `1y` 等单位：`now - duration < last_used_at`（含未使用工单 `last_used_at=created_at`）
     - 无单位数字视为天数
   - **stale 默认排除**（除非 `--include-stale`）：`stale=true` 的工单不显示
5. **排序**（默认 `last_used_at` 倒序，最新在前）：
   - 同样时间按 `ticket_id` 升序兜底（稳定排序）
6. **`--limit` 截断**（默认 50，0 = 不限；超出条数时末尾标注 `(还有 N 条未显示，加 --limit N 提高或加关键词缩小范围)`）
7. **格式化输出**（表格 + ANSI 颜色，除非 `--no-color`）：

   | 字段 | 来源 | 宽度 | 颜色规则 |
   |------|------|------|---------|
   | TICKET-ID | `ticket_id` | 自适应（最长对齐） | 基础 |
   | PROJECT | `project_path` 智能截断（见下） | 60 字符 | 基础 |
   | STATUS | `status` | 14 字符 | `completed` 灰 / 含 `in_progress` 黄 / 其他 绿 |
   | WORKLOAD | `workload_estimate` | 7 字符 | `large` 粗体红 / `medium` 黄 / `small` 灰 / 缺失 `-` |
   | LAST-USED | `last_used_at` | 16 字符（`YYYY-MM-DD HH:MM`） | 基础 |
   | SCHEMA | `template_version` | 9 字符（`v1.1`/`v0`/`unknown`/`-`） | `v1.1+` 绿 / `v0` 黄 / `unknown` 灰 / 缺失 `-` |
   | VERDICT | `verdict` | 11 字符 | `disproved` 红 / `superseded` 蓝 / `verified` 绿 / `unknown` 灰 |
   | SUMMARY | `requirement_summary` | 60 字符截断（超长加 `…`） | 基础 |

   **PROJECT 列智能截断算法**（修默认 30 字符截断导致 path 不可见的痛点）：

   1. **完整路径 ≤ 60 字符**：原样显示
   2. **完整路径 > 60 字符**：按以下优先级智能截断
      - **优先一**：`$HOME` 替换为 `~`（如 `/home/user/myproject` → `~/myproject`），剩余若仍超 60 字符进行下一级
      - **优先二**：保留 basename + 关键父路径段（保留 basename 和最后 N 级父目录，体现工程身份而非纯路径）
      - **最终兜底**：从路径尾部取 60 字符，前缀加 `…`（如 `…ng-project-name/subdir/.ai/icode`），保留可点击的尾部信息
   3. **截断示例**：
      - `/home/user/myproject` → `~/myproject`（19 字符）
      - `/home/user/very-long-namespace-name/myproject` → `~/very-long-namespace-name/myproject`（41 字符，原样）
      - `/home/user/very-long-namespace-name/myproject/.ai/icode` → `~/…/.ai/icode/`（智能缩中段）
      - `/home/user/very-long-namespace-name/myproject/.ai/icode/icode_3` → `~/<truncated header>…myproject/.ai/icode_3`（保留尾段）
   4. **绝对优先**：保留的最后一段必须是工单目录名（`.ai/icode/icode_N`），让用户能直接 `cd` 进去

   **stale 工单**（如 `--include-stale` 显式包含）：`STATUS` 列前缀 `[stale] `，`SUMMARY` 后缀 ` [stale_reason: X]`

   **path_gone 工单**（工程已删）：`PROJECT` 列 `[path_gone]`，保留显示便于用户判断
8. **输出统计脚注**（表格下方）：
   ```
   共 N 条（过滤后）/ 全索引 M 条（stale K 条 / disproved L 条 / verified P 条）
   ```

## ANSI 颜色码（参考）

- 红（disproved / large workload）：`\033[31m`
- 绿（verified / 完成态）：`\033[32m`
- 黄（medium workload / in_progress）：`\033[33m`
- 蓝（superseded）：`\033[34m`
- 灰（completed / unknown / stale / small workload）：`\033[90m`
- 粗体（large workload 强调）：`\033[1m`
- 重置：`\033[0m`

**`--no-color` 模式**：所有颜色码替换为空字符串。**TTY 检测**：当 stdout 不是 TTY（如管道到 `less` / `grep` / 文件）时自动等价于 `--no-color`（防乱码）

## 边界处理

| 场景 | 行为 |
|------|------|
| 全局索引文件不存在 | 提示"无全局索引，请先跑 `$icodex run` 或 `$icodex init` 创建工单"后退出，不报错 |
| 索引为空（`tickets=[]`） | 提示"无工单记录"后退出 |
| 关键词无匹配 | 提示"无匹配工单（索引共 N 条，尝试其他关键词或去掉过滤条件）" |
| 旧 metadata 无 `workload_estimate` | WORKLOAD 列显示 `-`，不报错（向后兼容） |
| 旧 metadata 无 `template_version` | SCHEMA 列显示 `-`（与 WORKLOAD 兼容同形态），不报错 |
| `project_path` 已删（`stale_reason=path_gone`） | PROJECT 列显示 `[path_gone]`，默认排除（除非 `--include-stale`） |
| 字段格式异常（如 `last_used_at` 缺） | 退化为 `-`，不中断整行渲染 |
| `--limit` 截断 | 末尾标注 `(还有 N 条未显示...)` |
| TTY 检测 | `sys.stdout.isatty() == False` 时自动 `--no-color` |

## 反偷懒

- **禁止按行截断**：用 `json.load` 全量解析 `tickets` 数组（**前 50 行**仅适用于 project_docs 章节，不适用索引）
- **禁止写 metadata/index.json**：纯查询，无 `--write` 之类的破坏性扩展
- **禁止只列当前工程**：明确跨工程（从全索引读）
- **禁止硬编码时间**：用 `datetime.now()` 取真实当前时间（`--since` 过滤的基准）
- **禁止猜测字段值**：缺失字段退化为 `-`，不编造
- **禁止改 user 项目路径**：只读索引，不 `cd` / 不 `open`（"纯查询不跳转"原则）

## 与 `$icodex status` 的协作

- 用户从 `$icodex list` 看到感兴趣的 ticket_id → 用 `$icodex status --verdict {ticket_id} ...` 标注
- 用户从 `$icodex list` 看到要继续推进的工单 → 用对应工程的 `$icodex run` / `$icodex plan`（**仍需在工程目录下运行**，list 不支持跳转）
- 用户想批量扫证伪信号 → `$icodex status --scan-verdict`（跨工程批量治理）

## 性能

- 全索引 64 条工单实测 < 50ms（Python 解析 + 简单字符串过滤）
- 200 条上限（索引 LRU 淘汰 200 条，超过则按规则淘汰）
- 过滤+排序总耗时 < 100ms（无数据库，纯内存）
- 输出渲染：50 条表格 < 30ms

## 示例

```bash
# 列所有工单（默认 last_used_at 倒序，前 50 条）
$icodex list

# 关键词搜索（找含 "mcu" 的工单）
$icodex list mcu

# 按工程过滤（只显示 <品类代号> 相关的工单）
$icodex list --project <品类代号>

# 按状态过滤（只显示已完成工单）
$icodex list --status completed

# 组合过滤（<工程名> 工程下 plan_done 或 code_done 的工单，近 30 天用过）
$icodex list --project <工程名> --status plan_done,code_done --since 30d

# 禁用颜色（管道场景）
$icodex list --no-color | grep <品类代号>

# 不限条数
$icodex list --limit 0

# 包含 stale 工单（默认排除）
$icodex list --include-stale
```
## MCP 推荐

本步骤仅用 sequential-thinking 强制思考（见 [references/mcp_per_step.md](../references/mcp_per_step.md)「通用前置」段）。其他 5 个 MCP 本步骤不推荐。

**强制约束**：🟢/🟢*/⚪ 语义 + 双保险机制（执行步骤内嵌 + thinking_core gate）详见 [SKILL.md「MCP 调用覆盖强制化」](../SKILL.md) + [references/mcp_per_step.md「双保险机制」](../references/mcp_per_step.md)；本步骤表内的 🟢/🟢* 标注按上方真源判定。
