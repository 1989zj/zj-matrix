---
name: novel-reconstruction
description: Phase 0 — Novel Reconstruction (小说状态重建). One-time full-book scan to restore structured metadata, rebuild character states, migrate timelines, fix ARC metadata, classify foreshadows, and compile Canonical Bible. Strictly mechanical extraction — no content modification.
version: 1.0.0
tags: [novel, reconstruction, metadata, bible, timeline, foreshadow, character-states, canonical-bible]
---

# Phase 0: Novel Reconstruction — 小说状态重建

> **核心理念**: 先把整个小说变成"结构化、可维护、可追踪"的系统，再做精修。
> 这个阶段不修改正文。只做数据恢复。

## 为什么必须先做

直接精修"脏数据"会导致:

| 问题 | 后果 |
|------|------|
| 角色没身份数据 | 精修 Agent 使用旧/错误的 Bible → 越修越乱 |
| 章节没 timeline | 无法判断事件先后 → 时间线错乱 |
| 角色状态空 | state machine 无法工作 → 续写崩 |
| 伏笔未登记 | 精修时忽略伏笔 → 漏修 |
| ARC 数据残 | 精修范围判断错误 → 修错章节 |

## 架构位置

```
创作系统 (hermes-novel-factory)
    ↓
Phase 0: Novel Reconstruction (本章 skill) ← 必须先做
    ├── chapter-memory 补完       (timeline/ch136)
    ├── character-states 重建     (机械化提取)
    ├── ARC 元数据修复            (名字/描述/章节列表)
    ├── Foreshadow 分类           (标记 active/resolved)
    ├── Event Log 重建            (从 summary 生成事件)
    └── Canonical Bible 编译       (统一版本官方真相)
    ↓
Phase 1: Consistency Refinement (精修分支)
Phase 2: Narrative Enhancement
Phase 3: Lore Synchronization
```

## 命令

```bash
cd ~/.hermes/skills/content-creation/novel-reconstruction/scripts/

# 先诊断
python3 novel-reconstruct.py diagnose '诡异游戏'

# 全量重建（按依赖顺序执行所有模块）
python3 novel-reconstruct.py run '诡异游戏' --module all

# 单个模块
python3 novel-reconstruct.py run '诡异游戏' --module timeline
python3 novel-reconstruct.py run '诡异游戏' --module arcfix
python3 novel-reconstruct.py run '诡异游戏' --module foreshadow
python3 novel-reconstruct.py run '诡异游戏' --module ch136
python3 novel-reconstruct.py run '诡异游戏' --module character_states
python3 novel-reconstruct.py run '诡异游戏' --module event_log
python3 novel-reconstruct.py run '诡异游戏' --module bible

# 先看看改什么
python3 novel-reconstruct.py run '诡异游戏' --module all --dry-run
```

## 重建原则

1. **机械化提取** — 不用 LLM/创作模型，纯粹规则匹配
2. **禁止脑补** — 只提取已存在信息，不新增设定
3. **不动正文** — 只改元数据 (chapter_memory, arcs, foreshadow, Bible)
4. **版本可控** — Canonical Bible 带时间戳和版本号
5. **可重复** — 幂等操作，多次执行结果一致

## MongoDB Schema 参考

实际集合字段名与 V3 设计文档存在差异。重建脚本 `novel-reconstruct.py` 已全部适配, 关键差异摘要:

| 集合 | 你以为的字段 | 实际的字段 |
|------|------------|-----------|
| `arcs` | `name`, `chapters` | `title`, 无 chapters 数组 |
| `foreshadow` | `description`, `callback_chapter` | `content`, `suggested_callback_ch` |
| `foreshadow_queue` | — | `urgency` 是 enum (`low/medium/high/critical`), 不能含 emoji |
| `event_log` | — | `timestamp` 必须为 datetime 对象, 字符串会被 schema 拒绝 |
| `world_bible` | — | 所有设定字段为数组类型, 不能是 dict |

完整映射表含 `$jsonSchema` 校验规则详情见 `references/schema-field-mappings.md`。

## 输出

- `chapter_memory`:  每章添加 timeline + characters 字段
- `arcs`: 填充 name + chapters 列表 + description
- `foreshadow`: 所有伏笔标记 status (active/resolved)
- `foreshadow_queue`: 从活跃伏笔重建排队系统
- `event_log`: 每章追加 chapter_completed 事件
- `canonical_bible`: 统一世界观+角色+时间线+伏笔的权威参考

## 后续（LLM 密集型，通过 delegate_task）

- ch136 summary 提取
- character_states 动态状态 (每章情绪/战力/关系)
- 伏笔回补建议生成
- 叙事质量自动评估
