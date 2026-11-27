---
name: cc-epics
description: 以产品与用户视角将大需求拆解为 docs/epics/ 下的垂直 Story（prd.md、story-map.md、各 Story intent.md），并按 Story 滚动细化为用户可理解的行为规格 spec.md，衔接 /to-tickets 与 /implement-spec。
disable-model-invocation: true
---

# cc-epics

把跨多个 Story 的大需求拆成**产品、用户与研发都能看懂并拍板**的垂直 Story 交付蓝图，并按 Story 滚动细化行为规格。

**核心原则**：
- **纯产品与用户视角（What & Why，不写技术方案）**：全程使用业务语言、用户角色、场景与外部可见行为来讨论和撰写文档。**不讨论、不设计底层技术实现细节**（数据库/缓存选型、分布式锁、SDK 升级、类名、表结构、内部接口协议、测试缝等）；技术方案留到下游开发阶段（`/cc-design-proposal` 或 `/to-tickets` → `/implement-spec`）。
- **代码探查只核实产品现状**：读代码库仅用于确认影响产品口径或切片可行性的客观事实（如现网字数上限、页面已有入口/Tab、现有功能是否支持某业务能力、既有业务术语），不借此展开技术架构调研或实现方案讨论。
- **仓库即唯一真相源（SSoT）**：所有需求、Story 与规格正文只落在仓库 `docs/epics/` 下；远端 Issue 只保存摘要、状态与指向仓库文档的链接。
- **滚动波细化（Rolling Wave）**：立项时只为每个 Story 生成轻量 `intent.md`；真正轮到某个 Story 开工时，再细化该 Story 的 `spec.md`。

## 路由：识别入口模式

根据用户输入自动选择模式；若输入为空或指向不明，先反问一次再开工：

| 输入形态 | 模式 | 目标 |
|---|---|---|
| 新需求（一段话、草稿、Issue 链接/编号、现成 PRD 路径） | **模式 A：立项拆 Story** | 对齐业务口径，产出 `prd.md`、`story-map.md` 与各 Story `intent.md` |
| 已有 Story 的 `intent.md` 路径（推荐），或 Story 目录 / Epic + Story 编号 | **模式 B：滚动细化单 Story** | 将该 Story 细化为产品/用户可理解的行为规格 `spec.md`，更新状态并交接 `/to-tickets` |
| 已有 Epic 的 `story-map.md` 或 Epic 目录（未指定具体 Story） | **模式 C：前沿盘点与同步** | 展示当前可开工的 Story 前沿（frontier），供用户选择推进、更新状态或补建远端 Issue |

## 目录布局约定

默认落在 `docs/epics/YYYY-MM-<epic-slug>/`；若目标仓库的 `CLAUDE.md` / `AGENTS.md` 或用户显式指定了其他路径，优先遵循项目约定。

```text
docs/epics/YYYY-MM-<epic-slug>/
├── prd.md                  # 大需求背景、目标、非目标、核心旅程与全局业务规则
├── story-map.md            # 垂直切片清单、依赖 DAG、MVP 界线、状态表与 Issue 索引
└── stories/
    ├── 01-<story-slug>/
    │   ├── intent.md       # 立项时生成：最小可交付主干功能的目标、范围与验收边界
    │   └── spec.md         # 滚动细化：模式 B 推进本 Story 时生成（外部行为规格）
    └── 02-<story-slug>/
        └── intent.md
```

---

## 模式 A：立项拆 Story

开始本模式时，读取 [`references/epic-templates.md`](references/epic-templates.md) 获取业务体检清单、切片规则与各文件模板。

### A0. 读输入、轻核产品现状与规模分流

1. **读取输入**：若输入是 Issue 编号/URL，先按仓库 `docs/agents/issue-tracker.md`（如有）或 `gh`/`glab` 读全量正文与评论。
2. **轻量核实产品现状**：读取 `CLAUDE.md`/`AGENTS.md`、`GLOSSARY.md`（如有），仅针对输入中明确提及的现有页面入口、现网业务限制或复用能力做轻量核实，**不做深层代码实现与架构调研**。
3. **规模与雾度分流**（在建 `docs/epics/` 之前判定）：
   - **单 Story 可闭环** → 建议跳过 Epic，交接给 `/grill-me` → `/to-spec` → `/to-tickets`。
   - **业务目标极度模糊、前置未知决策成片（fog of war）** → 建议先用 `/wayfinder` 清雾，待方向收敛后再回 `/cc-epics`。
   - **多 Story 协同的大需求（或用户明确坚持建 Epic）** → 继续 A1。
   - *完成标准*：分流结论明确；若触发分流建议，等待用户确认「改走建议路径」或「坚持建 Epic」。

