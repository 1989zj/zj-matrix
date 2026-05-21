---
name: hermes-novel-factory
description: V3 - World state machine + event-sourcing multi-agent novel factory for 500万字 long-form web novels. Stateful character management, foreshadow debt system, dynamic ARC planning, context-packet recovery, live consistency validation, and anti-fatigue detection.
version: 6.0.0
tags: [novel, hermes, profile, multi-agent, pipeline, content-factory, web-novel, tomato-novel, v3, mongodb, 500万, batch-writing, seasonal, multi-session, state-machine, event-sourcing, foreshadow, arc-manager, world-simulator]
---
# Hermes Novel Factory V3 — 世界状态机 + 事件驱动架构

## 核心创新: 用 MongoDB 取代上下文记忆 + 世界状态机 + 事件溯源，实现 500 万字可持续创作。
## 核心原则: 所有产出自动写入 MongoDB，不依赖 GitHub 做持久化存储。
## 分批创作: 支持跨 Hermes 会话的季式创作（分 ARC 分季写完300万字，见「多轮次/季式创作策略」节）。
> **前身**: V1（章节级并行写作）→ **V2**（ARC 级持久化 + 防重复 + 记忆管理中心）→ **V3**（世界状态机 + 角色状态机 + 事件溯源 + 伏笔债务 + 动态 ARC + 疲劳检测 + 一致性校验）

---

## 为什么需要 V2

V1 的问题 —— 当小说超过 30 万字时：

| 问题 | 表现 | 根因 |
|------|------|------|
| 上下文崩塌 | 模型开始忘记早期设定、角色名字写错 | 单次 context 上限 128K tokens |
| 人物漂移 | 角色性格/能力逐渐偏离最初设定 | 没有持久化角色档案 |
| 世界观矛盾 | 后续章节新增规则与早期矛盾 | 没有版本控制的世界观圣经 |
| 剧情重复 | 中期出现相似的打脸/升级/副本套路 | 无法回溯已用过的剧情模式 |
| 伏笔丢失 | 前期埋伏笔、后期忘回收 | 没有伏笔数据库 |
| 爽点疲劳 | 同一个爽点模式用 10 次 | 没有重复检测 |

**V2 的解决方式**：所有 Agent 不再依赖上下文记忆，统一从 MongoDB 读取/写入世界数据。每次调用前加载最新状态，写完写入数据库。500 万字不崩。

---

## V3 核心升级：从持久化到状态机，从写手到操作系统

V2 解决了「记不住」的问题，但 V3 解决的是「写不深」的问题——当小说超过 100 万字后，即使数据库里有所有数据，模型仍然会写出逻辑矛盾、角色漂移、剧情重复的问题。根因不在于记忆，而在于**没有系统的状态管理**。

### V3 的 7 项核心创新

| # | 创新 | 解决什么 | 核心机制 |
|---|------|---------|---------|
| 1 | **Context Packet 恢复系统** | 跨会话上下文崩塌 | 每 continue 前组装「创作状态压缩包」，含 world_state、character_state、active_plot_threads、last_10_chapters_summary、foreshadow_queue |
| 2 | **角色状态机** | 角色性格/情绪/关系漂移 | base_personality 不可变 + current_state 每章更新（情绪/信任/疲劳/财富/战力/关系图），由 character-state-agent 维护 |
| 3 | **动态 ARC Manager** | 百万字后 ARC 规划僵化 | 四层 ARC（World→Phase→Beat→Chapter），每 10/30/100 章自动重构下级规划 |
| 4 | **世界状态模拟器** | 世界观矛盾、因果断裂 | 每章后更新经济/舆论/影响力/势力，维护因果链和阈值触发 |
| 5 | **伏笔债务系统** | 伏笔丢失、回收稀松 | foreshadow_queue 带 deadline/priority/urgency，每 draft 前检查到期坑位，强制回收 |
| 6 | **事件溯源同步** | 数据不一致、不可回滚 | append-only event_log 作为唯一真相源，snapshot 每 100 事件生成，支持任意点回滚 |
| 7 | **实时一致性校验** | 跨章数字/名称/金额/战力矛盾 | Draft 输出时并行校验 7 维（金额/战力/时间线/称呼/人设/地点/物品），BLOCKER 不停写仅告警 |

### V3 架构分层

```text
用户需求
  │
  ▼
┌──────────────────────────────────────────────┐
│      战略层 (Strategy Layer)                   │
│  arc-manager · analytics · context-packet     │
│  规划全书方向 · 生成 Context Packet · 质量反馈   │
└─────────────┬────────────────────────────────┘
              │
┌──────────────▼──────────────────────────────┐
│      世界层 (World Layer)                     │
│  world-simulator · lore · timeline · power   │
│  维护世界状态 · 圣经版本控制 · 因果链           │
└──────────────┬──────────────────────────────┘
              │
┌──────────────▼──────────────────────────────┐
│      角色层 (Character Layer)                 │
│  character-agent · character-state-agent     │
│  角色档案 · 动态状态机 · 关系图 · 记忆管理      │
└──────────────┬──────────────────────────────┘
              │
┌──────────────▼──────────────────────────────┐
│      写作层 (Writing Layer)                   │
│  draft-main/action/romance · editor          │
│  正文生成 · 微观/宏观审校 · 伏笔回收触发        │
└──────────────┬──────────────────────────────┘
              │
┌──────────────▼──────────────────────────────┐
│      审核层 (Review Layer)                    │
│  live-validator · anti-fatigue · compliance  │
│  实时校验 · 七维疲劳检测 · 合规审查             │
└──────────────┬──────────────────────────────┘
              │
┌──────────────▼──────────────────────────────┐
│      持久层 (Persistence Layer)               │
│  memory-manager · event-log · snapshot       │
│  原子写入 · 事件溯源 · 版本控制 · 快照          │
└──────────────────────────────────────────────┘
              │
              ▼
  MongoDB novel_factory（16个Collection）
```

### V3 新增/替换的 Collection

| # | Collection | 状态 | 说明 | 关系 |
|---|-----------|------|------|------|
| 9 | `world_state` | 新增 | 世界状态快照 | 与 world_bible 并行，圣经≡规则，快照≡当前 |
| 10 | `character_states` | 新增 | 角色动态状态 | 与 characters 并行，档案≡不变，状态≡变化 |
| 11 | `arc_plans` | 新增 | 四层 ARC 规划 | 是 V2 arcs 的扩展，arcs 保留归档 |
| 12 | `foreshadow_queue` | 升级替换 | 伏笔队列（带 deadline） | 逐步替代 V2 foreshadow |
| 13 | `plot_debt` | 新增 | 剧情债务 | 与 foreshadow_queue 互补 |
| 14 | `event_log` | 新增 | 事件溯源日志 | 所有写操作的权威记录 |
| 15 | `snapshot_store` | 新增 | 状态快照 | 每 100 event 生成一次 |
| 16 | `anti_fatigue` | 升级替换 | 七维疲劳检测 | 逐步替代 V2 anti_repetition |

> 完整 schema（含 `$jsonSchema` 校验规则）见 `references/novel-factory-v2-schema.md`（已升级为 V3 版）。

### V3 执行流程（单 ARC 循环）

```
for each ARC:
  Step 0: context-packet → 组装创作状态压缩包（从 event_log 恢复最新状态）
  Step 1: arc-manager → 四层 ARC 规划 → arc_plans + plot_debt
  Step 2: world-simulator → 世界状态初始化
  Step 3: character-state-agent → 角色状态机初始化
  Step 4: lore + timeline + power → 世界观/时间线/战力准备

  for each 3-chapter batch in ARC:
    Step 5: foreshadow-manager → 检查到期伏笔，标记回收提醒
    Step 6: draft-main/action/romance → 写 3 章（基于 context packet）
    Step 7: live-validator → 7 维实时一致性校验（并行）
    Step 8: editor 1st+2nd pass → 微观审校 + 宏观一致性
    Step 9: anti-fatigue → 七维疲劳检测
    Step 10: world-simulator → 更新世界状态
    Step 11: character-state-agent → 更新角色状态
    Step 12: memory-manager → event_log 写入 + 批量写入 MongoDB
    Step 13: compliance → 合规审查

  Step 14: analytics → ARC 质量报告
  Step 15: context-packet → 保存检查点
  Step 16: snapshot → 每 100 event 生成状态快照
```

---

## 系统架构

```text
用户需求
  │
  ▼
orchestrator（总控 V3）
  │
  ├── 战略层 ──→ ARC Manager · Analytics · Context Packet
  ├── 世界层 ──→ World Simulator · Lore · Timeline · Power-Control
  ├── 角色层 ──→ Character · Character-State Agent
  ├── 写作层 ──→ Draft Agents (main/action/romance) · Editor
  ├── 审核层 ──→ Live Validator · Anti-Fatigue · Compliance
  └── 持久层 ──→ Memory Manager · Event Log · Snapshot
        │
        ▼
  memory-manager（核心中间件——所有写入必经之路）
        │
        ▼
  MongoDB novel_factory（16个Collection）
```

---

## MongoDB 层（核心）

### 数据库

```text
数据库: novel_factory
地址:   192.168.2.30:27017
认证:   mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/
```

### 16 个主 Collection（+ 4 个 _history 版本库）

> 完整 schema（含 `$jsonSchema` 校验规则、允许类型、required 字段）见 `references/novel-factory-v2-schema.md`（已升级为 V3 版，含全部 16 个集合）

#### V2 继承（8 个，保持兼容）

| # | Collection | 用途 |
|---|-----------|------|
| 1 | `projects` | 小说项目元数据 |
| 2 | `world_bible` | 世界观圣经 |
| 3 | `characters` | 角色数据库 |
| 4 | `timeline` | 时间线 |
| 5 | `arcs` | 剧情弧（归档层，V3 改为 arc_plans 做规划） |
| 6 | `foreshadow` | 伏笔（逐步迁移到 foreshadow_queue） |
| 7 | `chapter_memory` | 章节记忆 |
| 8 | `anti_repetition` | 重复检测（逐步迁移到 anti_fatigue） |

#### V3 新增/升级（8 个）

