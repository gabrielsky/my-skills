---
name: cc-migrating-domain-persistence
description: >-
  Use when 用户给出一个（或几个）metis-entity 里的 JPA 实体，要评估把它及同领域实体、Dao、TxService 搬进 metis-core
  module/<域>/internal 的改造代价，或要实际执行这种搬家。 触发说法：实体搬家、entity 挪到领域里、dao 收进领域、领域内聚、持久化下沉到模块、 这个实体能不能搬、搬
  Xxx 代价多大、Xxx 和哪些实体是一个领域、XxxJpaConfiguration 怎么加。
disable-model-invocation: true
---

# 领域持久化搬家

入口是**用户给的实体**：先圈出同领域实体，再量这批实体的外溢，给出改造代价；用户拍板后才搬。
**核心原则：纯搬家——一域一提交，只动位置与 import，不改行为、不改类名、不顺手重构。**
目标只是"进领域目录"：不要求该域已有 Aggr / `api` 分包 / DmService；`module/<域>/` 不存在就新建目录。

**REQUIRED BACKGROUND:** `domain-layer-specification`（目标分包）· `git-conventional`（分支 / commit）。

## 1. 圈同领域实体

```bash
bash .claude/skills/migrating-domain-persistence/analyze-entity.sh <Entity>
```

`# siblings` 段（不给 `DOMAIN` 时才输出）列出疑似同域的实体与依据。依据是启发式，**逐个裁决后把结论（含排除理由）列给用户确认**，再进第 2 步：

| 依据 | 含义 | 裁决 |
|---|---|---|
| `结构` | 两个实体文件互相出现对方类名（内嵌 `List<另一个实体>`、继承 `XxxBase` / `XxxWithDeleted`） | 同域，必须一起搬。例外：被多个领域继承的公共基类（审计基类这类）不搬 |
| `同子包` | 同在 `entity/node/<子包>/` | 同域 |
| `前缀` | 类名前缀包含关系 | 大概率同域；读一眼表名与字段确认 |
| `BASE` / `COMMON(域:N)` | 公共基类 / 被 ≥3 个 core 领域引用 | 公共设施或别域的表，排除；除非 owner 判定指向本域 |
| `共用文件:N` | 有 N 个生产文件同时 import 两者 | **只是线索**。被很多领域共用的通用关联表是别的域或公共设施，排除；只有 owner 相同才算同域 |

owner 判定：**谁在写它**（哪个域的 TxService / Repository 在 `save` 它）。只读它的域是消费方，不因此把它圈进来。
脚本漏报的补法：按表名前缀、业务名到 `metis-entity/.../entity/` 再扫一眼；拿不准的用 `mcp__intellij-index__ide_find_references` 看写入方。

## 2. 量外溢，出代价报告

```bash
DOMAIN=<域> FILES=1 bash .claude/skills/migrating-domain-persistence/analyze-entity.sh <Entity> <同域实体...>
```

`# spillover` 段每个实体一行：verdict · `in`（`core/module/<域>/` 内引用文件数）· `out`（领域外生产代码引用文件数，已排除集中 Dao 与测试）· `entityCommits`（近 N 天实体被改次数，`DAYS=` 可调）· `otherDomains`（还有哪些 core 领域在引用）。`W` = 疑似写该实体的领域外文件数（`new` / `builder()` / 经同名 Dao·TxService 调 `save`·`update`·`delete`·`forceUpdate`；经别名 bean 写会漏，读方法名含 update/delete 会多报）。`FILES=1` 列出 `out` 文件并标 `W`，**标 W 的逐个打开确认**。`in` 只数直接 import 实体的域内文件，不代表域的大小。末尾 `# 域现有 api` 列出 owner 域已有的 api 方法，用来判断读方改走 api 还缺什么。`DOMAIN` 不给时取引用最多的 `core/module/<域>`；一个都没有说明要新建域，域名与用户商定。

| verdict | 含义 | 代价 |
|---|---|---|
| `GO` | 零外溢 | 低：直接搬 |
| `NARROW` | 有领域外引用，未命中否决项 | 逐个看 `out`：全是读 → 中：先单独一个提交把它们改走 owner 域 `api`（Query / Provider + Dto），再搬；有写 → 同 `BLOCK:web-write` |
| `BLOCK:backend-web` | 被 `metis-backend-web` 引用 | 不可搬：backend-web 不依赖 core，实体进 core 后它看不到 |
| `BLOCK:web-write` | metis-web 里有标 `W` 的文件（不论在哪个 `web/module/` 子包）；打开确认全是误报则降为 `NARROW` | 高：要先做"业务下沉"（web 的写逻辑收进 core 域），另立项写 spec |

`core/mysql/node/service/`、`core/mysql/node/dto/<域>/`、`core/mysql/node/converter/` 里该域专属的类虽然计入 `out`，但随域一起搬，不算外溢。

**按域下结论，最严的一行说了算**：不要只搬 `GO` 的那几个，域搬一半会让同一批类同时从新旧两处 import。

