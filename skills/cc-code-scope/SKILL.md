---
name: cc-code-scope
description: 仅手动触发。
disable-model-invocation: true
---

# cc-code-scope

圈定一段代码范围，交给用户后续指令使用。本 skill **只圈范围**：全程不跑 `git diff` / `git show`，不读任何改动内容。

## 1. 选类别

```bash
git status --porcelain --untracked-files=all | wc -l   # 未提交文件数（含未跟踪）
git log --format='%h %s' HEAD --not --remotes          # 未推送 commit
```

命令报错（不在 git 仓库里）→ 告诉用户原因，结束。

- 未提交、未推送**都为空** → 跳过本步，直接进第 2 步。
- 否则用 AskUserQuestion 弹窗，header `范围`，**multiSelect: true**，选项按下表，为空的那项不出现：

| label | description | 出现条件 |
|---|---|---|
| 未提交 | `<N> 个文件` | 未提交文件数 > 0 |
| 未推送 | `<N> 个 commit` | 未推送 commit 数 > 0 |
| 已推送代码 | 从最近 10 个 commit 里选 | 总是 |

没选「已推送代码」→ 跳到第 3 步。

## 2. 选已推送 commit

```bash
git rev-list --boundary HEAD --not --remotes | sed -n 's/^-//p' \
  | git log --stdin -10 --format='%h %ad %s' --date=short
```

（从未推送 commit 的边界往下取；没有未推送时 `--stdin` 收到空输入，默认从 HEAD 取。）

输出为空（仓库没有 remote、或分支从没推送过）→ 告诉用户没有已推送 commit；第 1 步还选了别的类别就带着它们进第 3 步，否则结束。

按输出顺序编号（1 = 最新），原样列出，然后**结束本轮**，等用户输入范围：

```
1. ee6026f 2026-10-09 refactor: 删除场景回放开关的前端引用
2. b694a0d 2026-10-08 refactor: 工具调用方错误日志降为 WARN
...
输入范围（如 1-3）：
```

用户可输 `1-3`、`2`、`1,3-5`。超出 1~10 或看不懂 → 指出问题，让用户重输。

## 3. 输出范围

只列用户选中的部分，按 未提交 → 未推送 → 已推送 的顺序：

```
## 代码范围
- 未提交：<N> 个文件
- 未推送：
  - <h> <subject>
- 已推送 #<用户输入的范围>：
  - <h> <subject>
```

输出后加一句「范围已圈定，等你下一步指令。」然后**结束本轮**。

之后用户说「这些改动 / 这个范围 / 上面的代码」，就指这里圈定的范围；到那时再按需读 diff。
