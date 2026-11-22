# 派 Explore 子探子的范例 prompt

Step 2 用。每个 facet 一个 `Explore` 子代理，**同一条消息一次性全部派出**并行。把 `<占位符>` 换成 scout 的实际发现。

通用骨架（每个探子都含这 5 块）：

```
你在探索 <语言> 项目 <项目名>（<一句话项目定位>）的「<业务名>」特征的 **<facet名>**。
工作目录 <项目绝对路径>。

工具：优先 IntelliJ MCP——先 ToolSearch 加载
mcp__intellij-index__ide_read_file / ide_file_structure / ide_call_hierarchy /
ide_find_references / ide_find_class。读某模块文件 project_path 用该子模块绝对路径
（如 <项目>/<子模块>）；报 multiple_projects_open 时按它列的路径挑。也可用 Read 读绝对路径。
非代码(.md/.sql/.sh/pom.xml/日志)用 Read/Bash。

要精读的文件/包（scout 已定位）：
<文件清单>

任务（七步里相关的几步）：
<分步任务>

产出：结构化 markdown，每条结论带 file:line。只读不改，返回纯数据，不寒暄，
没挖到的诚实标注。
```

---

## facet A：数据模型

分步任务示例：

```
1. 实体清单表：实体 | 表名(@Table) | 一句话职责 | 关键字段(字段:类型→业务含义) | 与其他实体关系(外键字段)
2. 枚举值表：每个枚举列全部项(code/name)+含义，状态类枚举单独标。
3. 实体关系图：mermaid erDiagram 画核心实体间一对多/引用。
4. 状态机线索：哪些 status 枚举、字段里有无版本(version/seq)、逻辑删(deleted)、归属(userId)痕迹。
5. 关键设计：版本机制/逻辑删除/归属/可见范围 各怎么用字段体现。
```

## facet B：配置·写入流（产品视角）

```
先 ide_file_structure 或 ls -R 摸清 <配置包路径> 结构(controller/service/dto/log)。
1. 入口清单：找 Controller，列所有 API：HTTP方法+路径 | 干啥 | 入参DTO | 出参DTO。
2. 核心 AppService：主 service 关键方法签名+职责（建/存草稿/发布/启停/删/列表）。
3. 业务规则：精读 service 方法体，抽规则——配额/校验/归属/版本/默认值/并发，每条带 file:line+触发条件。
4. 审计日志：读 <审计类>，列哪些操作记日志、文案模板。
5. DTO 字段：主 DTO 列用户能配哪些字段。
6. 状态机：从 service + 测试(test 目录下 *Spec) 推断生命周期流转。测试的 test("...") 标题是规则金矿，快速读。
```

## facet C：运行·读取流

```
先 ls -R <运行时包> 摸全貌。
1. 调用入口：用 ide_call_hierarchy(direction=callers) 从核心处理类往上追到消息/请求入口，画调用链(类#方法 file:line)。
2. 核心处理：精读主 processor/handler，搞清怎么组装请求、调哪个外部客户端、怎么处理返回、怎么落记录。
3. 路由/筛选(若有)：候选怎么选、按什么分支、命中多个怎么裁决。
4. 数据装配：各输入字段从哪个数据源/service 加载。
5. 端到端流程图：mermaid flowchart 画 入口→...→外部调用→解析→落库→响应。
6. 关键发现：分支区别、超时/失败处理(对应状态枚举)、扩展点。
```

## facet D：演进 WHY

```
用 Bash(git/grep/ls)+Read。
1. git 演进史：git log --oneline -50 -- <各业务包路径>；提取 ticket 号+功能描述，排时间线。
2. PRD/设计文档：ls -R product-docs/ dev-docs/；grep -rl -iE "<业务关键词>" 找相关 md，读最相关 2-4 篇要点。
3. 注释里的 WHY：grep 业务包里的长中文注释、类头注释。
4. 术语线索：收集 中文术语↔代码标识 对应。
产出：演进时间线表 | 业务目标与痛点(3-6条) | 设计意图(为什么这么分层/这么设计,推断标注) | 术语表。
每条带证据(commit hash/file:line/文档路径)。诚实标注没挖到的。
```

---

## 裁剪

- 小业务：合并成 2 个探子（模型+流 / WHY），或不派、自己串行走七步。
- 探子数 = 业务复杂度。别为小事开六个。
- 纯运行时特征砍 B；纯配置项砍 C。