| # | Collection | 用途 | 说明 |
|---|-----------|------|------|
| 9 | `world_state` | 世界状态快照 | 经济/舆论/势力/危机 |
| 10 | `character_states` | 角色动态状态 | 情绪/信任/疲劳/财富/战力/关系图 |
| 11 | `arc_plans` | 四层 ARC 规划 | World→Phase→Beat→Chapter |
| 12 | `foreshadow_queue` | 伏笔队列 | 带 deadline/priority/urgency |
| 13 | `plot_debt` | 剧情债务 | 对读者的承诺追踪 |
| 14 | `event_log` | 事件溯源日志 | 所有写操作的权威记录 |
| 15 | `snapshot_store` | 状态快照 | 每 100 event 生成 |
| 16 | `anti_fatigue` | 七维疲劳检测 | 爽点/台词/情绪/装逼/打脸/战斗/场景 |

**版本历史集合**（由 memory-manager 自动管理）：`characters_history`、`arcs_history`、`world_bible_history`、`chapter_memory_history`。每次写入自动存档旧版本，支持 rollback 回滚。

> **注意**: `novel_factory` 是 V2 **创作中间态**数据库。最终成品章节仍存回 `novel` 库的 `chapters` 集合（80 章 276K 字的 v1 模式兼容）。

---

## 读写协议（关键规则）

### 读取（Read）—— 自服务模式
任何 Agent 可以直接查询 MongoDB 读取数据，不需要经过 memory-manager。

```python
# 所有 Agent 可用的读取模式
client = pymongo.MongoClient("mongodb://mongo_8F6dTZ:<password>@192.168.2.30:27017/")
db = client["novel_factory"]

# 读取世界观
world = db["world_bible"].find_one({"project_id": pid})

# 读取角色
char = db["characters"].find_one({"project_id": pid, "name": "主角名"})

# 读取最近 N 章记忆
recent = db["chapter_memory"].find(
    {"project_id": pid}
).sort("chapter", -1).limit(5)
```

### 写入（Write）—— 必经 memory-manager
**任何对 `novel_factory` 数据库的修改，必须由 memory-manager 执行。**

写入流程：
1. 各 Agent 对数据做出修改后，将变更集打包递交给 orchestrator
2. orchestrator 将变更集转发给 memory-manager
3. memory-manager 执行冲突检测 → 版本归档（`save_with_version`）→ 写入主集合

> **版本化说明**：每次写入自动执行 `save_with_version`，旧版本快照保存到对应 `_history` 集合（characters_history / arcs_history / world_bible_history / chapter_memory_history），实现完整审计轨迹与回滚能力。详见 `soul-memory-manager.md`。
4. 返回确认（带写入后的完整文档，用于下游 Agent 校验）

```python
# memory-manager 工作模式（V2 带版本化）
def save_with_version(collection, query, update, changed_by, reason):
    """写出前检查冲突，归档旧版，写入新版"""
    current = db[collection].find_one(query)
    if current and has_conflict(current, update):
        return {"status": "conflict", "current": current, "proposed": update}
    # Phase 1: 归档旧版本到 _history（无事务，最佳努力）
    if current:
        history_entry = {
            "project_id": current.get("project_id"),
            "original_id": current["_id"],
            "version": current.get("version", 0) + 1,
            "snapshot": current,
            "changed_by": changed_by,
            "reason": reason,
            "timestamp": datetime.utcnow(),
        }
        db[f"{collection}_history"].insert_one(history_entry)
    # Phase 2: 写入新版到主集合（带版本号）
    update["$set"]["version"] = (current.get("version", 0) if current else 0) + 1
    db[collection].update_one(query, update, upsert=True)
    return {"status": "ok", "version": update["$set"]["version"]}
```

### conflict_detection 规则

| 类型 | 触发条件 | 处理方式 |
|------|---------|---------|
| 战力膨胀 | 战力提升 > 当前级别 3 级 | 标记需 power-control 审核 |
| 时间线矛盾 | 新增事件日期与已有事件冲突 | 标记需 timeline 调整 |
| 世界观突破 | 新增规则与 world_bible 规则相悖 | 标记需 lore 确认 |
| 角色记忆覆盖 | 同一字段被两个来源同时修改 | 保留最新版本，标注冲突 |

---

## Profile 结构（V3 最终版）

### 核心 Profile（必须创建，V3 新增 4 个 + 升级 2 个）

| # | Profile | 来源 | 职责 |
|---|---------|------|------|
| 1 | **orchestrator** | V1→V2→V3 升级 | 总控调度、ARC 周期管理、V3 五层调度 |
| 2 | **memory-manager** | V2 | MongoDB 写入唯一入口、冲突检测、摘要生成、版本控制、event_log 记录 |
| 3 | **arc-manager** | V3 新增 | 四层 ARC 规划（World→Phase→Beat→Chapter）、动态调整 |
| 4 | **lore** | V2 | 世界观圣经维护、规则版本控制、史实一致性 |
| 5 | **character** | V1→V2 升级 | 角色档案管理（不变信息） |
| 6 | **character-state-agent** | V3 新增 | 角色动态状态机（每章更新情绪/信任/战力/关系图） |
| 7 | **world-simulator** | V3 新增 | 世界状态模拟器（经济/舆论/势力因果链） |
| 8 | **timeline** | V2 | 全局时间线维护、事件排序 |
| 9 | **power-control** | V2 | 战力体系维护、升级路径设计、膨胀检测 |
| 10 | **draft-main** | V1→V2 升级 | 主线正文写作（基于 context packet） |
| 11 | **draft-action** | V2 | 战斗/高潮/战争场景专用 |
| 12 | **draft-romance** | V2 | 感情线/情感场景专用 |
| 13 | **foreshadow-manager** | V3 新增 | 伏笔队列管理、deadline 监控、强制回收提醒 |
| 14 | **editor** | V1→V2 升级 | 两遍审校（微观+宏观全局一致性） |
| 15 | **live-validator** | V3 新增 | 7 维实时一致性校验（金额/战力/时间线/称呼/人设/地点/物品） |
| 16 | **anti-fatigue** | V3（升级自 anti-repetition） | 七维疲劳检测、干预策略、与 arc-manager 联动 |
| 17 | **compliance** | V1 保留 | 番茄平台合规审查 |
| 18 | **ops** | V1 保留 | 发布运营、标题定稿、连载节奏 |
| 19 | **analytics** | V2 | 数据反馈、爽点效率分析、市场趋势、V3 疲劳报告 |

> **为什么是 15 个而不是 26 个？** 26 个 profile 的维护成本（API key 同步、SOUL.md 更新）和调用开销（每轮 session 切换成本）在实际操作中超过了收益。15 个覆盖了所有核心功能域，且每个 profile 有明确独立的职责边界。draft-{action,romance} 作为独立 profile 是为了让战斗和感情场景得到专业级处理，而不是混在主线正文里一笔带过。

---

## V3 Pipeline（7 层 17 阶段）

### 说明

V3 Pipeline 在 V2 的 13 阶段基础上，新增了 Context Packet 恢复（Step 0）、实时校验（Step 7）、世界/角色状态更新（Step 10-11）、事件溯源（Step 12）和检查点保存（Step 15-16）。详细执行流程已在上方「V3 执行流程（单 ARC 循环）」节定义。

以下保留 V2 各阶段的详细说明作为参考——V3 运行时在对应节点调用这些阶段。

### 阶段 1: ARC Planning（剧情弧规划）

**负责 Agent**: arc-planner
**输入**: 项目目标（字数、类型、基调）
**输出**: 写入 `arcs` collection

ARC 结构（500 万字版）：

```text
ARC 1:      起点觉醒    (ch001-ch080)   8万字   冲突: 身份危机
ARC 2:      势力初显    (ch081-ch180)   10万字  冲突: 势力博弈
ARC 3:      中期考验    (ch181-ch300)   12万字  冲突: 信任与背叛
ARC 4:      格局重塑    (ch301-ch420)   12万字  冲突: 阵营分裂
ARC 5:      终局序幕    (ch421-ch550)   13万字  冲突: 终极威胁显现
ARC 6:      大结局       (ch551-ch600)  5万字   冲突: 最终决战
```

每个 ARC 必须包含：
- **独立主题** — 每个 ARC 有自己的核心命题（身份、权力、牺牲...）
- **独立反派** — 每个 ARC 有主要的对抗力量
- **冲突升级** — 下一个 ARC 的冲突层级必须高于上一个
- **新坑 + 回收旧坑** — 每个 ARC 至少埋 3 个新伏笔、回收 2 个旧伏笔
- **余波缓冲** — 每个 ARC 结尾 3-5 章为过渡，让读者喘口气

### 阶段 2: World Building（世界观构建）

**负责 Agent**: lore
**输入**: ARC 规划、已有 world_bible
**输出**: 更新 `world_bible` collection

规则：
- world_bible 有 `version` 字段，每次修改递增版本号
- draft agent **不允许**在正文中新增世界规则
- 所有新增设定必须经 lore 备案
- 跨 ARC 的世界观变化必须记录变更原因

### 阶段 3: Character Setup（角色准备）

**负责 Agent**: character
**输入**: ARC 规划、已有 characters
**输出**: 更新 `characters` collection

每个角色必须有：
- `first_appearance`（首次出场章节）
- `last_appearance`（最后出场章节）
- `growth_arc`（完整的成长轨迹规划）
- `memory_summary`（浓缩记忆，每次 ARC 结束后更新）

### 阶段 4: Timeline Generation（时间线生成）

**负责 Agent**: timeline
**输入**: ARC 规划 + characters
**输出**: 写入 `timeline` collection

时间线粒度：每章 1 条事件记录
关键事件（importance=5）需要被所有 draft agent 知晓

### 阶段 5: Power-Control Setup（战力体系）

**负责 Agent**: power-control
**输入**: ARC 规划 + world_bible
**输出**: 更新 world_bible.power_system

战力原则：
- 每 ARC 主角战力提升不超过 1-2 个小级别
- 反派战力始终比主角高半个级别（制造压力感）
- 战力突破必须有代价（受伤、失去某物、时间代价）
- 500 万字的战力爬坡表预规划

### 阶段 6: Draft Writing（正文写作）

**负责 Agent**: draft-main / draft-action / draft-romance
**输入**: 当前 ARC 的 arcs + timeline + chapter_memory（最近5章）+ characters（当前章角色）
**输出**: 正文文件 + 更新 `chapter_memory`（经 memory-manager）

写作前必须执行的 MongoDB 查询：

