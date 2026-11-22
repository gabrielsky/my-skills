---
name: cc-worktree
description: 列出当前仓库的 worktree 供选择，选中后把会话切过去并把会话标题改成该 worktree 的主题，后续指令都在该 worktree 里执行。
disable-model-invocation: true
argument-hint: "[名称关键字]"
---

# cc-worktree

用户调用本 skill，就是明确要求进入某个已有的 worktree。

## 1. 取列表

```bash
bash ~/.claude/skills/cc-worktree/list.sh
```

每行 TSV：`path  branch  dirty(未提交文件数)  active(最近活跃)  current(1=会话所在)  commits(领先主干的提交，| 分隔)  files(未提交文件，逗号分隔)`，已按「有未提交改动优先、再按最近活跃」排好序，不含主 worktree。命令失败（不在 git 仓库里）就告诉用户原因，然后停止；输出为空就告诉用户除主干外没有 worktree，然后停止。

给每行写一句**简介**（15 字左右）：从 commits 和 files 归纳这个 worktree 在做什么，例如「补前端页面单测」「Sprint 页 milestone 接口 + 测试」。两列都空时写「无改动」。

每行的**名称**：目录名；current=1 的在后面加 `（当前）`。

## 2. 选定目标

`$ARGUMENTS` 非空，且恰好命中一行（不区分大小写，对目录名或分支做子串匹配）时，直接选中这一行，跳到第 3 步。

其余情况按行数分两种：

- **≤ 3 行**：用 AskUserQuestion 弹窗，header 为 `Worktree`，单选，每行一个选项。label 是名称，description 是 `简介 · <dirty> 个未提交 · <active>活跃`。
- **> 3 行**：直接输出编号列表，然后结束本轮，等用户回复序号或关键字：

  ```
  1. manual-reply（当前） [feature/手动回复] — 后台手动回复页面 · 4 个未提交 · 2小时前
  2. modest-kalam-07f818 — 补前端页面单测 · 5 个未提交 · 11天前
  ```

  分支名和目录名对不上时（比如不是 `claude/<目录名>`），在名称后加 `[<branch>]`。

用户回复的是关键字时，按上面的子串规则匹配；命中多行或没命中，就把结果告诉用户，让用户重新选。

## 3. 切换

- 目标 current=1：告诉用户已经在这里，做完第 4 步后结束。
- 其余情况：调用 `EnterWorktree`，参数 `path=<目标 path>`。本步和第 4 步的工具如果是 deferred，先用 ToolSearch `select:EnterWorktree,ExitWorktree,mcp__ccd_session_mgmt__set_session_title` 一次加载。
- EnterWorktree 拒绝时（常见原因：会话已在 worktree 里，而目标在 `.claude/worktrees/` 以外，如 `.worktrees/` 下）：调用 `ExitWorktree`，`action: "keep"`，回到会话的启动目录。启动目录如果就是目标，切换完成；否则用同一个 path 再调一次 EnterWorktree，仍被拒就把报错原样告诉用户。

## 4. 改会话标题

调用 `mcp__ccd_session_mgmt__set_session_title`，参数 `session_id: "self"`。`title` 从分支名取：先去掉最后一个 `/` 及之前的部分，再去掉开头的 issue 号段（`proj-123-`、`#123-`、`aikf#123-` 这类）。

| 分支 | 标题 |
|---|---|
| `feature/proj-123-属性应答管理` | `属性应答管理` |
| `chore/升级liquibase` | `升级liquibase` |
| `maint/jx/aikf#456-提示词缺环境变量` | `提示词缺环境变量` |

以下情况改用第 1 步生成的简介：分支是 `claude/*`（app 自动生成的名字）、处于 detached 状态，或者去掉前缀后为空。如果没有这个工具（不在桌面 app 里），就跳过这一步。

## 5. 确认

在新目录跑 `git status -sb`，用一行回报：`已切到 <名称>（<branch>，<dirty> 个未提交文件）`。之后的指令都在这个 worktree 里执行。
