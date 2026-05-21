# 事件溯源同步系统（V3）

> **所属系统**: novel-factory V3  
> **负责 Agent**: event-logger (事件溯源子代理)  
> **版本**: 3.0  
> **最后更新**: 2026-05-18

---

## 目录

1. [设计目标](#1-设计目标)
2. [核心概念](#2-核心概念)
3. [event_log Collection Schema](#3-event_log-collection-schema)
4. [事件类型枚举（12+ 种）](#4-事件类型枚举12-种)
5. [实时写入流程](#5-实时写入流程)
6. [快照机制 (snapshot_store)](#6-快照机制-snapshot_store)
7. [回滚流程](#7-回滚流程)
8. [状态折叠（Fold）算法](#8-状态折叠fold算法)
9. [与 novel-factory CLI 的集成方式](#9-与-novel-factory-cli-的集成方式)
10. [Python 伪代码](#10-python-伪代码)
11. [迁移路径：V2 → V3](#11-迁移路径v2--v3)
12. [风险与应对](#12-风险与应对)

---

## 1. 设计目标

V2 最大的同步风险——`sync-novel-to-mongodb.py` 是**离线批量行为**。该脚本在最后一次性将所有本地文件写入 MongoDB。只要脚本中途崩溃或网络中断，MongoDB 就处于「半同步」状态：部分章节已写入、部分还没写；本地已经编辑到第 8 章、数据库只到第 5 章。没有任何机制能检测或修复这种不一致。

V3 必须彻底消除这个风险。核心思路：**每个步骤都实时写数据库**，用 append-only event log 替代批量同步。

| 问题 | V2（离线批量） | V3（事件溯源） |
|------|---------------|---------------|
| 写入时机 | 所有步骤完成后一次性同步 | 每一步结束立即 append event |
| 真相源 | 本地文件系统 | MongoDB (event log) |
| 本地文件角色 | 持久化层 | 只读缓存层 |
| 中途崩溃后果 | MongoDB 与本地不一致 | event log 可回溯，至多丢一个 event |
| 回滚支持 | 无（需要手动修复） | 任意点回滚（重放到目标版本） |
| 审计追踪 | 无 | 完整的事件历史 |

---

## 2. 核心概念

### 2.1 Append-Only Event Log

所有变更不是"修改"数据，而是"追加"事件。每件事件代表一次不可变的状态变更。

```
时间轴:  E1 → E2 → E3 → ... → E100 → SNAPSHOT → E101 → ...
```

### 2.2 事件溯源（Event Sourcing）

当前状态 = 从事件日志折叠（fold）出来的结果。

```
CurrentState = fold([E1, E2, ..., En], initialState)
```

### 2.3 MongoDB 是唯一真相源

- 所有写入**先写 MongoDB event log**，再更新本地缓存
- 本地文件如果被误删，可以从 event log 完全重建
- 本地文件成为「可丢弃的缓存层」

### 2.4 快照（Snapshot）

每 100 个事件生成一个状态快照，避免每次都需要回放全部历史。

---

## 3. event_log Collection Schema

存储位置：`novel_factory` 数据库 → `event_log` 集合

```json
{
  "_id": ObjectId,
  "event_id": "evt_001a2b3c",          // 全局唯一事件 ID (ULID)
  "event_type": "CHAPTER_DRAFTED",       // 参见 §4
  "project_id": "ni-sheng-zhi-yu",       // 项目 slug
  "chapter_id": "ch-003",                // 关联章节（可选，可按章节查询）
  "payload": {                           // 事件负载：不同类型不同结构
    "chapter_title": "风云突变",
    "content_hash": "sha256:abc...",
    "word_count": 5200,
    "draft_version": 3
  },
  "version": 42,                         // 项目级别单调递增版本号
  "timestamp": "2026-05-18T15:30:00Z",   // 事件发生时间
  "source": "draft-agent",               // 来源 agent 名称
  "metadata": {                          // 扩展元数据
    "cli_run_id": "run_xyz",
    "parent_event": "evt_...",
    "rollback_target": null
  }
}
```

### 索引设计

```javascript
// 按项目+版本排序（用于折叠和回放）
db.event_log.createIndex({ project_id: 1, version: 1 }, { unique: true })

// 按项目+时间排序（用于时间范围查询）
db.event_log.createIndex({ project_id: 1, timestamp: -1 })

// 按事件类型查询（用于统计分析）
db.event_log.createIndex({ project_id: 1, event_type: 1 })
```

### 索引说明

- `project_id + version` 的 unique 索引确保版本号不冲突，同时也是折叠时的主要查询路径
- `project_id + timestamp` 索引用于快速查找特定时间点的状态
- `project_id + event_type` 索引用于分析（如统计某章节被编辑了多少次）

---

## 4. 事件类型枚举（12+ 种）

| # | 事件类型 | 所属模块 | Payload 关键字段 | 触发时机 |
|---|---------|---------|-----------------|---------|
| 1 | **CHAPTER_DRAFTED** | Draft | `chapter_title, content_hash, word_count, draft_version` | 草稿完成 |
| 2 | **CHAPTER_EDITED** | Editor | `edit_summary, changes, editor_version, review_score` | 编辑完成 |
| 3 | **CHARACTER_UPDATED** | World | `char_id, name, traits, relationships, power_level` | 角色变更 |
| 4 | **WORLD_UPDATED** | World | `location, faction, timeline, world_state_hash` | 世界状态变更 |
| 5 | **ARC_CREATED** | Arc | `arc_id, arc_name, target_chapters, theme` | 新弧线创建 |
| 6 | **ARC_ADJUSTED** | Arc | `arc_id, chapter_allocation_diff, old_plan, new_plan` | 弧线调整 |
| 7 | **FORESHADOW_SET** | Foreshadow | `foreshadow_id, source_chapter, target_chapter, hint_text` | 伏笔设定 |
| 8 | **FORESHADOW_RESOLVED** | Foreshadow | `foreshadow_id, resolution_chapter, resolution_text` | 伏笔回收 |
| 9 | **POWER_UPDATED** | Power | `char_id, old_power, new_power, reason` | 实力变化 |
| 10 | **FATIGUE_CHECKED** | Fatigue | `chapter_id, fatigue_score, action_quality_prediction` | 疲劳检测 |
| 11 | **CONTEXT_PACKET_GENERATED** | Context | `packet_id, chapter_id, included_sections, token_count` | 上下文包生成 |
| 12 | **STATE_SNAPSHOT** | System | `snapshot_id, base_version, state_hash` | 快照生成 |

### 4.1 事件类型设计原则

1. **不可变性**：事件一旦写入绝不修改或删除。如果需要"修正"，应追加一个补偿事件（如 `CHARACTER_UPDATED` 再次发生）
2. **自包含**：每个事件 payload 包含足够信息，不需要查其他集合就能理解变更
3. **颗粒度适中**：不细到每个字符变动，也不粗到"更新了整个项目"——每个事件对应一个原子操作

---

## 5. 实时写入流程

### 5.1 流程图

```
[Agent 执行步骤]
        │
        ▼
[步骤完成，有状态变更]
        │
        ├── 1. 构建事件对象 (event_type + payload)
        │
        ├── 2. 写入 MongoDB event_log (insert_one)
        │       └── 失败 → 重试 3 次 → 失败则中止当前步骤并告警
        │
        ├── 3. 写入成功后，更新本地缓存（可选）
        │       └── 失败 → 忽略（本地只是缓存）
        │
        └── 4. 返回成功给 Agent
```

### 5.2 伪代码流程

```python
def on_step_completed(step_result, project_id):
    """每个步骤完成后的 post-step hook"""
    event = build_event(step_result, project_id)
    
    # 写入 MongoDB（核心路径）
    for attempt in range(3):
        try:
            db.event_log.insert_one(event)
            break
        except pymongo.errors.DuplicateKeyError:
            # 版本冲突：自增重试
            event["version"] = get_next_version(project_id)
            continue
        except pymongo.errors.ConnectionFailure as e:
            if attempt == 2:
                raise RuntimeError(f"无法写入 event log: {e}")
            time.sleep(0.5 * (attempt + 1))
    
    # 更新本地缓存（尽力而为）
    try:
        update_local_cache(event)
    except Exception:
        pass  # 缓存失败不影响一致性
```

### 5.3 与 V2 的关键区别

| 方面 | V2 | V3 |
|------|----|----|
| 写入时机 | 所有步骤结束后 | 每个步骤结束后 |
| 写入对象 | chapters/novels/arcs 等多个集合 | 只有 event_log（一个集合） |
| 原子性 | 无（多个集合各自独立写入） | 有（单条 event insert 是原子的） |
| 失败恢复 | 需要手动重新同步 | 自动重试，最大丢失 1 个 event |
| 并行安全 | 无（CLI 单线程但无锁） | 版本号机制确保顺序一致性 |

---

## 6. 快照机制 (snapshot_store)

### 6.1 为什么需要快照

假设一个项目有 5000 个事件。每次需要「当前状态」时从头折叠 5000 个事件：
- 数据库查询 5000 次（或一次查询全加载）
- Python 端处理 5000 个事件，逐个应用状态变更
- 耗时可能达到秒级，对 CLI 交互不可接受

快照 = 每隔 N 个事件保存一份**完整状态副本**，下次只需从最近的快照继续折叠。

### 6.2 snapshot_store 集合

存储位置：`novel_factory` 数据库 → `snapshot_store` 集合

```json
{
  "_id": ObjectId,
  "snapshot_id": "snap_001",
  "project_id": "ni-sheng-zhi-yu",
  "base_version": 100,             // 该快照基于第 N 个事件之后的状态
  "state": {
    // 完整的项目状态对象
    "chapters": { ... },
    "characters": { ... },
    "world_state": { ... },
    "arcs": { ... },
    "foreshadows": { ... },
    "power_map": { ... },
    "fatigue_scores": { ... }
  },
  "state_hash": "sha256:def...",   // 状态对象的校验和
  "timestamp": "2026-05-18T16:00:00Z",
  "event_count_since_last": 100    // 从上一个快照至今的事件数
}
```

### 6.3 快照生成策略

```python
SNAPSHOT_INTERVAL = 100  # 每 100 个事件生成一次快照

def maybe_snapshot(project_id, current_version, current_state):
    """检查是否需要生成快照"""
    if current_version % SNAPSHOT_INTERVAL == 0:
        # 异步生成（不影响主流程）
        spawn_task(generate_snapshot, project_id, current_version, current_state)

def generate_snapshot(project_id, version, state):
    """生成并存储快照"""
    snapshot = {
        "snapshot_id": f"snap_{ulid()}",
        "project_id": project_id,
        "base_version": version,
        "state": state.to_dict(),
        "state_hash": hash_state(state),
        "timestamp": datetime.utcnow(),
        "event_count_since_last": SNAPSHOT_INTERVAL
    }
    db.snapshot_store.insert_one(snapshot)
```

### 6.4 快照清理

- 保留最近 20 个快照
- 每生成一个新快照时，删除最旧的快照（按 `base_version` 升序排列后的前 N-20 个）
- 可根据配置调整保留数量

---

## 7. 回滚流程

### 7.1 回滚需求场景

| 场景 | 说明 |
|------|------|
| 编辑质量不达标 | 某章编辑后 review 分数过低，需要恢复到编辑前 |
| 角色变更错误 | 误改了角色属性，影响后续生成一致性 |
| 弧线规划失误 | 弧线调整后导致后续章节逻辑断裂 |
| 实验性操作 | 试跑某个修改方案后需要撤销 |

### 7.2 回滚算法

```
1. 用户指定回滚目标：项目 + 章节 + 版本号
   └─ 例如："回滚 ch-005 到第 42 版事件之后的状态"

2. 找到目标事件：
   └─ 查询 event_log，找到该章节在目标版本之前的最后一个事件
   └─ 例如：ch-005 在 version <= 42 的最后一个事件是 version 40

3. 找到最近的快照：
   └─ 查询 snapshot_store，找到 base_version <= 40 的最新快照
   └─ 例如：base_version = 33 的快照

4. 重放快照之后的事件：
   └─ 从快照的 base_version (33) 开始
   └─ 重放 version 34 ~ 40 的事件（只重放 ch-005 相关的事件）
   └─ 得到 ch-005 在 version 40 时的状态

5. 写入补偿事件：
   └─ 生成一个 ROLLBACK 事件记录回滚操作
   └─ 将章节状态写回到目标版本

6. 重建本地文件：
   └─ 从 MongoDB 读取回滚后的状态
   └─ 写回本地文件系统（缓存层刷新）
```

### 7.3 回滚的 Python 伪代码

```python
def rollback_chapter(project_id, chapter_id, target_version):
    """
    将指定章节回滚到 target_version 之后的状态
    返回：回滚后的事件版本号
    """
    # 1. 验证目标版本存在
    target_event = db.event_log.find_one(
        {"project_id": project_id, "version": target_version}
    )
    if not target_event:
        raise ValueError(f"版本 {target_version} 不存在")

    # 2. 找到最近的快照
    snapshot = db.snapshot_store.find_one(
        {"project_id": project_id, "base_version": {"$lte": target_version}},
        sort=[("base_version", -1)]
    )

    # 3. 从快照或初始状态开始重放
    if snapshot:
        state = restore_from_snapshot(snapshot)
        replay_from = snapshot["base_version"] + 1
    else:
        state = ProjectState.empty()
        replay_from = 1

    # 4. 查询需要重放的事件（只查相关事件）
    events = db.event_log.find({
        "project_id": project_id,
        "version": {"$gte": replay_from, "$lte": target_version},
        "$or": [
            {"chapter_id": chapter_id},       # 直接相关
            {"event_type": {"$in": GLOBAL_EVENTS}}  # 全局事件（角色、世界等）
        ]
    }).sort("version", 1)

    # 5. 逐个应用事件
    for event in events:
        apply_event(state, event)

    # 6. 提取该章节的回滚后状态
    rolled_back_chapter = state.chapters[chapter_id]

    # 7. 写入 ROLLBACK 补偿事件
    rollback_event = {
        "event_id": f"evt_{ulid()}",
        "event_type": "ROLLBACK_EXECUTED",
        "project_id": project_id,
        "chapter_id": chapter_id,
        "payload": {
            "target_version": target_version,
            "chapter_state": rolled_back_chapter,
            "reason": "user_initiated_rollback"
        },
        "version": get_next_version(project_id),
        "timestamp": datetime.utcnow(),
        "source": "rollback-manager"
    }
    db.event_log.insert_one(rollback_event)

    # 8. 刷新本地缓存
    write_chapter_to_local(project_id, chapter_id, rolled_back_chapter)

    return rollback_event["version"]
```

### 7.4 回滚注意事项

- **回滚不是删除事件**：事件日志永远 append-only。回滚是追加一个 `ROLLBACK_EXECUTED` 事件，并将后续读取逻辑指向目标版本
- **部分回滚 vs 全量回滚**：可以回滚单个章节（仅影响该章节状态），也可以回滚整个项目到某时间点
- **回滚后的编辑**：在回滚基础上继续编辑 = 追加新事件，版本号继续递增
- **冲突检测**：如果回滚目标版本之后已经有其他章节的大幅修改，需告警提示可能产生逻辑矛盾

---

## 8. 状态折叠（Fold）算法

### 8.1 基本折叠（从 0 开始）

```python
def fold_events(project_id, up_to_version=None):
    """
    从 event log 折叠出当前项目状态
    
    Args:
        project_id: 项目 slug
        up_to_version: 折叠到哪个版本为止（None = 最新）
    
    Returns:
        ProjectState 对象
    """
    # 1. 尝试从快照恢复
    query = {"project_id": project_id}
    if up_to_version:
        query["base_version"] = {"$lte": up_to_version}
    
    snapshot = db.snapshot_store.find_one(
        query,
        sort=[("base_version", -1)]
    )
    
    if snapshot:
        state = ProjectState.from_dict(snapshot["state"])
        start_version = snapshot["base_version"] + 1
    else:
        state = ProjectState.empty()
        start_version = 1

    # 2. 查询事件
    event_query = {
        "project_id": project_id,
        "version": {"$gte": start_version}
    }
    if up_to_version:
        event_query["version"]["$lte"] = up_to_version
    
    events = db.event_log.find(
        event_query,
        sort=[("version", 1)]
    )

    # 3. 逐个应用
    for event in events:
        apply_event(state, event)
        # 如果刚好碰到快照且我们不是从快照开始的
        # （并行快照加载场景），可以跳过
        state.version = event["version"]

    return state
```

### 8.2 apply_event 核心分派

```python
def apply_event(state, event):
    """将单个事件应用到状态对象上"""
    dispatcher = {
        "CHAPTER_DRAFTED":        apply_chapter_drafted,
        "CHAPTER_EDITED":         apply_chapter_edited,
        "CHARACTER_UPDATED":      apply_character_updated,
        "WORLD_UPDATED":          apply_world_updated,
        "ARC_CREATED":            apply_arc_created,
        "ARC_ADJUSTED":           apply_arc_adjusted,
        "FORESHADOW_SET":         apply_foreshadow_set,
        "FORESHADOW_RESOLVED":    apply_foreshadow_resolved,
        "POWER_UPDATED":          apply_power_updated,
        "FATIGUE_CHECKED":        apply_fatigue_checked,
        "CONTEXT_PACKET_GENERATED": apply_context_packet,
        "STATE_SNAPSHOT":         lambda s, e: s,  # 快照事件不影响折叠状态
        "ROLLBACK_EXECUTED":      apply_rollback,
    }
    
    handler = dispatcher.get(event["event_type"])
    if handler:
        handler(state, event)
    else:
        logger.warning(f"未知事件类型: {event['event_type']}")
```

### 8.3 缓存折叠结果

由于频繁折叠（CLI 每次交互可能需要读取项目状态），应缓存折叠结果：

```python
class FoldCache:
    """折叠结果缓存，防止每次 CLI 命令都全量折叠"""
    
    def __init__(self, project_id, ttl_seconds=300):
        self.project_id = project_id
        self.cache = {}  # version -> (state, timestamp)
        self.ttl = ttl_seconds
    
    def get(self, version=None):
        key = version or "latest"
        if key in self.cache:
            state, ts = self.cache[key]
            if time.time() - ts < self.ttl:
                return state
        return None
    
    def set(self, state, version=None):
        key = version or "latest"
        self.cache[key] = (state, time.time())
```

---

## 9. 与 novel-factory CLI 的集成方式

### 9.1 不需要改 CLI 本身

核心原则：**不修改 CLI 的 main 流程**，只需要在**每个步骤执行完毕后插入一个 hook**。

CLI 当前流程（V2）：
```
run_pipeline()
  ├── draft_chapter()      → 写入本地 draft/
  ├── edit_chapter()       → 写入本地 draft/（覆盖）
  ├── update_world()       → 写入本地 ops/
  ├── update_character()   → 写入本地 ops/
  └── sync_to_mongodb()    → 一次性批量写入 MongoDB
```

V3 改造后的流程：
```
run_pipeline()
  ├── draft_chapter()      → 写入本地 draft/ + post_step_hook("CHAPTER_DRAFTED")
  ├── edit_chapter()       → 写入本地 draft/ + post_step_hook("CHAPTER_EDITED")
  ├── update_world()       → 写入本地 ops/  + post_step_hook("WORLD_UPDATED")
  ├── update_character()   → 写入本地 ops/  + post_step_hook("CHARACTER_UPDATED")
  └── [不再需要 sync_to_mongodb]
```

### 9.2 实现方式：post-step hook

在 `novel-factory` CLI 的 pipeline 中，每个步骤完成后调用一个统一函数：

```python
# 在 pipeline.py 中添加

from event_sourcing import emit_event

def post_step_hook(step_result, context):
    """
    每个步骤完成后的钩子函数
    
    Args:
        step_result: 步骤执行结果（包含 event_type, payload, project_id 等）
        context: 执行上下文（包含 project_id, cli_run_id 等）
    """
    if not step_result.get("has_changes"):
        return  # 没有状态变更，跳过
    
    emit_event(
        event_type=step_result["event_type"],
        project_id=context["project_id"],
        payload=step_result["payload"],
        source=context.get("agent_name", "cli"),
        chapter_id=step_result.get("chapter_id"),
        metadata={
            "cli_run_id": context.get("cli_run_id"),
        }
    )
```

### 9.3 修改位置

只需修改 pipeline 中的步骤调用：

```python
# 修改前
def draft_chapter(proj, chapter_num):
    content = generate_chapter(proj, chapter_num)
    write_to_local(proj, chapter_num, content)
    return content

# 修改后
def draft_chapter(proj, chapter_num):
    content = generate_chapter(proj, chapter_num)
    write_to_local(proj, chapter_num, content)  # 仍写本地（缓存层）
    post_step_hook({                           # 追加写入 event log
        "has_changes": True,
        "event_type": "CHAPTER_DRAFTED",
        "chapter_id": f"ch-{chapter_num:03d}",
        "payload": {
            "chapter_title": extract_title(content),
            "content_hash": sha256(content),
            "word_count": count_words(content),
            "draft_version": get_draft_version(proj, chapter_num),
        },
        "agent_name": "draft-agent"
    }, context)
    return content
```

### 9.4 移除 sync_to_mongodb 步骤

V2 的最后一步 `sync_to_mongodb()` 在 V3 中完全移除。不再需要"最后同步"，因为每个步骤已经同步完毕。

---

## 10. Python 伪代码

### 10.1 完整模块：event_sourcing.py

```python
# event_sourcing.py — 事件溯源核心模块
# 引入方式：from event_sourcing import emit_event, fold_events, rollback

import pymongo
import hashlib
import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# --- 配置 ---
MONGO_URI = "mongodb://mongo_8F6dTZ:***@192.168.2.30:27017/novel_factory?authSource=admin"
SNAPSHOT_INTERVAL = 100
MAX_RETRIES = 3

# --- 数据库连接 ---
_client = None

def get_db():
    global _client
    if _client is None:
        _client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client["novel_factory"]


# ==============================================================
# 1. 事件写入
# ==============================================================

def get_next_version(project_id: str) -> int:
    """原子递增版本号（使用 MongoDB findAndModify）"""
    db = get_db()
    counter = db.counters.find_one_and_update(
        {"_id": f"version_{project_id}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    return counter["seq"]


def emit_event(
    event_type: str,
    project_id: str,
    payload: Dict[str, Any],
    source: str = "cli",
    chapter_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    追加一个事件到 event log
    
    这是整个系统中最重要的写入函数。
    每次调用 = 一个原子操作写入 MongoDB。
    """
    db = get_db()
    
    version = get_next_version(project_id)
    
    event = {
        "event_id": f"evt_{version:06d}_{project_id[:4]}",
        "event_type": event_type,
        "project_id": project_id,
        "payload": payload,
        "version": version,
        "timestamp": datetime.utcnow(),
        "source": source,
    }
    
    if chapter_id:
        event["chapter_id"] = chapter_id
    if metadata:
        event["metadata"] = metadata
    
    # 写入 event log（最多重试 3 次）
    for attempt in range(MAX_RETRIES):
        try:
            db.event_log.insert_one(event)
            break
        except pymongo.errors.DuplicateKeyError:
            # 版本冲突：重新获取版本号
            logger.warning(f"版本冲突，重试 ({attempt+1}/{MAX_RETRIES})")
            version = get_next_version(project_id)
            event["version"] = version
            event["event_id"] = f"evt_{version:06d}_{project_id[:4]}"
        except pymongo.errors.ConnectionFailure as e:
            if attempt == MAX_RETRIES - 1:
                logger.error(f"无法写入 event log (project={project_id}): {e}")
                raise
            time.sleep(0.5 * (attempt + 1))
    
    logger.info(f"事件已写入: {event_type} v{version} (project={project_id})")
    
    # 检查是否需要生成快照
    if version % SNAPSHOT_INTERVAL == 0:
        _trigger_snapshot(project_id, version)
    
    return event


# ==============================================================
# 2. 状态折叠
# ==============================================================

def fold_events(
    project_id: str,
    up_to_version: Optional[int] = None
) -> Dict[str, Any]:
    """
    从 event log 折叠出项目当前状态
    
    算法说明：
    1. 找到最近的快照（base_version <= up_to_version）
    2. 从快照状态开始
    3. 重放快照之后到目标版本之间的所有事件
    
    返回 ProjectState 字典
    """
    db = get_db()
    
    # 1. 找最近的快照
    snapshot = db.snapshot_store.find_one(
        {
            "project_id": project_id,
            **({"base_version": {"$lte": up_to_version}} if up_to_version else {})
        },
        sort=[("base_version", -1)]
    )
    
    if snapshot:
        state = ProjectState.from_dict(snapshot["state"])
        start_version = snapshot["base_version"] + 1
        logger.info(f"从快照 v{snapshot['base_version']} 恢复")
    else:
        state = ProjectState.empty()
        start_version = 1
        logger.info("无快照，从初始状态开始折叠")
    
    # 2. 查询事件
    event_filter = {
        "project_id": project_id,
        "version": {"$gte": start_version}
    }
    if up_to_version:
        event_filter["version"]["$lte"] = up_to_version
    
    events = db.event_log.find(
        event_filter,
        sort=[("version", 1)]
    )
    
    # 3. 折叠
    event_count = 0
    for event in events:
        apply_event(state, event)
        state.version = event["version"]
        event_count += 1
    
    logger.info(f"折叠完成: {event_count} 个事件重放，当前版本 v{state.version}")
    
    return state


# ==============================================================
# 3. 快照生成
# ==============================================================

def _trigger_snapshot(project_id: str, version: int):
    """触发异步快照生成"""
    # 实际实现可丢入线程池或异步任务队列
    import threading
    t = threading.Thread(target=_generate_snapshot, args=(project_id, version))
    t.start()


def _generate_snapshot(project_id: str, version: int):
    """生成快照"""
    db = get_db()
    
    # 折叠到当前版本获取完整状态
    state = fold_events(project_id, up_to_version=version)
    
    snapshot = {
        "snapshot_id": f"snap_{project_id[:4]}_{version:06d}",
        "project_id": project_id,
        "base_version": version,
        "state": state.to_dict(),
        "state_hash": hashlib.sha256(
            json.dumps(state.to_dict(), sort_keys=True, default=str).encode()
        ).hexdigest(),
        "timestamp": datetime.utcnow(),
        "event_count_since_last": SNAPSHOT_INTERVAL
    }
    
    db.snapshot_store.insert_one(snapshot)
    
    # 清理旧快照（保留最近 20 个）
    old_snapshots = db.snapshot_store.find(
        {"project_id": project_id},
        sort=[("base_version", -1)],
        skip=20
    )
    for old in old_snapshots:
        db.snapshot_store.delete_one({"_id": old["_id"]})
    
    logger.info(f"快照已生成: v{version} (project={project_id})")


# ==============================================================
# 4. 回滚
# ==============================================================

def rollback(
    project_id: str,
    target_version: int,
    scope: str = "chapter",
    chapter_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    回滚项目到指定版本
    
    Args:
        project_id: 项目 slug
        target_version: 目标版本号
        scope: "chapter"（只回滚单个章节）或 "project"（回滚整个项目）
        chapter_id: scope="chapter" 时需要
    
    Returns:
        回滚补偿事件
    """
    db = get_db()
    
    # 1. 验证目标版本
    target_event = db.event_log.find_one(
        {"project_id": project_id, "version": target_version}
    )
    if not target_event:
        raise ValueError(f"目标版本 v{target_version} 不存在")
    
    # 2. 折叠到目标版本
    target_state = fold_events(project_id, up_to_version=target_version)
    
    # 3. 写入 ROLLBACK 事件
    rollback_event = emit_event(
        event_type="ROLLBACK_EXECUTED",
        project_id=project_id,
        payload={
            "target_version": target_version,
            "scope": scope,
            "chapter_id": chapter_id,
            "snapshot": target_state.to_dict() if scope == "project" else None,
        },
        source="rollback-manager",
        metadata={
            "is_rollback": True,
            "rolled_back_from": target_state.version,
        }
    )
    
    # 4. 刷新本地缓存
    if scope == "project":
        _write_state_to_local(project_id, target_state)
    elif scope == "chapter" and chapter_id:
        chapter_state = target_state.chapters.get(chapter_id)
        if chapter_state:
            _write_chapter_to_local(project_id, chapter_id, chapter_state)
    
    logger.info(
        f"回滚完成: project={project_id}, "
        f"target=v{target_version}, scope={scope}"
    )
    
    return rollback_event


# ==============================================================
# 5. 本地缓存刷新
# ==============================================================

def _write_chapter_to_local(project_id: str, chapter_id: str, content: str):
    """将章节内容写回本地文件"""
    path = f"/root/novel-factory/{project_id}/draft/{chapter_id}.md"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def rebuild_local_from_event_log(project_id: str):
    """
    从 event log 完全重建本地文件
    
    场景：本地文件被误删除或损坏时使用
    """
    state = fold_events(project_id)
    
    # 写入所有章节
    for ch_id, ch_content in state.chapters.items():
        _write_chapter_to_local(project_id, ch_id, ch_content)
    
    # 写入世界状态
    world_path = f"/root/novel-factory/{project_id}/ops/world_state.json"
    with open(world_path, "w", encoding="utf-8") as f:
        json.dump(state.world_state, f, ensure_ascii=False, indent=2)
    
    # 写入角色状态
    char_path = f"/root/novel-factory/{project_id}/ops/characters.json"
    with open(char_path, "w", encoding="utf-8") as f:
        json.dump(state.characters, f, ensure_ascii=False, indent=2)
    
    logger.info(f"本地文件已从 event log 重建: {project_id}")


# ==============================================================
# 6. ProjectState 类
# ==============================================================

class ProjectState:
    """
    项目状态对象
    
    包含所有可以从 event log 折叠出的状态信息。
    本质是一个可序列化的 DTO。
    """
    
    def __init__(self):
        self.version = 0
        self.chapters = {}        # chapter_id -> content
        self.chapter_meta = {}    # chapter_id -> {title, word_count, ...}
        self.characters = {}      # char_id -> {name, traits, ...}
        self.world_state = {}     # {locations, factions, timeline, ...}
        self.arcs = {}            # arc_id -> {name, chapters, ...}
        self.foreshadows = {}     # foreshadow_id -> {hint, source, target, ...}
        self.resolved_foreshadows = {}
        self.power_map = {}       # char_id -> power_level
        self.fatigue_scores = {}  # chapter_id -> score
    
    @classmethod
    def empty(cls):
        return cls()
    
    @classmethod
    def from_dict(cls, data):
        state = cls()
        for key, value in data.items():
            setattr(state, key, value)
        return state
    
    def to_dict(self):
        return {
            "version": self.version,
            "chapters": self.chapters,
            "chapter_meta": self.chapter_meta,
            "characters": self.characters,
            "world_state": self.world_state,
            "arcs": self.arcs,
            "foreshadows": self.foreshadows,
            "resolved_foreshadows": self.resolved_foreshadows,
            "power_map": self.power_map,
            "fatigue_scores": self.fatigue_scores,
        }


# ==============================================================
# 7. 事件应用函数集
# ==============================================================

def apply_event(state: ProjectState, event: Dict[str, Any]):
    """将单个事件应用到状态对象上"""
    dispatcher = {
        "CHAPTER_DRAFTED":        _on_chapter_drafted,
        "CHAPTER_EDITED":         _on_chapter_edited,
        "CHARACTER_UPDATED":      _on_character_updated,
        "WORLD_UPDATED":          _on_world_updated,
        "ARC_CREATED":            _on_arc_created,
        "ARC_ADJUSTED":           _on_arc_adjusted,
        "FORESHADOW_SET":         _on_foreshadow_set,
        "FORESHADOW_RESOLVED":    _on_foreshadow_resolved,
        "POWER_UPDATED":          _on_power_updated,
        "FATIGUE_CHECKED":        _on_fatigue_checked,
        "CONTEXT_PACKET_GENERATED": lambda s, e: None,
        "STATE_SNAPSHOT":         lambda s, e: None,
        "ROLLBACK_EXECUTED":      lambda s, e: None,
    }
    
    handler = dispatcher.get(event["event_type"])
    if handler:
        handler(state, event)


def _on_chapter_drafted(state, event):
    ch_id = event.get("chapter_id")
    payload = event["payload"]
    state.chapters[ch_id] = payload.get("content", "")
    state.chapter_meta[ch_id] = {
        "title": payload.get("chapter_title"),
        "word_count": payload.get("word_count"),
        "draft_version": payload.get("draft_version"),
        "status": "drafted",
    }


def _on_chapter_edited(state, event):
    ch_id = event.get("chapter_id")
    payload = event["payload"]
    state.chapters[ch_id] = payload.get("content", state.chapters.get(ch_id, ""))
    meta = state.chapter_meta.get(ch_id, {})
    meta.update({
        "editor_version": payload.get("editor_version"),
        "review_score": payload.get("review_score"),
        "status": "edited",
    })
    state.chapter_meta[ch_id] = meta


def _on_character_updated(state, event):
    payload = event["payload"]
    char_id = payload.get("char_id")
    state.characters[char_id] = {
        "name": payload.get("name"),
        "traits": payload.get("traits"),
        "relationships": payload.get("relationships"),
        "power_level": payload.get("power_level"),
    }


def _on_world_updated(state, event):
    payload = event["payload"]
    state.world_state.update(payload)


def _on_arc_created(state, event):
    payload = event["payload"]
    arc_id = payload.get("arc_id")
    state.arcs[arc_id] = {
        "name": payload.get("arc_name"),
        "target_chapters": payload.get("target_chapters"),
        "theme": payload.get("theme"),
        "chapter_allocation": payload.get("chapter_allocation", {}),
    }


def _on_arc_adjusted(state, event):
    payload = event["payload"]
    arc_id = payload.get("arc_id")
    if arc_id in state.arcs:
        state.arcs[arc_id]["chapter_allocation"] = payload.get("new_plan", {})


def _on_foreshadow_set(state, event):
    payload = event["payload"]
    fid = payload.get("foreshadow_id")
    state.foreshadows[fid] = {
        "source_chapter": payload.get("source_chapter"),
        "target_chapter": payload.get("target_chapter"),
        "hint_text": payload.get("hint_text"),
    }


def _on_foreshadow_resolved(state, event):
    payload = event["payload"]
    fid = payload.get("foreshadow_id")
    if fid in state.foreshadows:
        resolved = state.foreshadows.pop(fid)
        resolved["resolution_chapter"] = payload.get("resolution_chapter")
        resolved["resolution_text"] = payload.get("resolution_text")
        state.resolved_foreshadows[fid] = resolved


def _on_power_updated(state, event):
    payload = event["payload"]
    char_id = payload.get("char_id")
    state.power_map[char_id] = payload.get("new_power")


def _on_fatigue_checked(state, event):
    payload = event["payload"]
    ch_id = payload.get("chapter_id")
    state.fatigue_scores[ch_id] = {
        "score": payload.get("fatigue_score"),
        "prediction": payload.get("action_quality_prediction"),
    }
```

### 10.2 Pipeline 集成示例

```python
# pipeline.py（核心修改部分）

def run_pipeline(project_id, chapter_nums, context):
    """运行完整的小说生成管线"""
    
    for ch_num in chapter_nums:
        # 1. 起草
        draft_result = draft_chapter(project_id, ch_num)
        post_step_hook({
            "has_changes": True,
            "event_type": "CHAPTER_DRAFTED",
            "chapter_id": f"ch-{ch_num:03d}",
            "payload": {
                "chapter_title": draft_result["title"],
                "content_hash": draft_result["hash"],
                "word_count": draft_result["word_count"],
                "draft_version": draft_result["version"],
            },
        }, context)
        
        # 2. 编辑
        edit_result = edit_chapter(project_id, ch_num)
        post_step_hook({
            "has_changes": True,
            "event_type": "CHAPTER_EDITED",
            "chapter_id": f"ch-{ch_num:03d}",
            "payload": {
                "content_hash": edit_result["hash"],
                "edit_summary": edit_result["summary"],
                "editor_version": edit_result["version"],
                "review_score": edit_result["score"],
            },
        }, context)
    
    # 不再需要 sync_to_mongodb()
    logger.info("管线完成，所有事件已实时写入 event log")
```

---

## 11. 迁移路径：V2 → V3

### 11.1 一次性迁移脚本

```python
# migrate_v2_to_v3.py

def migrate_project(project_slug):
    """
    将 V2 项目迁移到 V3 事件溯源
    
    流程：
    1. 读取本地所有章节文件
    2. 读取本地角色/世界状态
    3. 按时间顺序生成初始 event log
    4. 生成初始快照
    5. 验证一致性
    """
    db = get_db()
    
    # 1. 读取本地文件
    chapters = read_chapters_from_local(project_slug)
    characters = read_characters_from_local(project_slug)
    world_state = read_world_state_from_local(project_slug)
    
    # 2. 生成初始事件
    for ch_id, ch_data in sorted(chapters.items()):
        emit_event(
            event_type="CHAPTER_DRAFTED",
            project_id=project_slug,
            payload={
                "chapter_title": ch_data["title"],
                "content_hash": ch_data["hash"],
                "word_count": ch_data["word_count"],
                "draft_version": 1,
            },
            chapter_id=ch_id,
            source="migration",
        )
    
    # 3. 生成初始快照
    state = fold_events(project_slug)
    _generate_snapshot(project_slug, state.version)
    
    # 4. 标记迁移完成
    db.project_meta.update_one(
        {"_id": project_slug},
        {"$set": {
            "event_sourcing_version": 3,
            "migrated_at": datetime.utcnow(),
            "event_count": state.version,
        }},
        upsert=True
    )
```

### 11.2 迁移检查清单

- [ ] V2 的 `novel.novels` 和 `novel.chapters` 数据保留（只读不再写入）
- [ ] V3 写入 `novel_factory.event_log` 和 `novel_factory.snapshot_store`
- [ ] V2 的 `sync-novel-to-mongodb.py` 脚本废弃或改为兼容 V3 的只读工具
- [ ] 所有 Agent 的 post-step hook 已接入
- [ ] 本地缓存重建验证通过

---

## 12. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| MongoDB 写入失败（网络故障） | event 丢失 | 3 次重试 + 写入失败时抛异常阻断步骤执行（宁可中止也不要半写） |
| 版本号冲突 | 版本号跳跃或重复 | `get_next_version()` 使用原子 `findAndModify` 确保严格递增 |
| 快照生成太慢阻塞主流程 | CLI 响应变慢 | 快照生成异步执行（线程/任务队列），不阻塞主流程 |
| 事件膨胀导致折叠变慢 | `fold_events()` 响应退化 | 每 100 event 快照确保折叠复杂度 O(number_of_snapshots + 100) |
| 回滚后逻辑矛盾 | 后续生成质量下降 | 回滚时记录 `ROLLBACK_EXECUTED` 事件，LLM Agent 可感知回滚历史 |
| 本地文件被误删除 | 缓存丢失 | `rebuild_local_from_event_log()` 可从 event log 完全重建 |
| 多个 CLI 实例并行写入 | 事件顺序错乱 | 暂不支持多实例并行（single-writer pattern）；未来可加分布式锁 |

---

> **总结**：V3 的事件溯源系统将 novel-factory 的同步从「最后一次性批量操作」改为「每个步骤实时写入」，MongoDB 成为唯一真相源，本地文件成为可丢弃的缓存层。这消除了 V2 最大的数据不一致风险，同时提供了任意点回滚、完整审计追踪等新能力。