```python
# 每次写作前的标准加载
context = {
    "arc": db["arcs"].find_one({"project_id": pid, "arc_id": current_arc}),
    "recent_chapters": list(db["chapter_memory"].find(
        {"project_id": pid}).sort("chapter", -1).limit(5)),
    "active_characters": list(db["characters"].find(
        {"project_id": pid, "status": "active"})),
    "timeline_events": list(db["timeline"].find(
        {"project_id": pid, "chapter": {"$gte": current_ch - 5, "$lte": current_ch}})),
    "active_foreshadows": list(db["foreshadow"].find(
        {"project_id": pid, "status": "active"}))
}
```

**Draft Agent 禁止做的事：**
- ❌ 新增世界规则（必须走 lore）
- ❌ 修改角色核心设定（必须走 character）
- ❌ 跳过时间线（必须按章节顺序写入）
- ❌ 战力无故升级（必须走 power-control）

### 阶段 7: Editor（两遍审校）

**负责 Agent**: editor
**输入**: 正文文件 + MongoDB 数据
**输出**: 修复项 + patch

**1st Pass** — 微观审校（逐章）：
- 字数达标（每章 2000+ 字）
- 对话比例（男频 40%+，女频 40-50%）
- 情节密度（每章至少 1 个冲突/推进）
- 章末钩子强度
- 格式合规（引号统一、段落间距）

**2nd Pass** — 宏观一致性（跨章扫描）：
- 时间线一致性（对比 timeline collection）
- 角色名/排行/称呼一致性（对比 characters collection）
- 战斗力数值一致性（对比 power_system）
- 伏笔回收进度（对比 foreshadow collection）
- 场景跳跃衔接
- POV 稳定性

2nd pass 必须读取 MongoDB 数据进行交叉验证，不能只靠上下文。

### 阶段 8: Anti-Repetition（防重复）

**负责 Agent**: anti-repetition
**输入**: 本章正文 + 历史 50 章 chapter_memory
**输出**: 写入 `anti_repetition` collection

检测维度（7 维扫描）：

| 维度 | 检测内容 | 阈值 |
|------|---------|------|
| 对白重复 | 相似句式/情绪对白出现频率 | >3 次/10章 |
| 剧情模式重复 | 打脸/逆袭/升级等桥段结构相似度 | >70% |
| 爽点重复 | 同一类爽点的密度 | >1 次/5章 |
| 副本/场景重复 | 类似场景/副本出现的间隔 | <10章 |
| 情绪曲线重复 | 章节情绪起伏模式 | 连续 3 章同模式 |
| 人物互动模式 | 同一组角色类似互动 | >2 次/ARC |
| 战斗模式 | 战斗描写结构/节奏相似 | >70% |

输出格式：
```text
【Duplicate Score】: 0.22 (阈值 0.30，通过)
【Duplicate Items】:
  1. [中风险] ch047 的"被打脸→震惊→反杀"模式与 ch023 相似度 68%
  2. [低风险] 主角说"就这？"已出现 4 次（ch015, ch027, ch036, ch047）
【Rewrite Suggestions】:
  1. ch047 反杀方式改为智取而非硬刚
  2. 替换"就这？"为"看来我高估你了"
【Status】: PASS
```

若 duplicate_score > 0.30，退回 editor 重写。

### 阶段 9: Compliance（合规审核）

**负责 Agent**: compliance
**输入**: 通过 anti-repetition 的正文
**输出**: 合规报告

检查项（与 V1 保持一致）：
- 标题党风险
- 色情低俗内容
- 未成年人内容
- 暴力血腥描写
- 封面合规

评分体系：<50 高风险 / 50-69 中风险 / 70-89 低风险 / 90-100 安全

### 阶段 10: Ops（发布运营）

**负责 Agent**: ops
**输入**: 合规后的正文
**输出**: 运营方案

必须包含：
- 最终章节标题（15 字以内，事件+结果格式）
- 章节简介（50 字）
- 更新节奏建议
- 付费节点分析（番茄小说免费阅读模式下，推荐节点位置）

### 阶段 11: Memory Manager（记忆写入）

**负责 Agent**: memory-manager
**输入**: 本章所有产出（正文、character_changes、power_changes、timeline_events）
**输出**: 写入 MongoDB 所有相关 collection

单章完成后，memory-manager 执行一次**批量提交**：

```python
# 单次提交 = 更新多个 collection
batch_write = {
    "chapter_memory": {"project_id": pid, "chapter": n, ...},
    "timeline": [{"project_id": pid, "chapter": n, "event": e, ...} for e in events],
    "characters": [{"project_id": pid, "character_id": cid, ...} for c in updates],
    "foreshadow": [{"project_id": pid, "foreshadow_id": fid, ...} for f in new_shadows],
}
# 一次性写入，保证原子性

> **版本化说明**：批量提交自动触发 `save_with_version`，涉及 `characters_history`、`world_bible_history`、`chapter_memory_history`、`arcs_history` 四个历史集合。策略：history 无事务批量 `insert_many`（最佳努力），主集合事务保证原子性。详见 `soul-memory-manager.md`。
```

### 阶段 12: Analytics & Refresh（数据反馈）

**负责 Agent**: analytics
**触发**: 每完成 1 个 ARC（约 10-15 万字）
**输入**: 最近 ARC 的 chapter_memory + anti_repetition 数据
**输出**: ARC 质量报告 + 下一 ARC 调整建议

分析维度：
- 爽点密度：每万字有几个爽点
- 情绪曲线：章节情绪起伏是否合理
- 读者疲劳指数：相似模式的重复频率
- 升级速度：战力/地位提升是否过快或过慢
- 伏笔回收率：已回收 vs 已埋没回收
- 角色活跃度：每个角色的出场频率

Refresh 触发：
- 疲劳指数 > 0.7 -> 建议调整节奏，加入新冲突方向
- 爽点密度 < 2/万字 -> 建议增加爽点密度
- 伏笔回收率 < 30% -> 建议回收一些旧伏笔

### 阶段 13: 下一 ARC（循环）

**负责 Agent**: arc-planner（基于 analytics 的反馈）
**输入**: analytics 报告 + 当前 arcs 状态
**输出**: 下一 ARC 规划

### 阶段 14: MongoDB 持久化（收尾写入 — 必选）

每次 orchestrator pipeline 执行完成后，**必须执行此阶段**将产出写入 MongoDB。这是所有 novel-factory 操作的强制收尾步骤，不可跳过。

**触发时机**: Editor → Compliance → Ops 完成后，作为最终写入动作。

**负责 Agent**: 当前主 agent（Hermes）

**输出**:
| 数据 | 目标库 | 目标集合 | 写入方式 |
|------|--------|---------|---------|
| 正文 | `novel` | `chapters` | upsert（novelName + chapterNumber） |
| 小说元数据 | `novel` | `novels` | upsert（title） |
| 草稿版正文 | `novel_factory` | `chapter_memory` | upsert（project_id + chapter） |
| 章节记忆摘要 | `novel_factory` | `chapter_memory` | 更新 summary/hook 字段 |
| 角色数据 | `novel_factory` | `characters` | upsert（project_id + name） |
| 大纲 | `novel_factory` | `arcs` | upsert（project_id + arc_id） |

#### 方法一：novel-factory CLI 输出同步（推荐，日常使用）

`novel-factory new` 和 `novel-factory continue` 的输出在 `/root/novel-factory/<slug>/` 目录下（draft/chapter-*.md 格式），**不会**自动写入 `novel` 数据库。每次 CLI 操作完成后，必须手动执行：

```bash
python3 /root/.hermes/skills/content-creation/hermes-novel-factory/scripts/sync-novel-to-mongodb.py \
  --proj-dir <slug>
```

该脚本自动完成：\n1. 从 `ops/synopsis.md` → `ops/summary.md` → `ops/blurb.md` → `ops/cover-copy.md` 依次搜索 `《》` 提取书名\n2. 从 `ops/synopsis.md`/`synopsis.md` 提取梗概（synopsis），从 `blurb.md` 提取一句话简介（description）\n3. 从 `outline.md` 提取角色和章节标题列表\n4. 读取 `draft/chapter-*.md` 逐章写入 `novel.novels` + `novel.chapters`（upsert，可重复执行）\n5. 更新字数统计和角色数据

> **用户强制要求（2026-05-17）**：所有 novel-factory 产出 **必须** 同步到 `novel` 数据库，格式遵循现有 schema。本地文件和 MongoDB 必须保持同步。

**`novel.chapters` 集合 schema（与 `novel_factory` 不同，请注意）**：
```python
{
    "novelName": "深夜小馆的温暖守则",         # 字符串，与 novels.name 一致
    "chapterNumber": 1,                       # int
    "title": "第1章 深夜十点",                 # 标题字符串
    "filename": "ch001_深夜十点.md",           # 原始文件名（可为空）
    "content": "# 深夜十点\n\n十点整，林暖推开小馆的木门。...",  # 完整Markdown
    "chapterEndNotes": "",                    # 章末注释（通常为空）
    "version": "v1",                          # 版本标记
    "wordCount": 2857                         # int
}
```

完整 schema 参考 `references/mongodb-schema.md`。

#### 方法二：V1 多 agent 模式同步（仅用于 /root/chapterN_edited.txt 旧格式）

当 V1 pipeline 产生 `/root/chapterN_edited.txt` 格式的文件时：
```bash
python3 /root/.hermes/skills/content-creation/hermes-novel-factory/scripts/persist-to-mongodb.py
```
该脚本从 `ops_package.txt` 或第一章首行推断书名，写入 `novel` 数据库。**不提交 GitHub**。

---

## 执行策略（500 万字版）

### ARC 级执行（核心循环）

```
for each ARC:
  Step 1: arc-planner → 输出 ARC 规划 → memory-manager 写入 arcs
  Step 2: lore → 更新 world_bible（如需）
  Step 3: character → 准备角色状态
  Step 4: timeline → 生成时间线骨架
  Step 5: power-control → 确认战力路径

  for each 3-chapter batch in ARC:
    Step 6: draft-main/action/romance → 写 3 章（并行）
    Step 7: editor 1st pass → 微观审校
    Step 8: editor 2nd pass → 宏观一致性（读 MongoDB 验证）
    Step 9: anti-repetition → 防重复检测
    Step 10: compliance → 合规
    Step 11: memory-manager → 批量写入 MongoDB

  Step 12: analytics → ARC 质量报告
  Step 13: refresh? → 是否调整方向
```

