# MCP 工具集成与降级路径

> icode 工作流可调用 6 个 MCP（`$icodex install` 一键安装）。**用户可能不装全部**，每个 MCP 都是**可选 + 降级**的。
>
> 安装入口：`$icodex install`（详见 [steps/install.md](../steps/install.md)）
>
> 步骤 × MCP 推荐矩阵：[mcp_per_step.md](mcp_per_step.md)
>
> **二元化**：推荐级别为 🟢 必须调 / ⚪ 不必调（无 🟡），按 [mcp_per_step.md](mcp_per_step.md)「强证据场景判定」执行。本文档的「强证据 + 降级路径」适用，下文各 MCP 的「触发场景」即强证据场景。

## 判定 MCP 是否可用

本静态规则按 [静态 references 读取与复用合同](thinking_core.md#静态-references-读取与复用合同) 读取：首次完整实读正文并计算 SHA256；仅同绝对 skill 根、文件路径、SHA256 且完整正文仍在当前上下文时复用。压缩、丢失正文、换根或内容变化必须重读，确认区分实读与复用。业务源码实读、每轮判断和 Read/worklist 登记不得复用，MCP 适用性及可用性每步重新判断。

业务 eligibility 按触发场景判定 🟢/⚪，可用性按 [thinking_core.md](thinking_core.md) 第 0 判据单独判定。五层证据分别说明其观测对象，不能互相替代：

| 层 | 观测证据 | 可支持的结论 |
|---|---|---|
| 源码 | 仓库内有 server/工具实现 | 存在实现，不能证明已安装 |
| 安装 | 目标环境文件、依赖和解释器探针 | 已在该环境准备，不能证明已注册 |
| 注册 | `codex mcp list --json` 或配置段 | 宿主存在注册项，不能证明握手成功 |
| 握手 | 指定进程/连接的 initialize、tools/list 原始返回 | 该连接当时完成协议握手，不能证明当前会话已暴露工具 |
| 当前会话可用 | 当前工具列表直接可见完整 schema，或宿主现有发现能力取得 schema | 当前会话可以尝试调用；成功仍需实际返回 |

配置存在不等于当前会话可调用。源码、安装、注册、握手和当前会话可用不能混淆，也不是五种执行状态。前三层及独立探针的握手成功只作诊断；当前会话取得 schema 时必须实际调用，不能从配置猜测跳过。

- `called`：实际调用成功，保留返回证据。
- `degraded_after_attempt`：已实际调用，但错误、超时或空结果；记录真实返回，再用替代方法。
- `unavailable_before_call`：工具未直接暴露，宿主现有发现能力无命中或宿主没有发现能力；记录 `attempted=false`、发现依据、替代方法、替代结果/残余风险，不能伪造调用失败。

只有在不可见时才使用当前宿主真实提供的发现能力，不假设必有 ToolSearch。下文工具名描述调用目标，安装建议及配置项描述准备条件，均不构成本次会话的成功证据。合规降级不阻塞流程。

---

## 6 个 MCP 的强证据 + 降级路径

### ① sequential-thinking（**优先安装，支持合规降级**）

- **强证据**：`mcp__sequential-thinking__sequentialthinking`（至少 3 步）
- **降级**：`### 结构化思考` 文字块（每步骤强制思考不可省）
- **触发场景**：**所有步骤**（强制思考前置）
- **安装状态**：依当前目标环境探针确认，不预设已装或本会话可用

### ② vision-bridge（**推荐装，需配三件套**）

- **准备条件（诊断）**：vision-bridge 注册项 + `config.json` 三件套（base_url/api_key/model）；配置不能证明当前会话可用
- **调用证据**：当前会话取得 schema 后实际调用 `mcp__vision-bridge__analyze_media(media_path, prompt)`，按真实返回记录三态
- **降级**（发现不可用或实际调用失败，按上方三态记录）：AI 不替用户判断原生能力
  - 原生支不支持图片/视频 **视具体 session 模型而定**（Opus/Sonnet 一般支持，Haiku 可能部分支持）
  - **用户自己把握**原生能力是否够用；AI 不假装"可以原生处理"
  - 不报错、不阻塞
- **触发场景**：涉及图片/视频/UI 截图（用户主动提供时直接调）**或 TB 缺陷源拉取的附件含视频/图片**（`{ICODE_OUT_DIR}/tb_source/<ID>/` 下）—— vision-bridge 可用则主动调（视频先用 ffmpeg 本地提取关键帧省钱，详见 [steps/log.md](../steps/log.md)「附件分析（含本地路径 + TB 源）与 ffmpeg 抽帧」）；vision-bridge 不可用时仅提示附件清单不主动调（防纯文字模型报错）
- **安装状态**：目标环境现场核查；三件套是准备条件，调用成功以本次真实返回为准

### ③ memory（推荐）

- **强证据**：`mcp__memory__create_entities` / `mcp__memory__search_nodes` / `mcp__memory__read_graph`
- **降级**：本对话内手动维护笔记（`## 记忆` 段落），或写到 `~/.codex/icode_data/memory.md`
- **触发场景**：跨工单偏好（"用户偏好 NoSQL"）、项目特性（"用 gRPC v3"）
- **token 性价比**：中（需要工程化使用才收益大）

### ④ context7（推荐）

- **强证据**：`mcp__context7__resolve-library-id` + `mcp__context7__query-docs`
- **降级**：WebFetch `https://<library>.readthedocs.io` 或官方文档
- **触发场景**：步骤 0 init（库调研）、步骤 1 plan（API 核对）、步骤 4 code（实时查 API）
- **token 性价比**：高（解决训练数据过时问题）

### ⑤ playwright（仅前端项目）

- **强证据**：`mcp__playwright__browser_navigate` / `mcp__playwright__browser_take_screenshot` / `mcp__playwright__browser_click` / `mcp__playwright__browser_evaluate`
- **降级**：Bash + `curl <url>`（无 JS 渲染、不支持交互）
- **触发场景**：步骤 5 deepcheck E2E、步骤 6 audit UI 验证
- **⚠️ token 警告**：24 个工具 schema 永久加载，**非前端项目慎装**
- **仓库范围**：保留 playwright 集成；包名 `@playwright/mcp`，安装、注册、握手与会话暴露仍须分别核查

### ⑥ cheap-research（**可选 · 降本场景**）

- **准备条件（诊断）**：cheap-research 注册项 + `config.json` 三件套（base_url/api_key/model）；不能替代当前会话工具 schema
- **调用证据**：取得 schema 后实际调用 `mcp__cheap-research__summarize(text)` / `__retrieve_similar(query, candidates)` / `__fill_template(template, data)` / `__extract(text, schema)` / `__audit_facts(repo_path)` 等工具，按返回记录三态
- **降级**（发现不可用或实际调用失败，按上方三态记录）：主会话按原始证据完成；只有当前宿主确实提供子代理能力时，才使用可用的低成本子代理，不绑定具体 API 或模型名，不阻塞主流程
- **触发场景**：长上下文压缩（log / doc / init / deepcheck / review）、历史工单检索（init / plan / start / fast / log）、模板填充（readme / audit / list）、结构化提取（doc 99_code_facts_audit）、TB 评论预提取（log 阶段2，评论 ≥ 8 条时）、差异摘要（audit 计划vs代码）、远程 README 拉取（doc 模块文档参考输入）—— 23 个入选子任务（单闸门：价值 ≥ 3 ★ + 低风险）
- **不接管决策**：所有高风险子任务（3 质疑者对抗 / 架构决策 / 终审裁决 / 修复方案 / 用户对话）一律不交给 cheap-research
- **触发场景详见**：[mcp_per_step.md](mcp_per_step.md) 强证据场景表 + 14 工具入参/出参 schema（见 [mcp/cheap-research/server.py](../mcp/cheap-research/server.py)）
- **状态边界**：仓库工具、自检、已安装目录及本会话为不同证据对象；历史自检结论不能代替本次环境或调用证据

### ⑦ cheap-research 单跑：dedup 子阶段

- **复用 MCP**：⑥ cheap-research（`extract` 用于分类和分析重复）；枚举方式与覆盖判定见下文。
- **业务触发条件**：review/deepcheck 的适用范围内，可信枚举达到 50 个函数。工具可用性单独判断。
- **触发场景**：
  - **02_review §2.5.7（轻量 top 5）**：ripgrep 抽所有函数 → `mcp__cheap-research__extract`(haiku) 分类（wrapper object schema）→ 后处理映射到 25 类 → 取 top 5 类别逐类调高质量模型找重复
  - **05_deepcheck §9.4（逐类检查）**：抽取→分类→拆分→逐类找重复→报告。复用 §2 目录和分类前核对当前候选、范围和输入身份。
- **中间产物路径**：`{ICODE_OUT_DIR}/<ticket>/dedup/{catalog,categorized,duplicates/*.json}`
- **最终报告**：进 step 产物 .md（02_review.md §2.5.7 / 05_deepcheck.md §9.4）的 `## 语义重复检测报告` 段（HIGH/MEDIUM/LOW 三段 + top 5 重复函数对）
#### 语义去重覆盖规则

- 先明确当前候选、受影响仓库及文件和语言范围。优先用 `rg` 枚举并核对文件、定义位置和覆盖情况。`rg` 缺失、无匹配或失败时，可用适用语言的解析器（如 Python AST）或读取范围内文件来替代。记录实际方法、范围、结果和限制。
- 只有可信枚举才能判定低于阈值。完整覆盖适用范围且计数低于 50 时，记录理由后跳过。达到阈值后核对当前会话的工具可用性。若已核实至少 50 个定义但还有未枚举范围，继续处理已确认的范围。
- 枚举不完整或不可信时，记录未覆盖范围和原因，不能把未知计为零。检查读取错误、语言不支持、忽略规则、取样与截断（包括 `head` 限额），保留本阶段报告中的覆盖缺口。超 500 个已核实的函数时仍按既有规则分批。
- 工具不可用或调用失败时，记录实际核查范围和剩余覆盖缺口。按本节三态规则记录调用或发现证据。可基于原始代码人工核查关键候选，列出位置、比较依据和结果。零个可核查项时照实记录。有效结果中的 `duplicates: []` 仅说明该批已查未见重复。未查范围和失败批次均列入现有阶段报告，包括 review 的 top 5 范围之外未核查的内容。
- 仅当当前候选、范围与输入身份一致时复用目录或分类。核对当前文件身份及枚举/分类输入，任何不一致或缺证都重新核对受影响部分。历史工单保留原有记录，续跑按当前证据记录本轮范围。

- **已知限制**：
  - **cheap-research schema 不支持 `enum` 类型**——`{"enum": [...]}` 报 `'enum' is not valid under any of the given schemas`。改用 `string` + prompt 强约束
  - **cheap-research LLM 把 array-of-objects 退化为 single object**——多次确认，schema `{"type": "array", "items": {...}}` 时 LLM 仍返回单个 object。**必须用 wrapper object 模式** `{"results": [...]}` 规避
  - **cheap-research LLM 不严格遵守 25 类清单**——即使 prompt 强约束，LLM 仍返回"Number Parsing"/"Math"/"String Manipulation"等自由类别。**必须主代理在写入 categorized.json 前做后处理映射**（见 §2.5.7/§9.4 第 3 步映射表）
  - extract 返回 schema_validation_failed → 重试 1 次（自动改 instruction），仍失败标"分类降级"
- **类别清单（共 25 类）**：
  - 通用类 22：file-ops / string-utils / validation / error-handling / http-api / date-time / data-transform / database / logging / config / async-utils / testing / ui-helpers / crypto / provider-impl / tool-impl / event-handling / session-management / compaction / other（19）+ file-ops/string-utils 子类补 3 = 22
  - iCode 扩展 3 类（嵌入式场景）：**hardware-abstraction**（硬件抽象：传感器/GPIO/中断）/ **protocol-impl**（通信协议：MQTT/Modbus/CAN/串口）/ **build-system**（构建脚本：CMake/Make/Bazel）

---

## 工具命名约定

- 实际工具名格式：`mcp__<server-name>__<tool-name>`
- server-name 用 kebab-case（`sequential-thinking` / `vision-bridge` / `cheap-research`）
- tool-name 用 snake_case（`sequentialthinking` / `analyze_media` / `resolve-library-id` / `summarize`）
- 示例：
  - `mcp__sequential-thinking__sequentialthinking`
  - `mcp__vision-bridge__analyze_media`
  - `mcp__playwright__browser_navigate`
  - `mcp__cheap-research__summarize`

## AI 执行时的工作流

1. **本步骤开始前**：判定本步骤推荐的 MCP（见 [mcp_per_step.md](mcp_per_step.md)）是否可用
   - 先判断业务 🟢/⚪，再查当前会话工具列表：完整 schema 直接可见（含代理前缀）即调用；不可见时使用宿主现有发现能力，不能虚构 ToolSearch
   - 源码、安装、注册和握手仅按需诊断，不替代当前会话 schema 或实际返回
2. **🟢 且 schema 可用**：必须实际调用；成功记 called，错误/超时/空结果记 degraded_after_attempt 并使用降级路径
3. **🟢 且发现后仍无 schema 或宿主无发现能力**：记 unavailable_before_call、attempted=false、发现依据与替代结果/风险，再走降级路径；⚪ 无需调用声明
4. **不阻塞**：MCP 不可用不是错误，**降级操作完全是合规的**

---

## 安装建议

| 场景 | 推荐安装 |
|---|---|
| 全新 clone icode-skill | sequential-thinking（优先安装） + vision-bridge（推荐装，需配三件套） |
| 纯后端项目 | sequential-thinking + vision-bridge + context7 |
| 前端项目 | 上述 + playwright |
| 长期项目 | 上述 + memory（跨工单积累） |
| **降本场景** | 上述 + **cheap-research**（仅 23 个低风险子任务；3 质疑者对抗 / 架构决策 / 终审裁决 / 修复方案一律不走） |

完整安装：`$icodex install`（一键扫描 `mcp/` 目录里所有 `install.sh`）