**代价报告固定形态**（回给用户，到此为止，不动代码）：

1. 同域实体清单：每个实体的圈入依据；被排除的候选与理由
2. 外溢表：每实体 verdict / in / out（按模块）/ 近期改动
3. 前置工作清单：每条写"哪个领域外文件、读还是写、要改成什么"——读 → 走哪个 api；写 → 哪段逻辑要下沉
4. 结论：整域代价档（低 / 中 / 高 / 不可搬）+ 建议的提交切分；`entityCommits>0` 时提示冲突风险与在改它的分支

**判"领域内"一律用 `/core/module/<域>/`。** 只写 `/module/<域>/` 会把 metis-web 的同名镜像包算成领域内，外溢被严重低估。自己写 grep / IDEA `paths` 过滤时同样适用。

## 3. 搬

worktree + 分支 `refactor/<域>领域内聚`（无 issue 时；有 issue 按 `git-conventional`）。

| 对象 | 从 | 到 |
|---|---|---|
| `@Entity`（含 `XxxBase` / `XxxWithDeleted`） | `metis-entity/.../entity/node/` | `module/<域>/internal/domain/model/` |
| `XxxDao` | `core/mysql/node/dao/` | `module/<域>/internal/mysql/` |
| 该域专属的集中 TxService / dto / converter | `core/mysql/node/service/` · `core/mysql/node/dto/<域>/` · `core/mysql/node/converter/` | `module/<域>/internal/` 对应子包 |
| 新建 `<Xxx>JpaConfiguration` | — | `module/<域>/`（模块根，照 `replystyle/AiAgentReplyStyleJpaConfiguration`） |

- Dao 不用改扫描配置：Repository 扫描已覆盖 `com.darcytech.metis.core.module`。实体**必须**有 `@EntityScan`，否则启动期 `Not a managed type`。一域一个配置类，指向 `domain/model` 包里任一实体即可覆盖整包；各域的 `@EntityScan` 是叠加关系：

```java
@Configuration(proxyBeanMethods = false)
@EntityScan(basePackageClasses = <Xxx>.class)
public class <Xxx>JpaConfiguration {
}
```
- 内嵌关系（实体里 `List<另一个实体>`）的一组实体必须一起搬。
- `XxxAggr` 已在 `internal/domain/` 且与同包其他类耦合时，留在原地；只有零成本时才顺手归位到 `domain/model/`。
- IDEA 已打开该 worktree → 用 `ide_move_file`（自动改引用）。没打开 → `git mv` 后用 perl 改 `package` 行与 import，文件名逐个写字面量：

```bash
perl -pi -e 's/com\.darcytech\.metis\.entity\.node\.(<Xxx>)\b/com.darcytech.metis.core.module.<域>.internal.domain.model.$1/; s/com\.darcytech\.metis\.core\.mysql\.node\.dao\.(<Xxx>Dao)\b/com.darcytech.metis.core.module.<域>.internal.mysql.$1/' -- <文件1> <文件2>
# 改完 import 顺序会乱，对 com.darcytech 连续块排序：
perl -0pi -e 's/((?:^import com\.darcytech\.[^\n]*\n)+)/join("", sort split(m{(?<=\n)}, $1))/mge' -- <文件…>
```

同包后多余的 import（Aggr 引用同包实体）要删。

## 4. 验

```bash
mvnd clean test -pl metis-web -am -Dtest='<域类名前缀>*' -Dsurefire.failIfNoSpecifiedTests=false -q
```

- `-pl metis-web -am` 让 web / core / entity 全量重编——**metis-web 编译通过才是"零外溢"的最终证据**；涉及 agent / datasync / updater 的域把对应模块也加进 `-pl`。
- 退出码 0 不算数：到 `*/target/surefire-reports/TEST-*<前缀>*.xml` 数 `<testcase` 与 `<failure` / `<error`。必须有 MSpec（真实查库）通过，才证明 `@EntityScan` 生效。
- 提交用 `refactor:`，body 写"纯搬家，不改行为"。合回主干走 rebase / `--ff-only`，push 与 MR 等用户明说。

## 常见坑

| 现象 | 处理 |
|---|---|
| worktree 隔离会话里命令被拒："too complex to verify" | 拆成单条命令；不用 shell 变量、循环、`$(...)` 拼路径 |
| `Back-end: Internal error in file lowering`，崩在无关 Kotlin 测试文件 | Kotlin 编译器偶发，原样重跑；再崩 `mvnd --stop` 后重跑 |
| grep 统计引用数偏大 | 扫到了 `.worktrees/` 与 `target/`。用脚本（`git grep` 只扫已跟踪文件）或 IDEA 带 `paths: ["!.worktrees/**"]` |
| 测试 0 个用例却 BUILD SUCCESS | `-Dtest` 用通配 `'Xxx*'`，不要逗号类名列表 |
| 想顺手把 TxService 改成 Repository、给实体去 `DO` 后缀 | 不做。另开提交，保持本次 diff 只有 rename + import |