### 并行策略

| 阶段 | 并行度 | 说明 |
|------|--------|------|
| ARC 规划 | 串行 | 依赖上游输出 |
| 世界观/角色/时间线/战力 | 可并行（4 个 delegate_task） | 但 max_concurrent=3，所以分 2 批 |
| 正文写作 | 3 章/批（max_concurrent=3） | 每个 ARC 循环 |
| editor 两遍 | 串行 | 2nd pass 依赖 1st pass |
| anti-repetition + compliance + ops | 可并行（3 个） | 互不依赖 |

### 每 50 万字大刷新

```
触发条件: total_words % 500000 == 0
执行:
  1. analytics → 全项目质量报告
  2. arc-planner → 重新审视后半段 ARC 规划
  3. lore → 世界观一致性审计
  4. character → 所有角色成长轨迹审计
  5. memory-manager → 全库一致性检查
```

## 多轮次/季式创作策略（跨会话写作 + Context Packet 恢复）

300 万字不需要一次性写完。V3 的设计允许跨多个独立 Hermes 会话续写，每次只写一个 ARC（约 8-12 万字）。这就是用户问的「能不能分开多次创作」——答案是肯定的，而且这才是正确的用法。

### V3 核心改进：Context Packet 恢复系统

V2 的续写只依赖 MongoDB 数据加载（查 projects → chapter_memory → characters → timeline）。这能保证数据完整，但**不能保证模型理解当前状态**。V3 引入 Context Packet 作为续写的桥梁：

```
[MongoDB] → 读取最新状态 → 组装 Context Packet → 注入 draft agent → 续写
                    ↑                                         ↓
              [snapshot_store]                        [event_log] → 写入
```

Context Packet 包含：
- world_state（当前世界快照）
- character_states（所有活跃角色的当前状态）
- active_plot_threads（进行中的剧情线 + 到期伏笔）
- last_10_chapters_summary（最近 10 章摘要）
- foreshadow_queue（到期需回收的伏笔清单）
- last_arc_summary（上一个 ARC 的完成情况）
- anti_fatigue_report（当前疲劳指数）

每次 continue 前执行 context-packet 系统，而不是依赖模型「我记得」。详见 `references/context-packet-system.md`。

### 为什么不能一次性写 300 万字

| 风险 | 表现 | 根因 |
|------|------|------|
| 模型疲劳 | 单次会话太长，模型开始前后矛盾 | 上下文窗口有限，长会话尾部质量下降 |
| 成本不可控 | 300 万字单次生成的 token 消耗巨大 | 即使按 1:4 的输入输出比，也 > 1000 万 token |
| 无中间检查点 | 写到第 200 万字发现方向错了，回退成本极高 | 没有 ARC 级的 analytics 反馈循环 |
| 创作心态 | 300 万字的目标在一开始就让人望而却步 | 分成 25-30 个 ARC，每个 ARC 只是写 10 万字 |

### 正确的节奏

```
每个 Hermes 会话 = 1 个 ARC（10-12 万字，约 40-60 章）
                    ↓
每 3 个 ARC = 1 季（约 30-35 万字）
                    ↓
每 5 季 = 完整故事（约 150-175 万字，中型小说）
                    ↓
每 10 季 = 超长篇（约 300-350 万字）
```

### 续写流程（跨会话）

```
会话 1: novel-factory arc '诡异游戏' ARC-005  → 写 10-12 万字
  → sync-novel-to-mongodb.py --proj-dir <slug>   ← MongoDB 持久化（必选）
  → 关闭会话

（下次打开新会话）
会话 2: 读取 MongoDB 最新状态
  → 运行 analytics 回顾已完成 ARC
  → arc-planner 规划下一 ARC
  → novel-factory arc '诡异游戏' ARC-006
  → sync-novel-to-mongodb.py --proj-dir <slug>   ← 再次持久化
  → 关闭会话
```

### 关键原则

| 场景 | 做法 |
|------|------|
| **新会话续写** | 先查 `projects` 取 `current_arc`，再查 `chapter_memory` 最近 5 章回忆状态 |
| **跨月/跨年续写** | timeline + characters 完整保留，不会丢失任何设定 |
| **调整方向** | 运行 analytics 检查现状 → 通过 `arcs` collection 新增或修改 ARC 规划 |
| **分季（Season）** | 在 `projects.metadata.season` 中标记季节号。新季可重启 draft 节奏但继承世界观 |
| **换平台/换风格** | 通过 `projects` 的 `metadata` 字段记录，不影响核心数据 |

### 停止点与恢复点

**好的停止点（每 ARC 完成后）：**
- `sync-novel-to-mongodb.py` 已执行（数据库已写入）
- analytics 已写入 `anti_repetition` collection
- 所有角色的 `last_appearance` 更新到最新章
- `projects.total_words` 和 `projects.current_arc` 已更新
- 留下一个明确的「余波缓冲」章节（ARC 结尾 3-5 章过渡）
- **V3**: event_log 最后 10 条已确认写入
- **V3**: snapshot_store 已更新
- **V3**: world_state 和 character_states 已更新到最后章节

**下次启动时自动恢复（V3 Context Packet 模式）：**
1. 读 `projects` → 知道当前 ARC、总字数、项目状态
2. 读 `event_log` 最后 50 条 → 最近的创作活动全景
3. 读 `snapshot_store` → 恢复世界状态快照
4. **组装 Context Packet** → world_state + character_states + active_plot_threads + last_10_chapters + foreshadow_queue
5. 读 `arc_plans` → 当前 ARC 规划 + 剩余章节数
6. 读 `anti_fatigue` → 疲劳检测报告
7. analytics → 基于历史数据生成推荐方向
8. **Context Packet 注入 draft agent** → 开始续写

---

## CLI 参考（V3 完整版）

> 完整 V3 CLI 使用说明（含所有子命令参数、调用链、时间预算）见 `references/v3-cli-reference.md`。
> **跨技能统一 CLI**：另有 `novel` 统一入口（`~/.local/bin/novel`）覆盖全部 11 个子技能（factory/reconstruct/judge/refine/voice/lore/state/audit/validate/count/init-db），搭配 Flask API 端点和 Web 控制台页面。完整参考见 `references/unified-cli-reference.md`。

| 子命令 | 完整用法 | 功能 | 内部调用链 |
|--------|---------|------|-----------|
| `new` | `novel-factory new '<需求>'` | 启动新项目 + 初始化 V3 集合 | `init_collections.py` → orchestrator |
| `continue` | `novel-factory continue <项目名> [章节]` | 中断恢复 + Context Packet 注入 | `resume-project.py` → `build-context-packet.py` → orchestrator → draft → `validate-chapter.py` → `snapshot-manager.py` → `event-log-writer.py` |
| `status` | `novel-factory status <项目名>` | 显示项目状态和 V3 recovery 策略 | `resume-project.py` status |
| `snapshot` | `novel-factory snapshot <项目名> <章节>` | 手动保存状态快照 | `snapshot-manager.py` save |
| `validate` | `novel-factory validate <项目名> <章节>` | 7 维一致性校验（自动从 DB 取内容） | `validate-chapter.py` check |
| `event` | `novel-factory event <项目名> <类型> <章> [--data JSON]` | 手动写入事件日志 | `event-log-writer.py` log |
| `arc` | `novel-factory arc <项目名> <arc_id>` | 直接写入指定 ARC | `build-context-packet.py` → orchestrator |
| `refresh` | `novel-factory refresh <项目名>` | 触发全量刷新/重整理 | → orchestrator（analytics → 审计） |
| `-h` | `novel-factory --help` | 显示帮助信息 | — |
| `*`(默认) | `novel-factory '<任意需求>'` | 向后兼容，直接路由 orchestrator | → orchestrator |

### 典型使用场景

| 场景 | 命令 | 说明 |
|------|------|------|
| **新书启动** | `novel-factory new '男频系统流，3万字，开局爽'` | 先跑初始三阶段 + 开头几章，超时后用 continue 接续 |
| **日常续写** | `novel-factory continue '诡异游戏'` | 自动恢复上次中断位置，续写下一章 |
| **指定章节续写** | `novel-factory continue '诡异游戏' 136` | 从第 136 章开始写 |
| **检查项目状态** | `novel-factory status '诡异游戏'` | 看最后一章、恢复策略、Context Packet 摘要 |
| **校验已写内容** | `novel-factory validate '诡异游戏' 135` | 检查第 135 章是否有 7 维矛盾 |
| **保存快照** | `novel-factory snapshot '诡异游戏' 135` | 手动触发状态快照（系统每 100 event 自动保存） |
| **批量写入新 ARC** | `novel-factory arc '诡异游戏' ARC-005` | 整个 ARC 一次性写完 |

> 更多实操记录：`references/orchestrator-run-walkthrough.md`（V3 通用）、`references/wan-yin-dao-zhu-new-run.md`（300万字修仙项目，2026-05-19）

---

## 与 V1 的兼容性

V2 完全兼容 V1 已有的 `novel` 数据库（192.168.2.30:27017/novel）：

| V1 产物 | V2 中如何处理 |
|---------|-------------|
| 已有小说 | 导入到 novel_factory 作为已完成 ARC（见下方迁移指南） |
| 已有 novels/chapters collection | 保留不动，V2 的最终成品仍存回 chapters |
| 已有 SOUL.md 文件 | V2 使用升级版 SOUL.md（参考 references/） |
| V1 CLI 脚本 | V2 升级为 multi-command CLI |

### 数据维护与质量审计（Data Maintenance & Audit）

本流程覆盖三个场景：
- **V1→V2 迁移后修复**：某些 collection 字段为空/缺失
- **ongoing 质量审计**：续写新 ARC 前，对已有数据的全面检查
- **全链路内容一致性修复**：修正正文中跨章节的数字/名称/事件错误（见下方 Step 9）

**总原则**：按依赖顺序执行，先读后写，不改正文内容只修元数据。

#### Step 0: 全量审计（有多少问题）

在执行任何修复之前，先做全面数据扫描，明确问题范围：

```python
# 审计维度
audit_items = [
    'ARC metadata completeness',       # arcs.core_conflict/major_twists/ending_hook
    'foreshadow database health',      # 真实伏笔数量 vs 占位符
    'chapter hook coverage',           # hooks 非空率
    'character data completeness',     # growth_arc/goals/relationships
    'character presence audit',        # 正文出场 vs 摘要提及的偏差
    'timeline density',                # 每章最少事件数
    'emotion_tone diversity',          # 全篇同色 vs 合理单一
    'character departure scan',        # 哪些角色无故消失
    'foreshadow callback urgency',     # 未回收伏笔的等待章数
]
```

