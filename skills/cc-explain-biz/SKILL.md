---
name: cc-explain-biz
description: 仅手动触发。
disable-model-invocation: true
---
# explain-biz — 业务考古

把一个业务名，变成一份程序员+产品都能看懂的全景讲解。专治"AI 讲业务又浅又片面"。

## 为什么需要它

代码只告诉你 **WHAT**，不告诉你 **WHY**；业务意图散落在 PRD、ticket、人脑里。默认 AI 回答业务浅，是因为：读两层就停、只看一个入口、不追数据流、不区分规则与边界、不挖历史。

深度不靠"更努力地读"，靠三条纪律：

1. **遍历纪律** —— 沿调用链/数据流追到叶子，不半途停。调用层级(call hierarchy)是深度引擎，grep 做不到。
2. **多 facet 抽取** —— 一个业务有多个面（数据模型 / 配置流 / 运行流 / 演进史），分头探再合并，避免单线漏面。
3. **诚实标注** —— 没探明的列进"未解之谜"，推断的标「推断」，每条结论带 `file:line`。编造比漏掉更糟。

## 总体流程

```
Step 0 摸点(scout)  →  Step 1 切 facet  →  Step 2 并行派探子  →  Step 3 合成 12 段讲解
   (你亲自做)            (你判断)            (Explore 子代理)        (你综合+对账+标盲区)
```

先亲自摸清"这业务住在哪几个包"，再按面切分派子代理深挖，最后你来综合成文。**不要一上来就派子代理**——先 scout 才知道该切几个 facet、每个该给哪些文件。

---

## Step 0 — 摸点(scout)，亲自做

目标：定位业务落在哪些模块/包，拿到入口线索。**先读项目的模块地图**（根 `CLAUDE.md` 或各模块 `CLAUDE.md`），理解依赖方向，再定位。

工具优先级：**优先 IntelliJ MCP 语义工具**（区分注释/字符串/同名符号，比 grep 准）。多模块项目 `ide_*` 工具需带 `project_path`（子模块绝对路径）；报 `multiple_projects_open` 时它会列出所有可选路径，挑对应模块再调。

| 找什么 | 工具 |
|---|---|
| 按概念名找类 | `ide_find_class`（驼峰/子串匹配，如 `CustomAgent`、`AiAgent`） |
| 中文业务词定位 | `ide_search_text`（`context: strings` 找 UI 文案/枚举名，`comments` 找注释） |
| 找符号/方法/字段 | `ide_find_symbol` |
| 找文件 | `ide_find_file` |

回退到 `grep`/`Read`/`Bash` 仅当：MCP 没连、目标在索引外（`.sh`/日志/`pom.xml`/`.md`/配置/迁移 SQL）、或 MCP 返回空但确信存在。

scout 产出（你自己心里有数即可）：业务横跨哪几个模块、各模块里的核心包路径、几个明显入口类。据此决定切几个 facet。

## Step 1 — 切 facet

按业务的"面"切，不按模块切。**默认四面，按实际增删**：

| facet | 探什么 | 典型模块 |
|---|---|---|
| **数据模型** | 实体/表/字段/枚举/实体关系/状态机种子 | entity + valueobject |
| **配置·写入流（产品视角）** | 用户/运营怎么配置管理它：入口API、AppService、DTO、业务规则、审计日志、生命周期状态机 | web / backend-web |
| **运行·读取流** | 运行时怎么执行：从入口追调用链到叶子、端到端路径、外部调用 | agent / updater / datasync |
| **演进WHY** | git log + ticket + PRD + 注释 → 业务目标、痛点、设计意图、术语、历史 | git/docs（无关代码） |

裁剪：纯运行时特征（无配置界面）砍掉配置面；纯配置项（无运行逻辑）砍掉运行面；小特征可合并成 2 个 facet 或干脆不派子代理、你自己串行七步走完。**facet 数 = 业务复杂度**，别为小事开六个探子。

## Step 2 — 并行派探子

每个 facet 派一个 `Explore` 子代理（`subagent_type: "Explore"`），**同一条消息里一次性全部派出**以并行。

