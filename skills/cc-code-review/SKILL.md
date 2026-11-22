---
name: cc-code-review
description: 仅手动触发。
disable-model-invocation: true
---

# code-review

审 Metis 后端 **Java / Kotlin 代码与 DB 脚本**，四个维度**并发**排查，合并成一份按严重度排序的问题清单（正文 ≤15 条 + 附录）：

| 维度 | 挂载 skill | 找什么 |
|---|---|---|
| **正确性**（总起） | 无 | 逻辑错、空指针、并发、事务边界、边界条件、异常吞掉、SQL 注入、资源泄漏 |
| **测试规范** | `testing-guidelines` | 测试类型选错、命名、断言、Mock/Fake 误用、造数据绕业务入口、脚手架、时间/随机未冻结（Metis 测试是 Kotlin kotest `*Spec.kt`） |
| **领域规范** | `domain-layer-specification` | 聚合根/AppService/DmService/分层、api·internal 分包、api 签名参数约定（标识用 Scalar、UserId 首位 / Operator 末位）、乐观锁、领域事件——**仅新代码** |
| **DB 脚本规范** | `mysql-guidelines` + `liquibase-guidelines` + `clickhouse-guidelines` | Liquibase migration（changeset id、目录/文件命名、多表拆分、global_id_seq 位置）、MySQL DDL 与 ID 策略（`@Id/@GlobalGen/global_id_seq`、索引）、ClickHouse DDL（引擎、CODEC、LowCardinality、Nullable、分区/排序键） |

## 接受输入 / 触发

- 目标可以是：不给（默认审工作区改动）/ commit sha / **issue 号（如 `proj/jx/aikf#10446`）** / 文件路径 / 全限定 class·方法 / 包名。目标含糊无法定位时反问一次。
- 审后端 **Java、Kotlin 代码与 DB 脚本**（`.sql` / liquibase migration / `.java` `.kt`）。纯应用配置（yml/properties）、前端不审，如占比大提醒一次。

## Phase 0：定位要审的代码

先确定**审查范围 = 一组文件路径**，并判定属于哪种模式。这批文件清单是 Phase 1 所有 subagent 的共同输入，四维审的必须是**同一批代码**。

| 目标 | 取证命令 | 模式 |
|---|---|---|
| 未跟踪（新文件） | `git ls-files --others --exclude-standard` | **diff 模式**（整文件都是新增，按全新代码审） |
| 已修改（工作区） | `git diff` + `git diff --cached` | **diff 模式**（只审改动的行及其上下文） |
| 某 commit | `git show <sha>` / `git diff <sha>^ <sha>` | **diff 模式** |
| 某 issue（见下） | 定位该 issue 的 commit 范围后 `git diff <OLD>^..<TIP>` | **diff 模式** |
| 某文件 / class / 方法 | 直接 Read 定位（class·方法先 grep 到文件与行段） | **存量模式**（审整段现状，不限于最近改动） |
| 某包 | `git ls-files '<包路径>/*'` 列出，逐个读 | **存量模式** |

**按 issue 号定位 commit 范围**（不用 `git diff master...HEAD`）：

```bash
git log --grep='<iid>' --oneline             # 默认搜当前 HEAD 可达；commit 若在别的分支，末尾补分支名
```

拿到该 issue 最旧、最新两个 commit（记为 OLD、TIP），审查范围 = `git diff <OLD>^..<TIP>`。先跑 `--stat` 确认没掺别的 issue 的文件，再进 Phase 1。掺进无关 commit 时向用户确认边界。

**默认目标**：用户没给目标 → 审工作区改动（`git status` 看未跟踪+已修改）。

**两种模式的差别，务必传给 subagent**：
- **diff 模式**：审改动行 + 必要上下文，不挑没动过的老代码。
- **存量模式**：审整段代码现状。领域规范维度不起，除非用户明说这段是新代码。

Phase 0 结束时你手里应有：**确切 git range 字符串（如 `<OLD>^..<TIP>`）或文件清单 + 模式**。**别把 diff 全文读进你自己的 context**；只留 range/清单，diff 由各 subagent 自己跑。

## Phase 0.5：预扫分流——决定起哪些 subagent

扫一眼文件清单，按下表决定起哪些 subagent。

| subagent | 起的条件 |
|---|---|
| 正确性 | **总起** |
| 测试规范 | 清单里有测试文件（`src/test/` 下的 `*Spec.kt`（kotest）或 `*Test.java`） |
| 领域规范 | 清单里有**任何后端业务模块的新代码**（metis-core，或 web/updater/pda/backend-web 等 access 层）。存量模式默认不起 |
| DB 脚本规范 | 清单里有 `.sql`（liquibase）、`db.changelog` / migration `root.xml`，或改动了 JPA `@Entity` 主键 / 新增 `@Entity` |

没起的维度，在最终报告里标一句"未审（无相关改动）"。

## Phase 1：并发 subagent