> 审计脚本模板见 `references/data-maintenance-workflow.md`。

#### Step 1: Character Presence Audit（角色出场审计）

这是最容易被忽略的坑。V1 迁移后，`chapter_memory.summary` 只有正文前 200 字截取，**没有标注出场角色**。后果：ARC planner 和 analytics 无法准确知道哪些角色在哪些章活跃。

**方法**（逐章扫描 `content` 全文，角色名匹配）：

```python
for char_name, aliases in char_map.items():
    if any(a in content for a in aliases):   # 正文出场
        if not any(a in summary for a in aliases):   # 摘要未提
            needs_fix.append((ch, char_name))
```

**关键点**：
- 别名必须覆盖：沈从越/沈教授、陆沉/图书馆老人/馆长、赵铁/铁哥、老钱/钱叔
- 首次出场标记 `★`（如"方晴★"），让系统能区分首次登场
- 只修"正文出场但摘要未提"的情况，不修"正文也不出场"的——那可能是未来 ARC 角色
- 摘要约 200 字，追加格式：`\n\n出场角色：林远、顾晚、方晴`

**典型数据**（诡异游戏 135 章为例）：
```
方晴: 89章出场, 29章摘要提及 → 漏60章（最严重）
顾晚: 71章出场, 24章摘要提及 → 漏47章
赵铁: 61章出场, 17章摘要提及 → 漏44章
林远: 134章出场, 100章摘要提及 → 漏34章
```

#### Step 2: ARC Metadata Repair（ARC 元数据修复）

同现有「基建修复」步骤 1 的流程不变。

#### Step 3: Foreshadow Database（伏笔数据库）

同现有「基建修复」步骤 2 的流程不变。

注意：`foreshadow.collection` 的 `$jsonSchema` 要求 `project_id` 在每条 doc 创建时就包含，不能在 `insert_many` 前才统一赋值。

#### Step 4: Chapter Hooks（章末钩子）

同现有「基建修复」步骤 3 的流程不变。

#### Step 5: Character Data Fill（角色数据）

同现有「基建修复」步骤 4 的流程不变。

#### Step 6: Character Departure Documentation（角色退场记录）

在 timeline 中添加角色退场/留守事件。方法：

1. **找到最后一次 ACTIVE 出场** — 检测包含角色名的行是否有对话引号「」、动作动词（说/走/看/拿）、或长度 >20 字的描述。排除纯回忆/与他无关的旁白。
2. **基于正文添加事件** — 只能记录正文中实际发生的事。如「老钱指路后分道扬镳」「赵铁留守仓库整理物资」。
3. **检查间接提及** — 退场后是否还有其他章节在回忆/旁白中提到该角色，也在 timeline 补事件。

**注意**：不要编造正文中没有的信息（如"他去了远方"如果正文没写就不要加）。退场事件只做记录，不做剧情创作。

#### Step 7: Timeline Enrichment（时间线扩充）

确保每章至少 2 个事件（标题事件 + 补充事件）。

**补充事件提取方法**：
- 读取每章 `content` 全文
- 找出核心剧情推进点（冲突、发现、抉择、转折）
- 写入 `timeline` 集合：`{project_id, chapter, event, importance(2-5), arc_id}`
- 去重：检查 `existing_texts` 避免同章内重复事件

**重要性分级**：
- 1: 标题/概要事件（已有）
- 2: 补充推进事件（新增）
- 3: 关键转折/发现
- 4: 重大事件（战力突破、角色死亡、世界观级发现）
- 5: 全书级高潮

#### Step 8: Foreshadow Callback Planning（伏笔回调计划）

不要直接修改 foreshadow 的 `status` 字段——那应该由 ARC 续写时自然触发。做的是：

1. **计算等待章数**：`pending_chs = current_last_chapter - setup_chapter`
2. **紧急度排序**：
   - 🔴 >80 章：ARC-005 前 15 章必须重提/回调
   - 🟡 50-80 章：ARC-005 前半段安排
   - 🟢 30-50 章：ARC-005 中后段
   - 🟢 <30 章：ARC-005 后半段或 ARC-006
3. **更新 foreshadow 文档**：添加 `suggested_callback_arc`、`suggested_callback_ch`、`urgency` 字段
4. **输出计划文档**：GitHub 持久化，供 ARC-005 写作时直接参考

**关键原则**：
- 7 条最紧急的伏笔（等待 >80 章）适合用「闪回+新线索」的方式在 ARC-005 开篇重提，不需要专门写回调章节
- 伏笔回调不应该打断 ARC 主线的节奏——用对话/内心独白/环境细节自然唤起
- 所有 callback 计划写入 MongoDB foreshadow 集合 + GitHub 文档双重备份

> 回调计划文档模板见 `references/data-maintenance-workflow.md`。

##### Step 9: Full-Chain Content Consistency Fix（全链路内容修复）

**适用场景**：正文中存在跨章节的数字/名称/金额/事件描述不一致（如「返三亿」的标题但正文写「三百万」），需要全量扫描后统一修正。

**不要在第一次读到问题时就动手改第1章**——先全面搞清楚波及范围。

**标准流程**：

1. **全量扫描** — 对以下所有渠道做「问题关键词」搜索，不遗漏：
   - MongoDB `chapters` 集合（逐章 content 全文搜索）
   - MongoDB `novels` 集合（synopsis / description / brief 字段）
   - 本地 /root/ 下所有 `.txt` / `.md` 文件
   - Web UI 渲染是否同步（登录→查看小说详情页）

2. **语境分类** — 对于每个命中的位置，判断它属于哪种情况：
   - **同事件引用**：前后文明显指的是同一个事件/数字（必须统一改）
   - **独立新事件**：剧情推进后出现了不同的金额/数字（保留不动）
   - **回忆/重复提及**：角色在后续章节回忆同一场景（必须统一改）
   - **数字公式**：涉及数学计算的公式字段（必须改，数字计算错误会让读者出戏）

3. **多位置同步更新** — 所有「同事件引用」「回忆/重复提及」「数字公式」的命中点，一次性全改完：
   - MongoDB chapters：`update_one` 或全文 `replace_one`
   - MongoDB novels：`$set` synopsis / description
   - 本地文件：`sed -i` 或 Python 替换
   - GitHub 文件（如有）：同步 commit

4. **数据验证** — 改完后重新扫描确认：
   - 旧关键词已清零（除非是「独立新事件」的合理保留）
   - 新关键词出现在预期位置
   - 字数/结构未受影响（只替换关键数字，不删不减段落）

5. **Web 端验收** — 刷新小说详情页和章节阅读页，确认渲染正确

**Pitfalls（全链路修复专属）**：
- ❌ 不要凭记忆判断——只相信全文 grep 结果。模型认为"后面的章节都不涉及"但实际 grep 出来 3 处。
- ❌ 不要一次性改所有命中——先分类，再改。把「独立新事件」也改了会导致新矛盾。
- ❌ 不要改完不验证——改后要 grep 确认旧关键词清零。
- ✅ 存疑的命中点优先改——让读者出戏的错误（金额、数字、重要事件）宁可多改也不要漏改。
- ✅ 全链路修复完成后，运行一次 analytics 检查情感色调/字数统计是否受影响（替换不会，但删改段落时可能）。

**执行参考**（本环境用过的 Python 扫描模式）：
```python
import pymongo, re
uri = 'mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/novel?authSource=admin'
db = pymongo.MongoClient(uri)['novel']
for ch in db.chapters.find({'novelName': '小说名'}).sort('chapterNumber', 1):
    c = ch.get('content',''); n = ch['chapterNumber']; t = ch.get('title','')
    ms = list(re.finditer(r'.{0,45}关键词.{0,45}', c))
    if ms:
        for m in ms:
            print(f'ch{n}: ...{m.group().replace(chr(10)," ")}...')
```

### 修复完成后的收尾

```python
# 更新 project 状态
db['projects'].update_one(
    {'project_id': pid},
    {'$set': {
        'last_maintenance': datetime.now(),
        'summary_fixed': True,
        'timeline_enriched': True,
        'callback_plan_created': True,
    }}
)
# 清理旧 analytics 报告
db['anti_repetition'].delete_many({'project_id': pid})
```

保存回调计划文档到 GitHub 后，提供直接下载链接。完整数据维护工作流见 `references/data-maintenance-workflow.md`。

### V1 → V2 迁移指南（从 novel 数据库导入已有小说）

1. **读取 V1 数据** — `novels` 查 `name`，`chapters` 查 `novelName` 按 `chapterNumber` 排序
2. **生成 project_id** — 格式 `proj_{slug}_{uuid[:8]}`，例如 `proj_gui-yi-you-xi_d3acfcdd`
3. **划分 ARC** — 对已有内容按 35 章/ARC（约 8-10 万字）划分，用 V1 已有卷结构命名（卷一·XXX）
4. **写入 projects** — 注意 `created_at`/`updated_at` 为 **字符串**，`target_words` 为 **int**
5. **写入 characters** — V1 的 `title`→`role`, `traits`→`personality`, `ability`→`abilities`(数组), `desc`→`memory_summary`
6. **写入 world_bible** — **所有字段为数组类型**，不能是 dict
7. **写入 chapter_memory** — 用 `chapter`(int) 作为键（不是 `chapter_number`），`summary` 截取前 200 字
8. **写入 timeline** — 历史事件（importance=2）+ 每章事件（importance=1）
9. **初始化 foreshadow + anti_repetition** — 空状态占位
10. **全量校验** — 章节数、字数、内容（抽检 5+ 章全文对比）、ARC 覆盖、字段完整性

> 完整 schema 定义见 `references/novel-factory-v2-schema.md`。迁移时必须严格遵守每个集合的 `$jsonSchema` 校验，否则 MongoDB 返回 WriteError code 121。

**校验清单**:
```python
# 迁移后必须验证的项
checks = {
    '章节数一致': len(v2_chs) == len(v1_chs),
    '字数一致': sum_v2_words == sum_v1_words,
    '内容一致': random.sample 5章全文比对通过,
    'ARC覆盖': sum(arc.chapter_count) == total_chapters,
    '角色数一致': len(v2_chars) == len(v1_chars),
    '字段完整': 所有required字段存在,
}
```

