# 单 Story 细化参考：`spec.md` 行为规格模板与交接格式

仅在**模式 B（滚动细化单个 Story）**加载。

---

## 一、编写原则（产品/用户视角检查清单）

落盘 `spec.md` 前逐项自检：

1. **可读性测试**：整份 `spec.md` 拿给产品经理、QA 或业务方阅读时，不需要懂代码架构也能完整理解并确认「系统应该如何表现」。
2. **只写外部行为，不写底层实现**：写清用户怎么操作、系统给出什么反馈、业务规则如何判定、状态如何变化、异常怎么兜底；不写代码类名、文件路径、表结构、分布式锁、缓存结构或内部协议字段。
3. **术语统一**：全程采用仓库 `GLOSSARY.md` 与 `prd.md` 约定的业务术语，同一概念不混用别名。
4. **场景可验收**：每条验收场景都能直接转化为产品演示步骤或端到端测试用例（有明确的触发条件与可观察结果）。
5. **范围回流检查**：若细化过程中改变了 `prd.md` 的全局业务规则或其他 Story 的边界，主动提醒用户同步修正。

---

## 二、`stories/<NN>-<story-slug>/spec.md` 模板

```markdown
# Spec: Story <NN> - <Story 名称>

> **Epic**: [<Epic 名称>](../../prd.md) | **Story Map**: [story-map.md](../../story-map.md)
> **Intent**: [intent.md](./intent.md) | **Story Issue**: <远端链接或"本地模式">

## Problem Statement

从用户/业务视角清晰描述本 Story 要解决的具体问题。

## Solution

从用户/业务视角描述本 Story 提供的端到端体验与解决方案。

## User Stories

覆盖本 Story 主路径、分支与异常态的编号用户故事：

1. 作为 <角色>，我希望 <做什么>，以便 <获得什么价值>
2. ...

## Behavior & Business Rules

用产品与用户可理解的语言写清本 Story 的确定性行为（按需取舍小节）：

- **入口与交互流**：用户从哪里进入、经历哪些步骤、看到哪些反馈或提示文案；
- **业务规则与计算口径**：判定条件、字段业务含义（仅业务语义，不写存储类型）、默认值与限制；
- **状态流转**：涉及对象在各状态下的可见表现与允许操作；
- **边界与异常表现**：空态、超限、重复触发、无权限、外部能力不可用时的明确行为与提示。

> 若 `prototype` 产出了交互线框或状态流转示意，可内联精简版示意或附上链接。

## Acceptance Scenarios

可直接用于产品验收与端到端测试的场景清单（Given / When / Then 或清晰的条件 → 预期结果）：

1. **<主路径场景名>**：给定 <前置状态>，当 <用户/外部触发动作>，则 <用户可观察到的明确结果>。
2. **<关键分支/异常场景名>**：给定 <...>，当 <...>，则 <...>。

## Out of Scope

明确本 Story 排除的范围（含归属后续 Story 的能力与 Epic 之外的能力）。

## Further Notes

补充说明（如本次拍板的业务口径变更、依赖的外部业务前提或上线注意事项）；无则省略。
```

---

## 三、完成后更新与下游交接（Handoff）

1. **更新 `story-map.md`**：
   - 将该 Story 行状态从 `intent` 改为 `spec-ready`；
   - 在 `Intent / Spec` 列补上 `[spec](stories/<NN>-<slug>/spec.md)` 链接。
2. **输出标准交接块**（可直接复制执行）：

```markdown
### 下一步交接（Handoff）

本 Story 行为规格已落盘：`docs/epics/YYYY-MM-<epic-slug>/stories/<NN>-<story-slug>/spec.md`（`story-map.md` 已更新为 `spec-ready`）。

1. **技术方案设计（可选，复杂改造时使用）**：
   - 若本 Story 涉及复杂架构或上游模块调整，可先运行 `/cc-design-proposal` 完成技术设计。
2. **进入研发拆票**：
   - 运行 `/to-tickets docs/epics/YYYY-MM-<epic-slug>/stories/<NN>-<story-slug>/spec.md`（若有远端 Story Issue，一并附上传入关联父 Issue），由研发视角结合代码库拆出开发 Ticket。
3. **编码实现与验收**：
   - Ticket 确认后，运行 `/implement-spec` 执行 TDD 实现与 code review。
4. **本 Story 交付后**：
   - 运行 `/cc-epics docs/epics/YYYY-MM-<epic-slug>/story-map.md` 更新状态为 `done` 并领取下一个前沿 Story。
```
