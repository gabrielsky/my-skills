---
name: cc-java-coding-standards
description: >-
  后端工程设计原则与 Java (17+ / Spring Boot) 编码规范：涵盖系统设计取舍（按需一致性、小错简单恢复、数据库原生能力优先、配置覆盖语义、按副作用判幂等、有界重试、按已知规模设计、只抽象明确共性、风险边界与范围限制），以及边界校验与反过度判空（Fail-Fast、集合与 Optional 契约）、Java 17+ 语法（var、switch 表达式、record）、禁用 API（OrikaUtils、Date）和异常处理纪律。在设计后端技术方案、讨论实现取舍、编写/修改/重构或评审后端代码时使用。
---

# cc-java-coding-standards

面向后端系统设计与 Java 17+ / Spring Boot 项目的工程规范，核心目标是**控制复杂度、保持契约清晰、消除防御性噪音、明确快速失败**。

---

## 1. 后端设计与实现原则

### 1.1 状态、数据与并发控制
1. **一致性按需保证**：业务允许时接受短暂不一致；本地事务能完成的事，不拆成异步消息和补偿流程。
2. **优先数据库原生能力**：用唯一约束防重复、事务保证原子性、条件更新限定状态转换，能用 SQL 解决就不引入分布式协调。
3. **配置按覆盖语义处理**：允许后保存覆盖先保存时，只更新目标字段；有重要工作丢失风险或明确协同需求时，再加乐观锁、冲突提示或合并。
4. **幂等按副作用判断**：可接受的重复计算不追求“恰好一次”；发消息、发券、扣额度等动作，单独评估重复执行的后果。

### 1.2 容错、恢复与边界契约
5. **小错优先简单恢复**：失败可发现、恢复成本低时，优先重跑或重建，不为此引入复杂预防机制。
6. **明确失败，不伪装成功**：返回可理解的错误，不用空列表、零值或“成功”掩盖故障；仅在业务明确允许时降级（编码细则见 §2.2、§5）。
7. **重试有界且不叠加**：仅重试可能恢复的临时故障，限制次数和时间，先确认框架已有行为；结果未知的外部写入不盲目重试。
8. **边界校验，内部守约**：校验外部输入，内部按明确契约调用，避免逐层判空、转换和补默认值；违约应暴露（编码细则见 §2）。

### 1.3 复杂度、规模与范围克制
9. **按已知规模设计**：小规模、低频操作优先直接查询、同步处理和简单循环；有实际规模、性能要求或测量依据后，再引入缓存、并行、异步或分片。
10. **只抽象明确的共性**：实现当前需求，不预建通用框架；已有清晰的共享业务规则应复用。
11. **按业务风险处理边界**：优先常见输入、明确限制、不可逆操作和已知故障；低概率、低损失且易恢复的情况，明确限制即可。
12. **用范围限制换简单可靠**：按需限制批量数量、导出时间范围或要求串行执行，不默认支持无上限兼容和复杂调度。

---

## 2. 判空与信任边界（反过度防御 `null`）

### 2.1 只在系统边界做防御（Validate at Boundaries Only）
- **外部边界才做校验与判空**：Controller 入参（`@Valid` + `@NotNull` / `@NotBlank` / `@NotEmpty`）、MQ 消费入口、外部 HTTP/RPC 响应、反序列化入口。
- **内部层信任上游契约**：Service / Domain / Repository 内部调用默认信任上游非空契约，**禁止层层重复判空**。

### 2.2 信奉 Fail-Fast，严禁静默兜底（No Silent Fallbacks）
- 按业务不变量绝不该为 `null` 的值（如数据库 `NOT NULL` 列、已鉴权上下文的 `userId`、刚校验过的对象），**严禁**写 `if (x == null) return null;`、`return Collections.emptyList();` 或 `Optional.ofNullable(x).orElse(...)` 伪装正常、掩盖故障。
- 若需在构造器或公共入口守护核心不变量，使用 `Objects.requireNonNull(x, "...")` 或直接抛出明确异常，让违约第一时间暴露。

### 2.3 依据显式契约判空，不盲猜
- **默认非空**：包/模块优先使用 `@NullMarked`（JSpecify）；只有真正可能为 `null` 的参数、返回值或字段才标 `@Nullable`（默认非空下不写冗余的 `@NonNull`）。
- **改代码前先查上游**：想在已有内部代码里加判空前，先查清字段定义或上游实现（如 JPA `@Column(nullable = false)`、DTO 校验注解、DAO 返回约定）。只有确认确实可空（如 DB 可空列、单条查询可能无结果）或 `null` 具有明确业务语义（如“未设置 / 永久有效 / 首次游标”）时才写判空。