---

## 触发规则

| 场景 | 触发链 | 说明 |
|------|--------|------|
| **新书启动(300万+字)** | arc-planner → lore → character → timeline → power-control → 循环 | 完整多 ARC 规划 |
| **续写下一卷** | analytics → arc-planner → lore/character/timeline → draft | 基于上一卷数据 |
| **日更（3章）** | draft → editor 1st+2nd → anti-repetition → compliance → memory-manager → ops | 单日循环 |
| **卡文时** | analytics → lore/character → arc-planner | 回头找方向 |
| **每50万字刷新** | analytics → arc-planner → lore → memory-manager audit | 大周期维护 |

---

## Pitfalls（V2 新增 + V1 保留）

- **`novel-factory new` 有超时风险**：即使是 3 万字项目，orchestrator 也需要跑完 Research → Outline → Character → Draft × N → Editor × N → ... 的完整流水线。实测 3 万字（约 20 章）在第 1 章 Editor 阶段超时（600s 的 `delegation.child_timeout_seconds` 限制）。正确做法是：`novel-factory new` 跑完初始三阶段（Research/Outline/Character）和开头几章 → **超时后** 用 `novel-factory continue '项目名'` 续写后续章节。任何超过 2 章的项目都不应期望一次 `new` 写完。

  时间预算参考（基于本环境 CPU+API 实测）：

  | 项目规模 | 预计时间 | 是否适合单次 new | 推荐策略 |
  |----------|---------|-----------------|---------|
  | 1-2 章（约 3000 字） | ~5-8 min | ✅ | 一次 new 即可 |
  | 3 万字（约 20 章） | ~40-60 min | ❌ 必超时 | new → continue |
  | 10 万字（ARC） | ~2-3 小时 | ❌ | new → continue × N |
  | 300 万字 | 3+ 天（不关机） | ❌❌ | 季式发布（见上） |

  每次 `continue` 从上次停下的位置继续（Editor 阶段后自动写下一章），不会丢失任何进度。MongoDB `chapter_memory` 集合中记录最近 5 章的上下文，角色/时间线/伏笔无缝衔接。

### 实操实录（2026-05-19 — 大型修仙项目全态验证，background mode）

下面的实录是 300 万字大型修仙项目「万印道主」的实际运行数据，展示了 `background=true` 模式下的完整行为。

**场景：** `novel-factory new '大型修仙小说，市面通用修仙体系（炼气→筑基→金丹→元婴→化神→大乘），300万字长篇设定，要有独创性的大世界观和新鲜剧情，避免套路化'` （后台进程，background=true）

**总耗时：** ~36分钟（前台看不到输出，但进程持续活跃）
**完成进度：** 5 章全部完成（11,014 字）

| 阶段 | 状态 | 用时 | 说明 |
|------|------|------|------|
| ARC 规划（4个ARC） | ✅ 完成 | ~60s | 道印体系、修仙界是试验场、道争而非力斗 |
| Research（选题/爽点/竞品/前20章钩子） | ✅ 完成 | ~40s | 14,130字 |
| Outline（20章逐章大纲+600章全线分布） | ✅ 完成 | ~155s | 20,665字 |
| Character（主角6阶段+双女主+反派6层） | ✅ 完成 | ~105s | 18,883字 |
| World State 初始化 | ✅ 完成 | ~30s | MongoDB 写入 |
| Foreshadow 规划 | ✅ 完成 | ~30s | 7条伏笔初始化 |
| Draft × 5（ch001-005） | ✅ 全部完成 | ~73s/章 | 对ch001也做了Validator |
| Editor × 5 | ✅ 全部完成 | ~83s/章 | ch001 Editor 精简 17处（2134→1966字） |
| State Update Foreshadow | ✅ 完成 | ~10s | MongoDB 写入 |
| 最终写入项目目录 | ✅ 完成 | — | `/root/novel-factory/xian-xia-shen-hua/` |

**关键行为观察：**

1. **background=true 让 `new` 远超 600s 运行** — 进程持续跑了 36 分钟，没有前台超时中断。`ps aux` 显示 ~3.3% CPU，~290MB RSS。
2. **Clarify 超时后自动批次化** — ch001 写完后，orchestrator 尝试 clarify 用户（等待 120s），超时后自动决策：继续批量写 ch002-005。
3. **每章 pipeline = Draft(73s) → Read → Editor(83s) → State Update** — 时间非常稳定。
4. **项目状态自动推进** — `projects.status` 从「规划完成·待写作」→「连载中」。
5. **任务卡自动生成** — 每个章节都创建了 task-card.md，含详细的逐场景写作指令。
6. **最终文件在项目目录，但 `novel.chapters` 未自动同步** — 需手动运行 `sync-novel-to-mongodb.py`。

**文件产出模式：**
```
/root/novel-factory/xian-xia-shen-hua/
├── ch001_废材道印.md              ← 最终版（已编辑）
├── ch002_万印初现.md
├── ch003_不能说的秘密.md
├── ch004_藏拙之道.md
├── ch005_小试牛刀.md
├── task-cards/
│   ├── project-plan.md
│   ├── arc-plan.md              ← 4个ARC
│   ├── research-card.md         ← 14,130字
│   ├── outline-card.md          ← 20,665字
│   ├── character-card.md        ← 18,883字
│   └── ch00X-task-card.md       ← 每章一个
/root/ch00X_*.txt                ← 临时草稿（每章的 Draft 原始输出）
/root/ch00X_editor.txt           ← 临时编辑稿（Editor 输出）
```

**对比 V2 的 600s 前台模式：**

| 模式 | 前台(terminal) | 后台(background=true) |
|------|---------------|---------------------|
| 超时 | 600s 必超时 | 无限期运行（需 agent 监控） |
| 章节数 | 1-2 章 + 未完成的 Editor | 5 章完整流水线 |
| 监控方式 | 无（前台被锁定） | `ps aux` 看 CPU→RSS→process poll |
| 续写需求 | 必须 continue 接 | 不需要续写，但数据要手动同步到 novel 库 |
| 退出状态 | 中断（exit_code != 0） | 正常退出（exit_code = 0） |

**最佳实践（更新版）：**
1. **新建大型项目（>2章）** 用 `background=true` 执行 `novel-factory new`，让 orchestrator 自己跑完一个批次
2. 通过 `process.poll` / `process.wait` 监控进度，间隔检查文件系统
3. 完成后同步到 novel 数据库：`python3 sync-novel-to-mongodb.py --proj-dir <slug>`
4. 如需继续下一批次：`novel-factory continue '项目名'`（同样用 background）

### MongoDB 数据格式规范（已踩过的坑）

同步脚本 `sync-novel-to-mongodb.py` 按以下字段写入 `novel.novels` 集合。其他小说的已有数据是权威参考——**任何字段格式都必须与其他小说保持严格一致**，不要发明新字段或新结构。

**核心写入逻辑**（`sync-novel-to-mongodb.py` upsert，2026-05-18 修复）：

```python
slug = to_slug(novel_name)  # 中文→拼音连字符，如 凌晨站台的访客 → ling-chen-zhan-tai-de-fang-ke
genre = existing.get('genre', '虚构') or '虚构'   # 不再硬编码为女频·治愈·都市
tags = existing.get('tags', ['小说', '情感']) or ['小说', '情感']
synopsis = synopsis_from_files or existing.get('synopsis', '暂无简介')
description = desc_from_blurb or ''    # 从 blurb.md 提取
```

**字段格式对照表**（对比其他小说的已有数据）：

| 字段 | 正确格式 | 踩过的坑 |
|------|---------|---------|
| `slug` | `ling-chen-zhan-tai-de-fang-ke`（拼音连字符） | 曾写入中文「凌晨站台的访客」，必须拼音化 |
| `genre` | `科幻悬疑·都市怪谈·情感治愈`（匹配实际内容） | 曾默认为 `女频·治愈·都市` |
| `tags` | `['科幻', '悬疑', '怪谈', '都市', '情感', '微恐']` | 曾硬编码 `['女频', '治愈', '都市', '情感']` |
| `characters[].title` | 角色身份（如「主角」、「关键角色」）— 字段名必须是 `title`，不是 `role` | 曾写入 `role` 字段，其他小说均无此字段 |
| `characters[].age` | ❌ 不存在此字段 | 曾写入 `age`/`occupation`，其他小说均无 |
| `characters[].occupation` | ❌ 不存在此字段 | 同上 |
| `characters[].traits` | 角色特质数组，如 `['冷静', '理智', '念旧']` | 曾缺失此字段 |
| `world` | dict 格式，如 `{'setting': '近未来...', 'core_concept': '...', 'factions': {'势力名': '描述'}, 'rules': ['规则1', '规则2']}` | 曾使用数组+对象混合结构，与其他小说不一致 |
| `timeline` | ❌ 不应存在此字段 | 其他小说均无 `timeline` 字段，已删除 |
| `description` | 从 blurb.md 提取的一句话简介 | 曾缺失，现已补全 |

**验证方法**——同步后检查数据格式是否与其他小说一致：
```python
db.novels.find_one({'name': '凌晨站台的访客'}, 
  {'slug':1, 'genre':1, 'tags':1, 'characters':1, 'world':1})
# 对比已有小说：
db.novels.find_one({'name': '诡异游戏：我的规则别人看不见'},
  {'slug':1, 'genre':1, 'tags':1, 'characters':1, 'world':1})
```

**slug 拼音映射**：`to_slug()` 函数维护 50+ 个常用汉字→拼音映射表（凌ling/晨chen/站zhan...），覆盖不足时 fallback 到 qmark。同步脚本中已内置映射表，如需扩展直接添加映射条目即可。

### V2 新增坑\n\n- **同步后必须检查 synopsis、tags、characters 是否正确填充**：旧版 sync-novel-to-mongodb.py 曾使用硬编码默认标签 `['女频', '治愈', '都市', '情感']` 和 `synopsis='暂无简介'`，对非女频小说（脑洞/悬疑/科幻等）会造成数据错误。脚本已修复为通用默认值并从 `ops/*.md` 自动提取，但已同步的旧数据需手动修正。验证方法：`db.novels.find_one({'name': '小说名'}, {'synopsis':1, 'tags':1, 'description':1, 'characters.name':1})`。