### A1. 对齐产品口径与业务范围 → 【Gate 1】

按输入完整度选一条路径进入（所有问题必须是**产品、业务规则或交付范围**问题，不问技术实现）：

- **标准路径**（口语描述、Issue 或粗糙草稿）：
  - 调用 `grilling`（按轮次问清业务目标、核心角色与旅程、非目标、关键业务规则与 MVP 范围）与 `domain-modeling`（对齐业务术语，实时维护 `GLOSSARY.md`）。
  - 交互形态拿不准时可调用 `prototype` 做轻量交互示意。
- **现成 PRD 快车道**（用户给出较完整的现成 PRD）：
  - 通读全文并对照 [`references/epic-templates.md`](references/epic-templates.md) 中的「现成 PRD 业务体检清单」，只揪出**影响产品行为或切片划分的问题**（现网产品口径冲突、规则前后矛盾、异常态缺失、MVP 范围归属）。
  - 跳过文中已写清的细节，仅针对上述产品/范围歧义做 1 轮精简 `grilling`；若无实质歧义，直接进入落盘确认。

落盘 `prd.md`（快车道若已有现成 PRD 文件，在 `prd.md` 头部链接原 PRD，正文提炼目标、非目标、核心旅程、全局规则与本次补充拍板的口径，不全文复制）。

- **【Gate 1 门禁】**：展示 `prd.md` 核心摘要与拍板口径，**停下来等待用户确认**，通过后再进入 A2。

### A2. 垂直切片与各 Story Intent → 【Gate 2】

基于已确认的 `prd.md`，按 [`references/epic-templates.md`](references/epic-templates.md) 的切片规则拆分 Story：

1. 每个 Story 必须是**用户可感知的垂直切片（Tracer Bullet）**，按端到端业务价值划分；**Story `01` 必须是最小可交付使用的主干功能**——即用户真实可用、可独立验收的最核心端到端主路径（非纯技术空架子），后续 Story 在此主干上叠加分支、规则与扩展能力。
2. 明确 Story 间的**业务依赖边（blocked-by）**与 **MVP 界线**（哪些 Story 属于 MVP，哪些放 Post-MVP）。
3. 落盘 `story-map.md`（所有 Story 初始状态均为 `intent`）及每个 Story 独立的 `stories/<NN>-<story-slug>/intent.md`。本步**只写 `intent.md`，不预写任何 `spec.md`**。

- **【Gate 2 门禁】**：用产品/用户语言展示 Story 清单、依赖 DAG、MVP 界线与 `01` 最小可交付主干功能，核对主干切法、粒度与优先级是否合理，**停下来等待用户确认**。

### A3. 可选：同步远端 Epic / Story 骨架 Issue

Gate 2 确认后，**主动询问用户**是否将 Epic 与 Story 骨架同步到远端 Issue Tracker（未经确认绝不写远端）：
- 用户选择**同步** → 读取 [`references/issue-sync.md`](references/issue-sync.md)，创建 **1 个 Epic Issue + N 个 Story 子 Issue**，两阶段连好 sub-issue 与 `blocked-by` 依赖边，并将真实 Issue 编号/链接回写到 `story-map.md` 与各 `intent.md`。
- 用户选择**暂不同步**（或仓库无远端 tracker）→ 保持纯本地模式，告知后续随时可通过模式 C 补建。

收尾时给出下一步指引：推荐从 Story `01`（最小可交付主干功能）开始，提示运行 `/cc-epics docs/epics/YYYY-MM-<epic-slug>/stories/01-<story-slug>/intent.md` 进入模式 B 细化。

---

## 模式 B：滚动细化单个 Story（`intent.md` → `spec.md`）

开始本模式时，读取 [`references/story-spec-template.md`](references/story-spec-template.md)。

### B1. 恢复产品上下文与前置检查

1. 读取该 Epic 的 `prd.md`、`story-map.md`、目标 Story 的 `intent.md` 以及仓库 `GLOSSARY.md`。
2. 检查该 Story 在 `story-map.md` 中的前置依赖：若存在未完成的阻塞 Story，先向用户显式提醒，确认是否继续细化。
3. 若前序 Story 已交付，轻量核实当前产品实际行为与既有术语，确保新 Story 与已有用户体验一致。

### B2. 细化产品行为与验收口径

调用 `grilling`（配合 `domain-modeling`）围绕本 Story 的**外部可见行为**做定向访谈，直到前沿清空：
- 用户操作路径、页面/入口表现与反馈文案；
- 业务规则、状态流转、权限与边界条件（空态、超限、重复操作、失败提示）；
- 可直接用于 QA/产品验收的端到端场景（Given / When / Then）。