每个探子 prompt 必须含：

1. **背景一句话** + 它负责哪个 facet。
2. **绝对工作目录**，并交代 IntelliJ MCP 用法："先 ToolSearch 加载 `mcp__intellij-index__ide_read_file`/`ide_file_structure`/`ide_call_hierarchy`/`ide_find_references` 等；读某模块文件 `project_path` 用该子模块绝对路径；也可用 `Read` 工具读绝对路径。"
3. **scout 找到的具体文件/包清单** —— 给路径，省得它重新摸。
4. **该 facet 要执行的七步**（见下）中相关的几步。
5. **结构化返回规格**：要哪些表/图、每条带 `file:line`、"只读不改、返回纯数据、不寒暄、没挖到的诚实标注"。

### 每个探子遵循的七步遍历

| 步 | 做什么 | 工具 |
|---|---|---|
| 1 找入口 | 业务从哪进代码：Controller / MQ listener / 定时 job / Dubbo / 消费者 | `ide_search_text` `ide_find_class` `ide_file_structure` |
| 2 追全链路 | 入口→...→叶子，**跨模块**调用链追到底（这步决定深度） | `ide_call_hierarchy`(callers/callees) `ide_find_references` |
| 3 抽数据模型 | 相关实体/DO、表名(@Table)、字段→业务含义、枚举全值 | `ide_find_class` `ide_file_structure` `ide_read_file` |
| 4 挖业务规则 | domainservice/bo/service 里的 if/switch/校验/默认值/边界/配额/权限 = 规则本体 | 读源码 |
| 5 重建状态机 | status 枚举 + 流转点（谁把状态从 A 改到 B、前置条件） | `ide_find_references`(枚举值) |
| 6 抓 WHY | commit ticket、PRD、长中文注释、类头注释 —— 代码给不出的意图 | `git log -- <path>` `Read` docs |
| 7 标盲区 | 没探明的诚实列出，不编 | — |

数据模型/配置/运行 facet 重点在 1-5；WHY facet 重点在 6 + 术语。**第 2 步用 `call_hierarchy` 追到叶子才算"深"**——这是和浅层回答的分水岭。

派探子的范例 prompt 见 `references/subagent-prompts.md`。

## Step 3 — 合成 12 段讲解

收齐探子结果后，**你**综合成文（不是粘贴拼接）：对账冲突、去重、补缺、标盲区。严格按 12 段模板（详解+mermaid骨架见 `references/template.md`）：

```
1. 一句话定义 + 业务目标   产品视角：谁用、为啥、解决啥；附演进一句话
2. 术语表                 中文 | 代码标识 | 含义
3. 角色 & 场景            主角色 + 主流程/异常场景
4. 端到端流程图           mermaid flowchart，关键节点标 file:line
5. 数据模型               mermaid erDiagram + 实体职责表(关键字段→含义) + 关键枚举
6. 状态机                 mermaid stateDiagram-v2 + 关键闸门(前置条件)
7. 核心业务规则           规则 | 条件 | 位置(file:line)；含配额/校验/权限/边界
8. 触发入口               配置态 API 清单 + 运行态入口
9. 关键代码路径           入口→...→叶子 一行串起，带 file:line
10. 依赖 & 外部交互        外部服务契约、数据源、扩展点(plugin)、异步/超时
11. 边界 / 异常 / 反例     情况 | 行为（超时/失败/越权/非法态）
12. 未解之谜              代码不可见的、纯推断的、需人确认的，逐条标注
```

裁剪：小业务可省 5/6 的图只留表，或合并 8/9。但 **1、2、4、7、12 永远保留**——定义、术语、主流程、规则、盲区是"不浅"的最低保证。

## 质量红线（自检）

- 每条业务结论可点击到 `file:line`？没有就是浮在表面。
- 调用链追到叶子了，还是停在中间层？
- 区分了"验证事实"和「推断」？
- 盲区诚实列出，没假装全懂？
- 产品视角和程序员视角都有，不是纯类图堆砌？

## 范例

`references/example.md` 是一次真实实跑（metis「自定义AIAgent」）的完整产出，照着对齐深度与结构。
