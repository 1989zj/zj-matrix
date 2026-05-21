# V3 Pipeline（7 层 17 阶段）

> 本文档记录 V3 架构的完整执行流水线（2026-05-18 起生效）

## 总览

```
┌─────────────────────────────────────────────────────────────────┐
│                     1. 总控层 (Orchestrator)                     │
├─────────┬──────────┬──────────┬──────────┬─────────────────────┤
│ 2. 规划  │ 3. 世界   │ 4. 角色   │ 5. 写作   │ 6. 校验             │
│ Research │ World    │ Character│ Draft   │ Live Validator      │
│ Outline  │ Arc Mgr  │ State Mgr│ Editor  │ Foreshadow Mgr      │
│ Arc Mgr  │ Simulator│          │         │ Anti-Fatigue        │
├─────────┴──────────┴──────────┴──────────┴─────────────────────┤
│                        7. 数据层 (MongoDB)                       │
│  Event Log → Snapshot Store → Collections → Analytics          │
└─────────────────────────────────────────────────────────────────┘
```

## 全流程 17 阶段

V3 pipeline 在 V2 的 13 阶段基础上，新增的阶段标明⬇：

| # | 阶段 | 层 | 说明 |
|---|------|-----|------|
| 0 | **Context Packet 恢复 ⬇** | 总控 | 续写时组装 Context Packet 注入 agent |
| 1 | ARC Planning | 规划 | 世界/阶段/节拍/章节四层规划 |
| 2 | Research | 规划 | 题材方向、爽点模型、市场调研 |
| 3 | Outline | 规划 | 章节场景、高潮分布、钩子设计 |
| 4 | Character Design | 规划 | 角色定位、成长线、关系网 |
| 5 | **World State 初始化 ⬇** | 世界 | 初始化 economy/public_opinion/factions |
| 6 | **Foreshadow 规划 ⬇** | 规划 | 埋伏笔到 foreshadow_queue |
| 7 | Draft（按章） | 写作 | 单章生成（2000-4000字） |
| 8 | **Live Validator ⬇** | 校验 | 实时一致性检查（角色/时间线/逻辑） |
| 9 | Editor（逐行审校） | 写作 | 废话删除、节奏优化、水字数排查 |
| 10 | **Character State 更新 ⬇** | 角色 | 本章写完后的角色状态批量更新 |
| 11 | **World State 更新 ⬇** | 世界 | 世界状态的 delta 更新 |
| 12 | **Event Sourcing 写入 ⬇** | 数据 | 本条 event 写入 event_log |
| 13 | Compliance（每 10 章） | 校验 | 标题党/色情/未成年人/封面/简介 |
| 14 | **Foreshadow 回收检查 ⬇** | 校验 | 本章到期伏笔回收，新伏笔创建 |
| 15 | **Snapshot 保存 ⬇** | 数据 | 每 100 events 生成快照 |
| 16 | Ops 发布 | 数据 | MongoDB 持久化、仓库同步 |

## 各阶段详细说明

### 阶段 0: Context Packet 恢复（续写时）

仅 `continue` 命令触发。从 MongoDB 读取最新状态，压缩为 Context Packet 注入写作 agent：

```
Context Packet = {
  world_state,           # 世界快照
  character_states,      # 所有角色当前状态
  active_plot_threads,   # 进行中剧情线
  last_10_chapters,      # 最近 10 章摘要
  foreshadow_queue,      # 到期需回收的伏笔
  last_arc_summary,      # 上一个 ARC 完成情况
  anti_fatigue_report    # 当前疲劳指数
}
```

详见 `references/context-packet-system.md`。

### 阶段 1: ARC Planning

四层 ARC 规划——World ARC（60-100 章）→ Phase ARC（15-25 章）→ Beat（5-8 章）→ Chapter。

- World ARC 定义顶层目标、核心冲突、终局状态
- Phase ARC 拆解为可管理的子弧（每个 Phase 有其 mini-climax）
- Beat 是 5 章左右的剧情节拍单位
- Chapter 是具体的一章

### 阶段 2-4: Research / Outline / Character

同 V2。Research 产出题材和市场分析；Outline 产出前 20 章钩子和高潮分布；Character 产出角色体系。

输出直接写入 MongoDB 对应 collections（`projects`, `arcs`, `characters`, `chapter_memory` metadata）。

### 阶段 5: World State 初始化

为项目在 `world_state` collection 创建初始状态：
- economy / public_opinion / faction_relations
- capital_attention / city_influence
- 各 faction 的初始力量和立场

V3 新增，V2 无此阶段。详见 `references/world-state-system.md`。

### 阶段 6: Foreshadow 规划

在 ARC 层面规划伏笔的埋设点和回收点，写入 `foreshadow_queue`：
- 每条伏笔有 `setup_chapter`、`expected_callback_chapter`、`deadline_type`（soft/hard）
- 按 urgency 排序，在写作时自动提醒到期回收

V3 新增，V2 的伏笔管理是事后审计而非实时追踪。

### 阶段 7: Draft

每章 2000-4000 字，结尾必须有钩子。draft agent 接收 Context Packet（续写时）或纯大纲提示（new 时）。

