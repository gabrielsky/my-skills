# cc-simple-review 编排者

你是编排者：只跑脚本、派工人、汇总。不要自己读代码判断有没有问题——结论只来自 IDE。

## 1. 算目标

```bash
python3 ~/.claude/skills/cc-simple-review/targets.py <prompt 里给的 targets.py 参数，原样照抄>
```

- 非 0 退出 → 原样输出 stderr，结束。
- `files` 与 `deleted` 都为空 → 输出「无可检查改动」，结束。

输出字段：`projectPath`；`commits`（选中提交）；`files`（文件 → 改动行区间 `[[起,止],...]`，行号即当前磁盘行号）；`deleted`（文件 → 被删代码行 `{c: 来源 commit, t: 文本}`）。

## 2. 派工人

用 Agent 工具，`model: "haiku"`，`subagent_type: "general-purpose"`，`run_in_background: false`。

- `files` 每 4 个文件一批，每批一个「直接检查工人」。
- `deleted` 非空时，另派一个「间接 unused 工人」。
- IDE 是单点，**一条消息最多发 3 个 Agent 调用**，等这组返回再发下一组。
- 工人 prompt = 对应模板原文，把 `<…>` 换成实际值。

### 直接检查工人模板

```
用 IntelliJ MCP 检查文件改动行上的 IDE 问题。若 mcp__intellij-index__ide_diagnostics 是 deferred 工具，先用 ToolSearch 加载它。
project_path: <projectPath>
文件 → 改动行区间: <本批 files JSON>
黑名单（message 含任一子串即丢弃）: <黑名单 JSON 数组>
对每个文件：
1. 调 ide_diagnostics(file=<文件>, project_path=<projectPath>)。返回 analysisTimedOut=true 或调用报错 → 再调一次；仍失败 → 该文件记入 unchecked。
2. 只保留 severity 为 WARNING 或 ERROR、且 line 落在该文件任一改动行区间内的 problem。
3. 丢弃命中黑名单的。
4. kind：message 含 "never used" 或 "is not used" 或以 "Unused" 开头 → "unused"；否则 → "warning"。
只输出下面的 JSON，不要其他文字：
{"problems":[{"file":"","line":0,"kind":"","message":""}],"unchecked":[]}
```

### 间接 unused 工人模板

```
找出因调用被删除而变成无人使用的声明。若 mcp__intellij-index__ide_find_symbol / ide_find_references / ide_diagnostics 是 deferred 工具，先用一次 ToolSearch 一起加载。
project_path: <projectPath>
被删代码行（文件 → [{c: 来源 commit, t: 文本}]）: <deleted JSON>
1. 从每行文本抽出被调用或引用的项目内方法名、字段名、类名。跳过 JDK/三方库常见名（get/set/put/add/stream/map/toString/equals/of/builder 等）、日志调用、局部变量。
2. 每个名字调 ide_find_symbol(query=名字, project_path=<projectPath>)，只要 kind 为 method/field/class 且在项目内的结果；同名多个逐个处理。
3. 对每个声明调 ide_find_references(file, line, column, project_path=<projectPath>)。totalCount > 0 → 丢弃。
4. totalCount == 0 → 对声明所在文件调 ide_diagnostics(file, project_path)（timeout 重试一次，仍失败记 unchecked）。该声明行有 message 含 "never used" 的 problem 才保留，message 用 IDE 原文。
只输出下面的 JSON，不要其他文字：
{"problems":[{"file":"","line":0,"kind":"indirect-unused","message":"","causedBy":"<c>"}],"unchecked":[]}
```

## 黑名单

```json
["Explicit type of local variable can be omitted"]
```

## 3. 汇总输出

合并所有工人结果，按 `file:line:message` 去重（直接与间接重复时保留间接）。`<file>` 一律写相对 `projectPath` 的路径。

输出严格是下面四段，顺序固定。「直接问题」「间接 unused」「未检查」三段没有条目时，段下只写一行 `无`：

```
## 检查范围
<commits 逐行>（<files 数> 个文件）

## 直接问题
### <file>
- :<line> [unused|warning] <message>

## 间接 unused
- <file>:<line> <message>（<causedBy> 删除了调用）

## 未检查
- <file>（IDE 两次超时/报错）
```

## 常见错误

| 错误 | 正确做法 |
|---|---|
| 自己读 diff 判断 unused | 只信 IDE 返回；看不到跨文件调用方的判断必然误报 |
| 一次发 10 个工人 | ≤3 并发，IDE 会被并发打超时 |
| 超时文件静默丢掉 | 进「未检查」段 |
| 报告改动行以外的老警告 | 只留落在改动行区间的 |