- **novel-factory CLI 输出不会自动同步到 `novel` 数据库**：`novel-factory new` 输出在 `/root/novel-factory/<slug>/draft/chapter-*.md`，`novel-factory continue`（V3 经 orchestrator）输出在 `/root/zj-matrix/novel-factory/chapters/ch###_*.md`。Web UI（NovelStudio）只读 `novel` 库。每次操作完成后必须同步。脚本 `sync-novel-to-mongodb.py --proj-dir <slug>` 已支持双路径自动查找和两种文件名格式。如果还失败，用 `novel-name` + `chapter-number` 做直连 MongoDB upsert 作为 fallback（见 `references/mongodb-sync-fallback.md`）。
- **MongoDB 写入不是即时的**：delegate_task 写入可能因网络延迟而延迟。在下一步读取前必须 `time.sleep(1)` 或重试读取。
- **memory-manager 是瓶颈**：所有写入串行化经过 memory-manager，高频写入时需批量处理，不要逐条写入。
- **`novel-factory refresh` 子会话可能超时**：CLI `novel-factory refresh <项目名>` 通过 `hermes -p orchestrator chat -q` 启动子会话，因子进程等待超时（10s）可能不完成工作。更可靠的方案是直接由主 agent 执行 analytics（连接 MongoDB 读取全量数据 → 计算指标 → 写入 anti_repetition collection → 输出报告）。参见 `references/manual-analytics-refresh.md`。
- **orchestrator 子会话无法传递完整上下文**：CLI 传参时项目名必须精确匹配 MongoDB 中的 title（"诡异游戏：我的规则别人看不见"而非"诡异游戏"），否则子会话找不到项目。
- **ARC 之间需要缓冲章**：不要 ARC 结尾直接接下一 ARC 开头。留 3-5 章过渡章节（角色休息、日常、新危机萌芽），否则读者（和模型）都会有跳跃感。
- **500 万字计划不可过于刚性**：预留 15-20% 的字数给"意外发展"（读者反馈导致的方向调整、灵感迸发的新支线）。
- **analytics 数据不能完全依赖数据库统计**：爽点密度、情绪曲线等定性指标需要模型判断，不能纯靠数值。
- **profile 越多，维护成本越高**：15 个 profile 是上限。每个新增 profile 意味着多一套 API key、多一份 SOUL.md、多一次 session 切换开销。新增 profile 前先问"这个职责能否合并到现有 profile？"
- **draft agent 必须强制读 MongoDB**：不能信任模型的"我记得"。每次写之前显式读 chapter_memory、characters、timeline。即使模型说"我记得"也要读。
- **anti-repetition 只检测不修改**：检测到重复后必须提交给 editor 修改，anti-repetition 不直接 patch 文件。

### V1 保留坑（已验证）

- **hook 字段 V1 迁移后非空**：V1→V2 迁移时 hook 字段已在 chapter_memory 中存在但值为空字符串 `""`。不是字段缺失。更新时用 `$set: {'hook': new_value}` 即可，不需要 `$unset` 或 `$rename`。
- **foreshadow 的 insert_many 必须每条都含 project_id**：`project_id` 是 `$jsonSchema` 的 required 字段。如果写成 `f['project_id'] = pid` 放在构建列表之后才赋值，会导致 schema validation 失败（WriteError code 121）。必须在每条 dict 创建时就包含。
- **characters 的 growth_arc/goals/relationships 是数组类型**：`goals` → 字符串数组 `["g1","g2","g3"]`，`relationships` → 对象数组 `[{"character_id": "...", "description": "..."}]`，`growth_arc` → 字符串数组 `["阶段1", "阶段2"]`。不是 dict。
- **emotion_tone 全部同色不一定有问题**：悬疑恐怖小说 135 章全是"悬疑"是合理的。analytics 的"情绪色调单一"警告需要结合类型判断，不一定是需要修复的漏洞。
- **`delegate_task` max_concurrent_children=3**，超过 3 个并行任务必须分多批。
- **novelName 不一致**：`novels.title` 和 `chapters.novelName` 可能不同。
- **合规报告必须执行修复**，不是看看就完。
- **并行批次的章节开头衔接**：批次之间可能场景跳跃，editor 必须检查。
- **女频·治愈互助类开篇不是打脸**，是"困境→微光→连接"。
- **女频字数易超预期**，规划时上浮 50%。
- **GitHub API 上传中文字符文件名需 URL 编码**。

### V3 新增坑点

- **CLI 通过 symlink 安装后必须用 readlink -f 解析路径**：`novel-factory` 通过 `ln -s` 安装到 `~/.local/bin/`，但 `$(dirname "$0")` 在 symlink 下会解析为软链所在目录而非真实路径，导致无法找到同目录下的 `.py` 脚本。必须用 `$(dirname "$(readlink -f "$0")")` 确保正确。安装方式必须为 `ln -s` 而非 `cp`（`cp` 会导致脚本更新后需重新复制，且缺失溯源信息）。
- **validate-chapter.py 的 check 命令已支持自动从 MongoDB 获取章节内容**：调用 `novel-factory validate <项目名> <章节>` 时无需提供 `--content-file` 或 `--stdin`。脚本会依次搜索 `novel.chapters`（V1 兼容层）和 `novel_factory.chapters` 库，再尝试从 `filename` 字段指向的本地文件读取。但项目名必须足够精确能被 MongoDB 正则匹配到。
- **Context Packet 不能替代 MongoDB 读取**：Context Packet 是创作状态的压缩摘要，**不是**完整数据源。draft agent 仍然必须先读 MongoDB 再写。Context Packet 只用来「补全模型上下文」，不替换持久层。
- **角色状态机过早更新**：不要在一章写到一半时就更新 character_states——情绪/战力变化应该等本章完全写完后再批量更新，否则当前章的状态会前后矛盾。
- **foreshadow_queue 的 deadline 不可过于刚性**：设定了 deadline 的伏笔如果需要延期不应强制回调（会破坏剧情节奏）。合理做法：设置 soft deadline + hard deadline，soft 可延 1-2 次后进入 hard 状态。
- **四层 ARC 规划的层级一致性**：World ARC 拆成 Phase ARC 时，Phase 的总弧线必须与 World ARC 目标一致。如果 arc-manager 在 Phase 层偏离了 World 方向，需要自动告警而非放任。
- **event_log 不能代替 commit message**：event_log 记录的是数据变更（写入了哪条数据、改了什么），不是「为什么改」。仍然需要 analytics 和 timeline 来记录创作决策的原因。
- **snapshot 生成不可过于频繁**：每 100 event 生成一次 snapshot（约 30 章），太频繁者者占用 MongoDB 存储空间（一条 snapshot ~50KB，100 万字约 ~170 条 snapshot~8.5MB，可接受）。
- **anti_fatigue 的检测阈值需要类型适配**：悬疑/恐怖小说的「紧张情绪重复」阈值应该低于爽文（悬疑需要持续紧张）。检测前先读 projects.genre 调整阈值。
- **live-validator 的 BLOCKER 不停写策略的双刃剑**：不停写意味着错误会写入数据库。editor 的 2nd pass 必须能发现并修正 live-validator 标记但放行的错误。memory-manager 的 event_log 记录 live-validator 的告警以便追踪。
- **V3 19 个 profile 的维护成本已接近上限**：每个 profile 维护一套 SOUL.md 和调用逻辑。新增前要问「能否复用现有 agent 的职责扩展？」。19 个是理论最大值，实际推荐 14-15 个核心 + 4-5 个按需创建。
- **分期创建 profile 不可全部同时创建**：建议优先创建 V2 已有 profile（保持兼容），再逐步添加 V3 新增的 arc-manager、character-state-agent、world-simulator、foreshadow-manager、live-validator。分批验证后再全部投入生产。
- **event_log 的 MongoDB 写入必须是写入通道的一部分**：任何写入 novel_factory 的操作必须在 event_log 记录，否则事件溯源链条断裂。memory-manager 的 `save_with_version` 必须串行化写入和日志记录。

---

## Kanban（V2 版）

```text
┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  Idea Pool  │→│Research  │→│ARC Plan  │→│World Bld │→
└─────────────┘ └──────────┘ └──────────┘ └──────────┘
                                               │
┌─────────────┐ ┌──────────┐ ┌──────────┐    │
│   Archived  │←│  Ops     │←│Compliance│←───┘
└─────────────┘ └──────────┘ └──────────┘    │
       │                              │       │
┌─────────────┐ ┌──────────┐ ┌──────────┐    │
│ Refresh Plan│←│Analytics │←│  Draft   │←───┘
└─────────────┘ └──────────┘ └──────────┘   
                                        │
                               ┌──────────┐
                               │  Editor  │
                               └──────────┘
                                        │
                               ┌─────────────┐
                               │Anti-Repetit.│
                               └─────────────┘
```

---

## 数据流总图

```text
Agent 输出变更集 (JSON)
  → orchestrator 收集
  → memory-manager 执行写入
    → 冲突检测
      → 无冲突 → 写入 MongoDB
      → 有冲突 → 返回冲突报告 → orchestrator 协调
  → 返回确认给调用 Agent
```

---

---

## Web UI: NovelStudio

NovelStudio 是 novel-factory 的 Web 前端，基于 Flask + Bootstrap 5 + MongoDB。**所有 Web 端改造工作必须在此项目中进行。**

### 仓库位置

| 项目 | 值 |
|------|-----|
| 远程仓库 | `https://gitee.com/zj1989/yz-Matrix.git`（原为 GitHub，2026-05-19 因网络问题切换至 Gitee） |
| 分支 | **`novel-studio`**（生产版，依赖阿里云 DYPNS SDK 但支持 mock 回退；`novel-studio-newest` 已废弃并删除） |
| 本地路径 | `~/zj-matrix/` |
| 端口 | 5003 |
| 数据库 | `novel`（192.168.2.30:27017，同服务器但非 `novel_factory` 库） |

### 启动方式

```bash
cd /root/zj-matrix && /opt/hermes-agent/venv/bin/python app.py
```

> **坑**：系统 `python3` 缺少 `dotenv` 模块，必须用 Hermes venv 的 Python 启动。`venv_studio` 虚拟环境可能过期或缺失 dotenv，实测使用 `/opt/hermes-agent/venv/bin/python` 最稳定。