V3 变化：draft agent 同时接收 `character_states` 和 `world_state` 的当前快照，保证角色行为一致。

### 阶段 8: Live Validator（V3 新增）

每章写完后立即执行实时校验，检查：
- **角色一致性**：角色情绪/战力与 character_states 是否矛盾
- **时间线一致性**：事件顺序与 timeline 是否冲突
- **逻辑一致性**：是否出现「角色已死又出现」「时间倒流」等逻辑错误
- **伏笔一致性**：到期伏笔是否被回收

Live Validator 的检查结果分为三级：
- `🔴 BLOCKER`：必须修复的错误（不停写，但标记）
- `🟡 WARNING`：需关注但不阻塞
- `🟢 PASS`：无问题

详见 `references/live-consistency-validator.md`。

### 阶段 9: Editor

逐行审校。每章修正：废话删除、拖节奏段落精简、水字数排查。

V3 变化：Editor 的 2nd pass 必须检查 live-validator 的 BLOCKER 标记，如果 BLOCKER 存在但 draft 未修复，editor 需要强制修正。

### 阶段 10: Character State 更新（V3 新增）

本章完全写完并审校通过后，批量更新所有出场角色的 `character_states`：
- `emotional_state` 变化（如 平静→愤怒→疲惫）
- `power_level` 变化（如 突破/升级）
- `relationship` 变化（如 信任值增减）
- `inventory` 变化（如 获得/失去道具）

⚠ 不要在一章写到一半时更新——必须等本章终稿确认后再批量处理。

详见 `references/character-state-machine.md`。

### 阶段 11: World State 更新（V3 新增）

根据本章事件，应用世界状态 delta：
- 经济系统变化（主角赚了多少钱、势力经济变动）
- 舆论变化（公众对主角的看法）
- 势力关系变化（联盟/敌对）
- 城市影响力变化

更新同时记录到 `event_log` 以便回溯。

### 阶段 12: Event Sourcing（V3 新增）

将本章所有变更（新章节、角色状态、世界状态、伏笔回收）以 event 形式写入 `event_log` collection：

```json
{
  "project_id": "...",
  "version": 234,
  "event_type": "chapter_written",
  "data": { "chapter": 45, "word_count": 2800, "title": "..." },
  "timestamp": "2026-05-18T12:00:00Z"
}
```

每 100 events 自动触发 snapshot 生成（阶段 15）。

详见 `references/event-sourcing-system.md`。

### 阶段 13: Compliance

每 10 章一次批量审核。同 V2。

覆盖：标题党、色情低俗、未成年人内容、封面、简介。

### 阶段 14: Foreshadow 回收检查（V3 新增）

检查 `foreshadow_queue` 中 `expected_callback_chapter = 当前章` 的伏笔：
- **到期且被回收** → 标记为 `fulfilled`
- **到期但未被回收** → 生成回调提示，soft deadline 自动延期一次，hard deadline 触发强制回调
- **新的潜在埋伏点** → 推荐在当前章埋设新伏笔

详见 `references/foreshadow-queue-system.md`。

### 阶段 15: Snapshot 保存（V3 新增）

每满 100 events 生成一个完整的状态快照，写入 `snapshot_store` collection：

```json
{
  "project_id": "...",
  "version": 200,
  "snapshot": {
    "world_state": { ... },
    "character_states": { ... },
    "active_plot_threads": [ ... ],
    "foreshadow_queue": { ... }
  },
  "generated_at": 1716000000
}
```

用于 event sourcing 的快速恢复——从最新 snapshot 重放后续 events 即可恢复状态，不需要从 genesis 开始重放。

### 阶段 16: Ops

整理产出、MongoDB 持久化、同步到仓库。同 V2。

## 执行规则

- **阶段 0 只在 `continue` 时执行**，`new` 时跳过
- **阶段 1-6 为串行依赖链**（Research → Outline → Character → World → Foreshadow）
- **阶段 7-15 为每章串行循环**（Draft → Validator → Editor → State Update → Event Log → Foreshadow Check）
- **阶段 8（Live Validator）不会阻塞写作**（不停写策略），但标记的 BLOCKER 会在阶段 9（Editor）中强制处理
- **阶段 13（Compliance）每 10 章触发一次**
- **阶段 15（Snapshot）每 100 events 触发一次**
- **阶段 16（Ops）在每 ARC 完成后执行**

## V2→V3 Pipeline 差异速览

| 项目 | V2 | V3 |
|------|----|----|
| 阶段数 | 13 | 17 |
| 续写恢复 | MongoDB 读取 | Context Packet 系统 |
| 角色管理 | profiles | character state machine + profiles |
| 世界管理 | 无 | world_state collection + simulator |
| 伏笔 | 被动审计 | foreshadow_queue 主动追踪 |
| 一致性 | Editor 人工检查 | Live Validator 自动化 |
| 疲劳检测 | 无 | anti_fatigue 7 维检测 |
| 历史追溯 | 无 | event_log + snapshot |
| 校验级别 | 无 | BLOCKER/WARNING/PASS 三级 |
