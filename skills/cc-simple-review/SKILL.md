---
name: cc-simple-review
description: 仅手动触发。
disable-model-invocation: true
---

# cc-simple-review

简单代码规则检验。

## 1. 圈范围

- 用户调用本 skill 前的上一条助手消息是 cc-code-scope 的「## 代码范围」输出 → 直接用它，进第 2 步。
- 否则 → Read `~/.claude/skills/cc-code-scope/SKILL.md`，按它的步骤圈范围。它第 3 步输出范围后不结束本轮，直接进第 2 步。

## 2. 检查如下项
1. 是否有unused 的类、方法、参数
2. 未使用java17的一些语法糖
    1. var 局部变量类型推断
    2. Switch 表达式
3. 不使用如下类：
    1. OrikaUtils
    2. new Date