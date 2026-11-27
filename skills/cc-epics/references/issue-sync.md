# 远端骨架 Issue 同步协议

仅在 **模式 A3（Gate 2 后用户确认同步）** 或 **模式 C（补建/同步 Issue）** 时加载。

**唯一真相源原则**：Issue 正文只写摘要、验收概览与指向仓库 `docs/epics/` 的相对/仓库链接，绝不把 `prd.md`、`intent.md` 或 `spec.md` 全文双写到 Issue 中。

---

## 一、检测 Issue Tracker 配置

按以下优先级确定操作规范：

1. **优先读取仓库 `docs/agents/issue-tracker.md`**（由 `/setup-matt-pocock-skills` 生成）：严格遵守其中声明的 CLI 命令、标签与子 Issue / 阻塞边操作方式。
2. **若无 `docs/agents/issue-tracker.md`**：检查 `git remote -v` 与本机 CLI 可用性：
   - 指向 GitHub 且 `gh` 可用 → 使用下方 GitHub 流程；
   - 指向 GitLab 且 `glab` 可用 → 使用下方 GitLab 流程；
   - 无远端或 CLI 未登录 → 提示用户保持纯本地模式，或建议运行 `/setup-matt-pocock-skills` 完成配置。

**安全前置检查（建单前必做）**：
- 创建第一个 Issue 前，先校验目标仓库（GitHub 用 `gh repo view --json nameWithOwner`，GitLab 用 `glab repo view`），确保不是误指向 fork 的上游公共仓库；若目标仓库与预期不符，先向用户确认再写。

---

## 二、两阶段建单与连边流程

按依赖拓扑顺序执行，确保所有跨 Issue 引用均使用真实编号（绝不写入占位符 `#N`）：

### Pass 1：创建 Epic Issue 与各 Story 子 Issue

1. 先创建 **1 个 Epic Issue**，拿到 `<epic-issue-id>` 与 URL。
2. 按 `story-map.md` 的编号顺序创建 **N 个 Story Issue**，逐个记录真实 `<story-issue-id>` 与 URL，并挂为 Epic 的子 Issue：
   - **GitHub（`gh`）**：
     - 创建并挂载：`gh issue create --title "[Epic] <名称>" --body-file -`；子 Issue 优先用 `gh issue create --parent <epic-num> ...` 或 `gh issue edit <epic-num> --add-sub-issue <child-num>`（`gh` 2.94+）。
     - 旧版 `gh` 回退：`gh api --method POST repos/<owner>/<repo>/issues/<epic-num>/sub_issues -F sub_issue_id=<child-db-id>`（注意传数据库 `id`，非 `#number`）；若仓库未启用 sub-issues，则在子 Issue 顶部保留 `Part of #<epic-num>`。
   - **GitLab（`glab`）**：
     - 创建并关联：`glab issue create --title "..." --description "..." --linked-issues <epic-num> --link-type relates_to`，并在子 Issue 顶部写 `Part of #<epic-num>`。

### Pass 2：连结 `blocked-by` 依赖边并回写 `story-map.md`

1. 按 `story-map.md` 中的依赖 DAG 为有前置依赖的 Story 连边：
   - **GitHub**：优先原生依赖 `gh issue edit <child-num> --add-blocked-by <blocker-num>`（旧版用 `gh api --method POST repos/<owner>/<repo>/issues/<child-num>/dependencies/blocked_by -F issue_id=<blocker-db-id>`）；原生能力不可用时在子 Issue 顶部更新 `Blocked by: #<n>`。
   - **GitLab**：优先原生快速命令 `glab issue note <child-num> --message "/blocked_by #<blocker-num>"`；免费版不可用时在子 Issue 描述顶部写 `Blocked by: #<n>`。
2. **回写仓库文档**：
   - 将 Epic Issue 链接回写到 `story-map.md` 顶部；
   - 将每个 Story 的真实 Issue 编号/链接回写到 `story-map.md` 表格及对应 `stories/<NN>-<slug>/intent.md` 头部。

---

## 三、Issue 摘要模板

### Epic Issue 正文模板

```markdown
## 概述

<1–3 句话说明本 Epic 的业务背景与核心目标>

## 仓库真相源文档

- PRD: `docs/epics/YYYY-MM-<epic-slug>/prd.md`
- Story Map: `docs/epics/YYYY-MM-<epic-slug>/story-map.md`

## MVP 界线

<一句话说明哪些 Story 构成 MVP 闭环>
```

### Story Issue 正文模板

```markdown
Part of #<epic-issue-number> <!-- 若原生 sub-issue 已挂载可省略 -->

## 目标

<摘自 intent.md 的 1–2 句话端到端价值>

## 仓库文档

- Intent: `docs/epics/YYYY-MM-<epic-slug>/stories/<NN>-<story-slug>/intent.md`
- Spec: `docs/epics/YYYY-MM-<epic-slug>/stories/<NN>-<story-slug>/spec.md`（滚动细化后生成）

## 验收边界

- [ ] <摘自 intent.md 的高层次可验证行为 1>
- [ ] <摘自 intent.md 的高层次可验证行为 2>

## 下游说明

本 Story 细化 `spec.md` 后，将通过 `/to-tickets` 在本 Issue 下拆分子开发 Ticket。
```