或使用 `manage.sh` 脚本（注意必须 `cd ~/zj-matrix` 后在当前目录执行，因为它使用相对路径的 `pkill -f` 匹配模式）：

```bash
cd ~/zj-matrix && ./manage.sh start   # 启动
./manage.sh stop    # 停止
./manage.sh status  # 查看状态
./manage.sh restart # 重启
```

首次运行需要创建 `.env` 文件：

```
MONGO_URI=mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/
FLASK_SECRET_KEY=<your-secret-key>
ADMIN_PASSWORD=456321zj
```

### 管理员登录

手机号填写 `admin`，验证码填写 `ADMIN_PASSWORD` 的值（默认 `456321zj`）。

### 当前 Novel DB 中的数据（V1 兼容层）

| 小说 | slug | 章节数 |
|------|------|--------|
| 末世：我的污染等级比怪物高 | wo-de-wu-ran-deng-ji | — |
| 诡异游戏：我的规则别人看不见 | gui-yi-you-xi | — |
| 离婚后，我在花店找到了自己 | li-hun-hou-wo-zai-hua-dian-zhao-dao-le-zi-ji | — |
| **总计** | | **210 章** |

### Web UI 创建新小说流程

`/novel/create/` 页面提供完整的表单提交 → API → CLI 调用链路。

#### 后端 API (`POST /api/novel/create/`)

```python
# novel.py blueprint
@novel_bp.route('/api/novel/create/', methods=['POST'])
@admin_required
def api_create_novel():
    data = request.get_json()
    title = data.get('title', '').strip()
    genre = data.get('genre', '')
    target = data.get('target', '')
    tags = data.get('tags', [])
    summary = data.get('summary', '')

    # 构造需求描述
    req_parts = [f"书名：{title}"]
    req_parts.append(f"体裁：{GENRE_MAP[genre]}")
    req_parts.append(f"篇幅：{LENGTH_MAP[target]}")
    if tags: req_parts.append(f"标签：{'、'.join(tags)}")
    if summary: req_parts.append(f"核心冲突：{summary}")
    req_text = '，'.join(req_parts)

    # 调用 CLI
    result = subprocess.run(
        ['novel-factory', 'new', req_text],
        capture_output=True, text=True, timeout=600,
        cwd=os.path.dirname(os.path.dirname(__file__))
    )
    # 返回 JSON
```

**关键实现细节：**
- **超时控制**：600 秒（10 分钟），因为 `hermes -p orchestrator chat` 可能较慢
- **需求描述构造**：`GENRE_MAP`/`LENGTH_MAP` 做中文映射，拼成自然语言字符串（`书名：xxx，体裁：yyy，篇幅：zzz`）
- **错误分层**：400（表单校验）→ 500（CLI 调用失败）→ 504（超时），前端根据 status 显示不同消息
- **cwd 设置**：`os.path.dirname(__file__)` 的两层 `dirname` 确保进程在项目根目录运行（读取 `.env` 等需要）

#### 前端表单 (`create_novel.html`)

InkFlow 风格，Tailwind + Literata + Material Symbols。核心交互：

| 组件 | 实现方式 |
|------|---------|
| 标签多选 | `.tag-btn` 元素 `data-active` 属性 + JS toggle className 切换（未选中→border-outline-variant，选中→border-primary bg-primary-container） |
| 字数统计 | `<textarea maxlength="100">` + `input` 事件监听，超 90 字变红（`text-error`） |
| 表单提交 | `fetch('/api/novel/create/')` POST JSON，按钮禁用 + 文字变为「正在创建...」+ 图标变 `hourglass_top` |
| Toast 提示 | 固定 top-right 容器，4 秒自动消失，滑动入场动画（`animate-slide-in`），成功绿色 / 错误红色 |
| 成功跳转 | `setTimeout(() => window.location.href = '/admin/', 1500)` |

**表单校验链条**（双重保险）：
1. HTML5 `required` 属性（标题/体裁/字数）
2. JS 前置校验（`if (!title) { showToast('请填写作品名称', 'error'); return; }`）
3. 后端 400 校验
4. Toast 统一展示所有错误，不区分前后端来源

#### 添加新页面的标准步骤

```text
1. 在 novel.py 中新建路由 + render_template
2. 在 templates/ 下创建 InkFlow 风格 HTML
3. 如需要 API 调用：添加 `POST /api/novel/<action>/` 端点
4. 前端 JS 用 fetch + Toast 模式处理提交/反馈
5. `git add && git commit && git push origin novel-studio`（当前远程指向 Gitee）
6. kill $(lsof -ti:5003); sleep 1; cd ~/zj-matrix && source venv_studio/bin/activate && python3 app.py
```

### Pitfalls (部署相关)
- **阿里云短信 SDK 不是必须的**：`novel-studio` 分支依赖 `alibabacloud_dypnsapi20170525`（DYPNS 号码认证服务），`novel-studio-newest` 分支曾依赖 `alibabacloud_dysmsapi20170525`（DYSMS 短信服务）。两个 SDK 都不是启动必须——`auth.py` 中已修复为 `try/except` 条件导入，`_SMS_AVAILABLE = False` / `_DYPNS_AVAILABLE = False` 时自动走 mock 发送，管理员密码登录不受影响。
- **.env 文件必须包含真实 MongoDB 密码**：app.py 通过 `load_dotenv` 加载 `.env`，缺少 .env 时 `MONGO_URI` 会回退到 `db.py` 中的硬编码默认值（含 `***` 密码占位符），导致连接失败。密码必须为 `mongo_dxx8nA`，且需要 `?authSource=admin` 参数。
- **Flask 进程可能被 OOM 或 systemd 意外杀死**：这台服务器内存有限（8GB），Flask 进程在系统压力大时可能被内核 OOM killer 杀掉。表现为 `ss -tlnp | grep 5003` 无输出且浏览器访问 502。标准恢复命令：`kill $(lsof -ti:5003) 2>/dev/null; sleep 1; cd ~/zj-matrix && source venv_studio/bin/activate && nohup python3 app.py > /tmp/novelstudio.log 2>&1 &`。如果端口已被僵尸进程占用，先 `fuser -k 5003/tcp` 再启动。
- **后台进程必须用 `background=true + pty=false` 启动**：在 Hermes 中启动 Flask 等长时间运行的服务时，必须设置 `terminal(timeout=0, background=true, pty=false)`。`pty=true` 会导致进程在终端会话结束后被杀死（SIGHUP），且 `background` 模式不兼容 PTY。如果使用 `pty=true` 启动的服务显示「后台进程已启动」但在 3 秒后消失，就是这个原因。
- **服务启动后 502 持续 3-5 秒是正常的**：Flask debug 模式下首次启动会初始化模板缓存和 MongoDB 连接，偶尔超时。静等 5 秒再刷新即可。
- **有脚本在持续扫描 5003 端口的非法路径**：启动后日志中会出现大量 `GET /wk/index.php`、`GET /alfa.php`、`GET /wp-theme.php` 等 404 请求。这是互联网扫描机器人的行为，不影响服务，可以忽略。如果日志过大，可在 `app.py` 中添加 `import logging; logging.getLogger('werkzeug').setLevel(logging.ERROR)` 减少输出。
- **MongoDB 双库结构**：`novel` 数据库是 V1 兼容层（`novels` + `chapters` 集合），`novel_factory` 是 V2 创作层（8 个集合 + 4 个 _history）。两个库的数据**不同步**——Web UI 当前只读 `novel` 库。如需展示 V2 数据（ARC、伏笔、时间线），需要新增路由或做数据桥接。
- **venv 名称不同分支不同**：`novel-studio` 分支推荐使用 `venv_studio` 作为虚拟环境目录，避免与 `novel-studio-newest`（已删除）的 `venv` 冲突。`git checkout` 切换分支后注意切换对应的 venv。
- **static/ 目录**：`create_app` 中配置了 `static_folder='../static'`，但仓库默认没有 `static/` 目录。启动前需确保存在（`mkdir -p ~/zj-matrix/static`）。
- **数据库中有 `novels` 条目但页面不显示**：检查 `chapters` 集合中是否有 `novelName` 匹配的文档。`index()` 路由过滤掉了 `ch_count == 0` 的小说。

### CLI 控制台集成

NovelStudio 集成了统一 CLI 控制台，支持从浏览器执行所有 novel 子命令：

| 组件 | 位置 | 说明 |
|------|------|------|
| API 端点 | `GET/POST /api/novel/cli/` | 返回命令列表 / 执行命令 |
| Web 页面 | `GET /novel/cli/` | 终端风格控制台 |
| 侧边栏 | sidebar.html `{% else %}` 分支 | "CLI 控制台" 导航项 |
| 模板 | `templates/novel_cli.html` | 暗色终端 UI |

详见 `references/unified-cli-reference.md`。

### 后续改造方向

NovelStudio 能直接显示 `novel` 数据库中的小说数据。要显示 novel_factory V2 的数据（ARC 视图、伏笔追踪、角色关系网、时间线），需要：

1. 在 `app/db.py` 中新增 `novel_factory` 数据库连接
2. 新增 blueprints/routes 读取 `novel_factory` 的集合
3. 新增 templates 渲染 V2 特有的数据视图

---

## 附录：快速开始

### 1. 创建 novel_factory 数据库（已完成）
```bash
python3 -c "
import pymongo
client = pymongo.MongoClient('mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/')
db = client['novel_factory']
for c in ['projects','world_bible','characters','timeline','arcs','foreshadow','chapter_memory','anti_repetition']:
    db.create_collection(c)
print('Done')
"
```

### 2. 创建新 Profile
```bash
# 基于参考文件创建每个 profile
hermes profile create memory-manager
hermes profile create arc-planner
hermes profile create lore
hermes profile create timeline
hermes profile create power-control
hermes profile create draft-action
hermes profile create draft-romance
hermes profile create anti-repetition
hermes profile create analytics

# 升级已有 profile
hermes profile create orchestrator --overwrite
hermes profile create draft-main --overwrite
hermes profile create character --overwrite
hermes profile create editor --overwrite
```

每个 profile 创建后，将对应的 SOUL.md（见 references/）写入 `~/.hermes/profiles/<name>/SOUL.md`。

### 3. 启动新项目
```bash
novel-factory '启动新项目：男频狼人吸血鬼，目标300万字，番茄平台'
```

SOUL.md 参考文件见 `references/` 目录：包括 9 个新增/升级 Profile 的完整 SOUL.md。