**在同一条消息里用 Agent 工具一次性起齐**选中的 subagent（`subagent_type: general-purpose`）。传给每个 subagent 的是**同一个确切 git range**；**主 agent 自己不读 diff 全文**，取证一律交给 subagent。

各维度挂载 skill（填进模板的"加载 skill"处，主 agent 在 prompt 里指明，不让 subagent 猜）：

| 维度 | 挂载 skill |
|---|---|
| 正确性 | 无 |
| 测试规范 | `testing-guidelines` |
| 领域规范 | `domain-layer-specification`；除 metis-core 内部分层外，务必扫 web/updater/pda 等 access 层有没有混入本该在 core 的业务决策（状态机流转 / 业务校验 / 计算） |
| DB 脚本 | 按迁移脚本路径判库：`/clickhouse/migration/` → `clickhouse-guidelines`；`node`/`dts`/`dbmq` 的 `*/migration/`、backend-web 的 `db/migration/` → `mysql-guidelines`；两者都同时挂 `liquibase-guidelines`；JPA `@Entity` 主键改动 → `mysql-guidelines` |

每个 subagent 的 prompt 按这个模板（把 `{...}` 填实）：

```
你是 Metis 项目（Java 17 + Kotlin + Spring Boot）的代码审查员，只审【{维度名}】这一个维度。工作目录 {repo 根}。

审查范围（严格限定，不要越界审别的）：
- diff 模式 → 自己跑 `git diff {确切 range}` 取证
- 存量模式 → 读这些文件：{文件清单}

模式：{diff 模式：只审改动行及上下文；/ 存量模式：审整段现状}

【仅规范维度加这段】动手前先用 Skill 工具加载 `{guideline skill 名}`，
严格按它的规范逐条比对上面的代码，只报真正违背规范的地方。

聚焦：贫血数据类（DTO/Cmd/Query/DO/枚举）只快速扫命名与结构；
有实现逻辑的类（AppService/DmService/TxService/调度/converter/util、DDL 脚本）才深读。

要求：
- 每条问题必须能落到具体 file:line。
- 只报你有把握的真问题；拿不准是否违规、或规范对这段不适用（如 legacy 代码），就别报。最多报 8 条。
- 纯 JSON 返回（不要 markdown 包裹），引用原文 ≤3 行。

【仅正确性维度加这段】每条打严重度，判据：
- P0 阻断：会导致线上事故——数据错乱、资金/权限错误、必现空指针/死锁、安全漏洞（注入、越权）。
- P1 严重：明确的 bug，特定输入必错。
- P2 一般：次优实现，该改但不致命。
- P3 提示：nit、风格、可读性小瑕疵。
返回 JSON：
{"dimension":"正确性","findings":[
  {"severity":"P0|P1|P2|P3","file":"...","line":123,
   "title":"一句话","problem":"为什么是问题+触发场景","suggestion":"怎么改","evidence":"≤3行原文"}
]}

【仅规范维度加这段】不打严重度，只报事实：违背了哪条、违背得多明确。
rule 必须带规范文档里的规则 ID 或章节号（如 LOCK-01、MOD-02、§4.6），找不到 ID 的写条款标题。
certainty 取值：clear = 条款适用且代码明确违背；borderline = 条款适用但是否违背有争议。
条款对这段不适用（legacy、规范明说豁免）就不报。
返回 JSON：
{"dimension":"{维度名}","findings":[
  {"rule":"{guideline skill 名} · {规则 ID 或章节号} · {条款一句话}","certainty":"clear|borderline","file":"...","line":123,
   "title":"一句话","problem":"违背了什么、怎么违背的","suggestion":"怎么改","evidence":"≤3行原文"}
]}
```

## Phase 1.5：规范 finding 定级 + 合并去重

收齐 subagent 返回的 findings（subagent 返回里 JSON 前面可能夹着思考文字，认**末尾那个 JSON 对象**解析），你（主 agent）来归并：

**先给规范 finding 定级**（正确性维度已自带 severity，不动）：

| 规范 finding | 落级 |
|---|---|
| certainty=clear 且 rule 命中下表 | **P1** |
| certainty=clear，其余 | P2 |
| 纯命名、风格、可读性 | P3 |
| certainty=borderline | P3，标"待确认" |

**P1 条款**（只列规则 ID，条款内容以规范文档为准）：

| 规范 | 规则 |
|---|---|
| domain-layer-specification | LOCK-01 聚合乐观锁 |
| domain-layer-specification | MOD-02 模块外 import internal |
| table-id-guidelines | 新增 Entity 主键策略 |
| liquibase-guidelines | 历史脚本目录只读、logicalFilePath 不变 |
| clickhouse-guidelines | 高可用表复制引擎 |
| testing-guidelines | §4.6 Fake reset |
| testing-guidelines | §4.8 given / then 走业务入口 |

然后归并：

