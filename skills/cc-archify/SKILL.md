---
name: cc-archify
description: 基于已安装的 Archify 生成或修改交互式架构图、流程图、时序图、数据流图和状态图，并完整显示源码类名与路径。用于请求 cc-archify、自定义 Archify，或要求源码标注不截断的图表。
---

# CC Archify

这是独立的个人定制层。复用当前安装的 Archify，不维护原版渲染器副本，也不修改原版安装目录。

## 使用流程

1. 选择并阅读已安装的原版 `SKILL.md`。优先使用 `~/.codex/skills/archify`；不存在时使用 `~/.agents/skills/archify`。全程使用同一份原版，其 schemas、examples、references 均相对于该目录读取。
2. 按原版流程完成证据检索、候选 JSON、生成和检查。把其中所有 `node .../bin/archify.mjs` 调用替换为下面的包装入口，保留原命令的其余参数和工作目录：

   ```bash
   python3 ~/.codex/skills/cc-archify/scripts/archify.py --upstream ~/.codex/skills/archify finalize architecture candidate.json diagram.html --quality showcase --json
   ```

   若选择另一份原版，相应替换 `--upstream`。仓库图仍须传入原版要求的 `--repo-root` 等参数。宿主要求命令前缀（如 `rtk proxy`）时照常添加。
3. 包装入口每次复制当前原版到临时目录，仅修改副本中的共享查看器模板，再调用原版 CLI；结束后清理副本。定制因此在生成和校验之前生效。不要在交付后直接修改 HTML 或伪造来源回执。
4. 补丁无法应用时停止生成并说明模板不兼容；检查新版模板后再适配本 Skill 中的补丁。不得绕过失败直接交付会截断来源的图。原版的浏览器检查、视觉复核、更新提示和结果报告要求继续适用；受工具限制而未执行的检查应明确说明。

## 源码显示规则

- 完整类名／文件名独占一行，放在完整的仓库相对路径之前，保留用途说明和行号。
- 类名、文件名和路径自动换行，包括没有空格的长名称；内容过长时面板可滚动。
- 不允许省略号、行数截断或人为缩短路径；悬浮提示不能替代直接显示完整信息。
- 保留真实 source path 和行号用于证据校验，不通过篡改来源数据缩短展示文字。

补丁位于 [assets/source-display.patch](assets/source-display.patch)，已验证原版 3.0.1 的五种图类型。升级原版不会覆盖本 Skill，但模板结构变化可能需要更新补丁；这不是对未来版本兼容性的保证。