需要验证交互形态时按需调用 `prototype`。**不讨论底层代码模块、表结构、锁机制或技术实现细节**。

### B3. 生成 `spec.md` 与更新状态

1. 按 [`references/story-spec-template.md`](references/story-spec-template.md) 落盘 `stories/<NN>-<story-slug>/spec.md`：
   - 顶部附 Epic / Intent / Story Issue 溯源指针；
   - 正文全部用产品与用户可理解的语言写清问题、方案、用户故事、业务行为规则、端到端验收场景与不做项。
2. 更新 `story-map.md` 中本 Story 的状态为 `spec-ready`，并补上 `spec.md` 链接。
3. 若细化过程调整了全局业务规则或与其他 Story 的边界，主动提示用户同步更新 `prd.md` 或受影响 Story 的 `intent.md`。

### B4. 下游交接（Handoff）

展示 `spec.md` 路径与核心摘要，按 [`references/story-spec-template.md`](references/story-spec-template.md) 末尾的交接格式输出下游命令：
1. 若本 Story 涉及复杂架构改造，可先运行 `/cc-design-proposal` 做技术设计；否则直接进入开发拆票；
2. 运行 `/to-tickets` 读取 `spec.md` 并结合代码库拆为开发 Ticket（有远端 Story Issue 时一并传入关联）；
3. 运行 `/implement-spec` 推进实现、TDD 与 code review；
4. 该 Story 交付后，运行 `/cc-epics docs/epics/YYYY-MM-<epic-slug>/story-map.md` 更新状态并领取下一个前沿 Story。

---

## 模式 C：前沿盘点与状态同步

当用户传入已有 Epic 的 `story-map.md` 或 Epic 目录（未指定具体 Story）时执行：

1. 读取 `story-map.md` 与各 `stories/<NN>-*/` 现状。
2. 若发现有 Story 已交付但状态表未更新，提议同步状态（`intent` → `spec-ready` → `in-progress` → `done`）。
3. 计算并列出当前**可开工前沿（Frontier）**：所有前置 `blocked-by` 均已 `done` 且自身尚未 `done` 的 Story。
4. 询问用户下一步操作：
   - 选一个前沿 Story 进入**模式 B** 细化 `spec.md`；
   - 调整 `story-map.md`（增删/重排 Story 或调整 MVP 界线）；
   - 补建/同步远端骨架 Issue（按需读取 [`references/issue-sync.md`](references/issue-sync.md)）。

---

## 技能编排速查

| 协作技能 | 触发方式 | 何时使用 |
|---|---|---|
| `grilling` | **直接调用** | A1 产品口径与范围对齐、B2 单 Story 行为与验收细节访谈（仅限产品/业务问题） |
| `domain-modeling` | **直接调用** | 统一业务术语并实时维护 `GLOSSARY.md`（不在本技能内写底层技术 ADR） |
| `prototype` | **直接调用** | 页面交互、状态展示或操作流模糊时做轻量可视化/交互原型 |
| `research` | **直接调用** | 仅用于核实外部平台业务规则或产品能力边界（如第三方开放能力限制） |
| `/wayfinder` | **交接给用户** | A0 判定业务方向雾度过高、无法直接拆交付 Story 时 |
| `/grill-me` → `/to-spec` | **交接给用户** | A0 判定单 Story 即可闭环、无需建 Epic 时 |
| `/cc-design-proposal` | **交接给用户** | B4 之后、开发前若需对复杂技术方案做专门设计评审时 |
| `/to-tickets` → `/implement-spec` | **交接给用户** | B4 单 Story `spec.md` 就绪后，进入研发阶段结合代码拆开发 Ticket 与编码实现 |
| `/setup-matt-pocock-skills` | **交接给用户** | 用户希望配置远端 tracker 但仓库尚无 `docs/agents/issue-tracker.md` 时 |

## 参考文档（按分支加载）

- [`references/epic-templates.md`](references/epic-templates.md) —— 模式 A 必读：现成 PRD 业务体检清单、SPIDR 垂直切片与主干强约束、`prd.md` / `story-map.md` / `intent.md` 模板。
- [`references/story-spec-template.md`](references/story-spec-template.md) —— 模式 B 必读：产品与用户可理解的 `spec.md` 行为规格模板、审查清单与下游交接格式。
- [`references/issue-sync.md`](references/issue-sync.md) —— 仅在模式 A3 / 模式 C 需要同步远端骨架 Issue 时读取：GitHub / GitLab 两阶段建单与依赖连边、Issue 摘要模板与本地降级规则。