- **同一 file:line（或同一方法）被多维命中 → 合并成一条**，`维度` 字段列全（如 `领域规范 + 正确性`），严重度取**最高**的一档。
- **合并同类**：同一条规范在多处重复违背（如多个测试 Fake 未实现 reset、多张 CH 表缺 CODEC），合成一条并注明"另有多处"。
- 每条再过一遍自问：**"这是真问题，还是规范对这段本就不适用？"** 存量/legacy 代码被领域规范命中的，删掉。

## Phase 1.7：对抗性验证（剔除假阳性）

合并去重后，对候选里的 **P0/P1 每条并发派一个独立 subagent 去证伪**。假阳性的典型形态：触发场景走不到、规范对这段不适用、有意设计被当 bug。

- **验哪些**：合并后 **P0/P1 全验**；入选正文的 P2 只抽验 finder 自己标了"需团队确认"的；附录 P3 不验。P0/P1 为 0 → 跳过本阶段。
- **验证 subagent（`general-purpose`）prompt 要点**：
  - 给它这一条 finding：file:line + 声称的问题 + 触发场景 / 违背的规范条款。
  - **默认立场"这是假阳性"，任务是证伪**：读实际代码 + 上下文 + 调用链。正确性类——确认触发路径真能走到、没有别处已兜住（上游已校验、已有锁/事务）；规范类——加载 rule 字段里的 guideline skill，按规则 ID 找到条款原文，只回答两个问题：条款是否适用这段、代码是否真违背。不评严重度。
  - 证伪必须给**具体反证**（哪行兜住了 / 哪条规范不管这段）。
  - 正确性类返回 `{verdict: CONFIRMED | FALSE_POSITIVE | DOWNGRADE, newSeverity?, reason, evidence: "file:line"}`；规范类返回 `{verdict: CONFIRMED | FALSE_POSITIVE | BORDERLINE, reason, evidence: "file:line"}`。
- **主 agent 据 verdict 处理**：FALSE_POSITIVE 从正文删除（附录留一行"经核实排除：…"）；DOWNGRADE 改严重度并重排；BORDERLINE 按 Phase 1.5 定级表落 P3 标"待确认"；CONFIRMED 保留、报告里标 `✓已核实`。**verifier 与 finder 打架时看谁反证更具体**。

## Phase 2：排序 + 输出（正文 ≤15 条 + 附录）

按 P0 → P3 排序：

- **正文**：P0/P1 **全列**，再择优补 P2 到约 12–15 条。
- **附录**：其余 P2 与全部 P3 收进末尾"未展开项"，每条只给一行（`[维度] 一句话 · file:line`），不展开问题/建议。
- 一条 finding 只讲一件事。引原文 ≤3 行、准确不意译。file:line 要能一键跳。

### 输出模板

````markdown
# 代码审查报告：{审查范围一句话}

- 范围：{文件清单概述 / commit·issue / 包名}　模式：{diff / 存量}
- 维度：{✓ 已审 / — 未审(无相关改动)}　正确性 _ | 测试规范 _ | 领域规范 _ | DB脚本 _
- 总览：P0 {N} / P1 {N} / P2 {N} / P3 {N}（对抗验证排除 {K} 条假阳性）
- 结论：**{可合并 / 建议修复后再合 / 阻断合并}**

## Findings（P0 → P3）

> P0/P1 均已过对抗性验证，条目标 `✓已核实`；被证伪的不列入正文。

### [P0-01] {一句话标题}
- **位置**：`path/to/File.java:123` · `方法名()`
- **维度**：正确性 / 测试规范 / 领域规范 / DB脚本（多维命中列全）
- **问题**：{为什么是 bug / 违背了哪条规范、会怎样}
- **建议**：{怎么改，给到能落地}
  ```java
  {≤3 行关键原文或改法}
  ```

### [P1-01] …
### [P2-01] …

## 附录：未展开的次要项
- `[{维度}] {一句话} · {File}.java:{line}`
- …
````

**结论判定**（写报告头）：只看经 Phase 1.7 核实的 P0/P1。任一 P0 → **阻断合并**；任一 P1 → **建议修复后再合**；否则 → **可合并**。

## 不做的事

- **不改代码**。只出报告，用户决定怎么修。（用户明确说"直接改"再动手，按 P0→P1 顺序改，改完标"✅ 已改"。）
- **不审纯配置 / 前端**。应用 yml/properties、前端代码不归本 skill（DB 脚本 SQL/DDL 归 DB 维度审）。
- **不拿领域规范套 legacy 存量代码**。
- **不发明事实**。拿不准的标"待确认"，别替作者假设意图。
- **不刷数量**。四维加起来正文 5-15 条。

## 何时反问

- 目标含糊定位不到（"审一下那个方法"但没说哪个）→ 问清楚再动。
- issue/commit 范围掺进别的 feature（`--stat` 文件数远超预期）→ 向用户确认边界再审。
- 目标全是纯配置 / 前端，没有代码和 DB 脚本 → 提醒不适用。
- 范围过大（上百文件）→ 不反问；数百文件 → 问是否缩小或只审核心模块。