### 2.4 集合与 `Optional` 契约
- **集合永不返回 `null`**：方法返回集合或对象内的集合字段，无数据时统一用 `List.of()` / `Set.of()` / `Map.of()`（或 `Collections.empty*()`）。内部消费集合直接遍历、`.stream()` 或判 `.isEmpty()`，**禁止**写 `if (list != null && !list.isEmpty())` 套娃。
- **`Optional` 仅作返回类型**：
  - 单条查询可能不存在时（如 `findBySlug`）返回 `Optional<T>`；**严禁**将 `Optional` 用作方法参数或类字段（可空入参/字段直接用 `@Nullable T`）。
  - 消费 `Optional` 用 `.map(...)` / `.orElse(...)` / `.orElseThrow(...)`，**禁止**裸调 `.get()`，也**禁止**把已知非空的对象套进 `Optional.ofNullable(...)`。

```java
// ✅ 边界校验 + 内部直接消费 + Optional 返回单值
public MarketResponse getMarket(String slug) {
    return marketRepository.findBySlug(slug)
        .map(MarketResponse::from)
        .orElseThrow(() -> new MarketNotFoundException(slug));
}

// ❌ 内部层过度防御、静默兜底掩盖问题
public List<String> extractNames(List<Market> markets) {
    if (markets == null || markets.isEmpty()) { // 多余的 != null
        return Collections.emptyList();
    }
    return markets.stream()
        .filter(Objects::nonNull) // 若契约中元素必非空，不加无意义过滤
        .map(m -> Optional.ofNullable(m.getName()).orElse("")) // 掩盖脏数据
        .toList();
}
```

---

## 3. Java 17+ 语法与不可变性

1. **`var` 局部变量类型推断**：右侧类型一目了然时（构造器、`of/from` 工厂方法、泛型冗长的局部变量）优先用 `var` 降噪；右侧返回类型不直观或涉及数值精度字面量时保留显式类型。
2. **`switch` 表达式与模式匹配**：
   - 优先使用 `switch (...) { case A -> ...; }` 箭头语法与返回值表达式，对枚举和 `sealed` 类型利用编译器穷举检查，避免手写 `default` 吞掉未来新增枚举值。
   - 类型判断并强转使用模式匹配：`if (event instanceof OrderPaidEvent paid)`。
3. **不可变优先**：
   - 纯数据载体（DTO、Command、Query、值对象、内部上下文元组）优先定义为 `record`，必要时在紧凑构造器中做不变量校验。
   - 普通类字段默认 `private final` + 构造器注入，按业务动作提供语义化方法，不无脑暴露全套 `setter`。
4. **文本块（Text Blocks）**：多行 JSON、SQL、脚本模板使用 `"""` 文本块，避免拼接转义。
5. **Stream 终端收集**：不可变列表直接用 `.toList()`，替代 `.collect(Collectors.toList())`。

---

## 4. 禁用 API 与零死代码

| 禁止写法 | 替代方案 |
|---|---|
| `OrikaUtils` | 使用显式类型安全的静态工厂/转换方法（如 `FooDto.from(entity)`、`entity.toDomain()`）或项目当前约定的编译期映射器 |
| `new Date()` / `Calendar` / `SimpleDateFormat` | 统一使用 `java.time`（`Instant`、`LocalDateTime`、`LocalDate`、`ZonedDateTime`、`DateTimeFormatter`） |
| 裸类型（Raw Types，如 `List`、`Map`） | 声明完整泛型参数 |

- **零 Unused 代码**：新增或修改代码后，清理所有未使用的类、方法、字段、方法参数、局部变量及多余 `import`，不留注释掉的废弃代码块。

---

## 5. 异常与错误处理

- **明确失败，不伪装成功**：严禁空 `catch` 块；严禁捕获异常后仅打一行日志就返回空集合、`null` 或 `0` 假装成功——除非业务明确要求了降级兜底策略。
- **领域异常语义化**：使用自定义运行时异常表达业务错误（如 `OrderStateConflictException`），附带关键排障标识（业务单号、当前状态），不泄露密钥或敏感隐私。
- **克制捕获范围**：避免在内部业务层宽泛 `catch (Exception ex)`，除非需要补充上下文重抛，或处于批处理单条隔离、顶层统一拦截入口。

---

## 6. 可读性与注释纪律

- **卫语句早返回**：遇到前置条件分支优先 `return` / `throw`，拍平多层 `if-else` 嵌套。
- **Stream 保持简短**：`Stream` 管道只做清晰的线性数据变换；涉及复杂条件跳转、外部可变状态或受检异常时，直接写普通 `for` 循环，禁止复杂嵌套 `stream`。
- **注释只写 Why，不写 What**：
  - 不写复述代码的注释（如 `// 查询用户`），不写变更流水账（如 `// 本次需求新增`）。
  - 仅在代码无法自解释时，写明这一处特有的外部事实与约束（如三方接口怪癖、DB 特殊约束、阈值测算依据）。
