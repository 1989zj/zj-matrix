# Novel Factory V3 — MongoDB 集合 Schema（精确版）

> 最后更新: 2026-05-18
> 版本: V3（V2 + 世界状态机 + 事件驱动架构）
> 数据库: `novel_factory` (192.168.2.30:27017)
> 认证: `mongo_8F6dTZ:mongo_dxx8nA`

**说明**: V3 所有集合均带有 `$jsonSchema` 校验规则。写入时必须精确匹配字段名和类型，否则 MongoDB 会拒绝写入（WriteError code 121）。V3 在 V2 的 8 个 collection 基础上新增了 6 个 collection，替换/升级了 2 个。

连接方式:
```python
from pymongo import MongoClient
client = MongoClient('mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/')
db = client['novel_factory']
```

---

## 1. projects — 小说项目元数据

```json
{
  "$jsonSchema": {
    "required": ["project_id", "title", "status", "target_words"],
    "properties": {
      "project_id":     {"bsonType": "string"},
      "title":          {"bsonType": "string"},
      "genre":          {"bsonType": "string"},
      "target_platform": {"bsonType": "string"},
      "target_words":   {"bsonType": "int"},
      "status":         {"bsonType": "string"},
      "current_arc":    {"bsonType": "int"},
      "total_chapters": {"bsonType": "int"},
      "total_words":    {"bsonType": "int"},
      "created_at":     {"bsonType": "string"},
      "updated_at":     {"bsonType": "string"}
    }
  }
}
```

**坑**:
- `created_at` / `updated_at` 必须是字符串（ISO格式），不是 datetime 对象
- `target_words` 是 `int`，不是 `long` 或嵌套在 `stats` 里
- 非 schema 字段（如 `synopsis`, `tags`, `slug`, `v1_migrated`）可以添加——MongoDB 不拒绝超集
- `current_arc` 是当前已完成 ARC 数，**不等于** ARC 集合中的文档数

### 迁移示例
```python
from datetime import datetime, timezone
now_str = datetime.now(timezone.utc).isoformat()

project = {
    'project_id': f"proj_{slug}_{uuid.uuid4().hex[:8]}",
    'title': novel_v1.get('title', name),
    'genre': novel_v1.get('genre', ''),
    'target_platform': novel_v1.get('target', '起点中文网'),
    'target_words': 5000000,  # int, not long
    'status': '连载中',
    'current_arc': arc_count,
    'total_chapters': len(chapters),
    'total_words': total_words,
    'created_at': now_str,  # string, not datetime
    'updated_at': now_str,
    # extra fields (allowed, not in schema):
    'slug': slug,
    'synopsis': novel_v1.get('synopsis', ''),
    'v1_migrated': True,
}
```

---

## 2. characters — 角色数据库

```json
{
  "$jsonSchema": {
    "required": ["project_id", "character_id", "name"],
    "properties": {
      "project_id":     {"bsonType": "string"},
      "character_id":   {"bsonType": "string"},
      "name":           {"bsonType": "string"},
      "role":           {"bsonType": "string"},
      "age":            {"bsonType": "string"},
      "personality":    {"bsonType": "array"},
      "goals":          {"bsonType": "array"},
      "relationships":  {"bsonType": "array"},
      "abilities":      {"bsonType": "array"},
      "status":         {"bsonType": "string"},
      "growth_arc":     {"bsonType": "array"},
      "taboos":         {"bsonType": "array"},
      "memory_summary": {"bsonType": "string"},
      "first_appearance":  {"bsonType": "int"},
      "last_appearance":   {"bsonType": "int"},
      "arc_appearances":   {"bsonType": "array"}
    }
  }
}
```

**迁移映射** (V1 character → V2):
| V1 字段 | V2 字段 | 说明 |
|---------|---------|------|
| `name` | `name` | 直接映射 |
| `title` | `role` | 主角→主角, 女主→女主 等 |
| `traits` | `personality` | 数组直接映射 |
| `ability` | `abilities` | 单字符串包装为数组（1个元素） |
| `desc` | `memory_summary` | 角色描述/记忆 |
| — | `age` | 从 desc 提取或留空字符串 |
| — | `first_appearance` | 默认为 1 |
| — | `last_appearance` | 默认为总章节数 |

---

## 3. world_bible — 世界观圣经

```json
{
  "$jsonSchema": {
    "required": ["project_id"],
    "properties": {
      "project_id":       {"bsonType": "string"},
      "world_rules":      {"bsonType": "array"},
      "power_system":     {"bsonType": "array"},
      "economy_system":   {"bsonType": "array"},
      "factions":         {"bsonType": "array"},
      "regions":          {"bsonType": "array"},
      "forbidden_rules":  {"bsonType": "array"},
      "history_events":   {"bsonType": "array"},
      "version":          {"bsonType": "int"}
    }
  }
}
```

**注意**: V2 所有字段都是 **数组**，不是对象/字典。V1 的 `power_system` 是嵌套对象（含 name/levels/source/note），迁移时需要包装为 `[{...}]`。

**迁移映射**:
```python
world = v1_novel.get('world', {})
world_bible = {
    'project_id': pid,
    'world_rules': [{'rule': k, 'desc': v} for k, v in world.get('timeline', {}).items()],
    'power_system': [world.get('power_system', {})],  # 包装为单元素数组
    'economy_system': [],
    'factions': [{'name': k, 'desc': v} for k, v in world.get('factions', {}).items()],
    'regions': [],
    'forbidden_rules': [],
    'history_events': [{'key': k, 'desc': v} for k, v in world.get('timeline', {}).items()],
    'version': 1,
}
```

---

## 4. arcs — 剧情弧

```json
{
  "$jsonSchema": {
    "required": ["project_id", "arc_id", "title"],
    "properties": {
      "project_id":       {"bsonType": "string"},
      "arc_id":           {"bsonType": "string"},
      "title":            {"bsonType": "string"},
      "goal":             {"bsonType": "string"},
      "start_chapter":    {"bsonType": "int"},
      "end_chapter":      {"bsonType": "int"},
      "core_conflict":    {"bsonType": "string"},
      "major_twists":     {"bsonType": "array"},
      "ending_hook":      {"bsonType": "string"},
      "status":           {"bsonType": "string"},
      "theme":            {"bsonType": "string"},
      "antagonist":       {"bsonType": "string"},
      "word_count_target": {"bsonType": "int"}
    }
  }
}
```

**ARC 划分策略**: 每 ARC 约 35 章 / 8-10 万字。但 300 万字规划下按 10-15 万字/ARC 计算。

**弧命名规范**:
- `ARC-001`, `ARC-002`, ..., always zero-padded to 3 digits
- 迁移已写内容时，用 V1 卷结构映射（卷一·B-7设施, 卷二·北上, 卷三·烬城, ...）

---

## 5. chapter_memory — 章节记忆

```json
{
  "$jsonSchema": {
    "required": ["project_id", "chapter"],
    "properties": {
      "project_id":         {"bsonType": "string"},
      "chapter":            {"bsonType": "int"},
      "title":              {"bsonType": "string"},
      "summary":            {"bsonType": "string"},
      "important_events":   {"bsonType": "array"},
      "new_characters":     {"bsonType": "array"},
      "power_changes":      {"bsonType": "array"},
      "relationship_changes": {"bsonType": "array"},
      "emotion_tone":       {"bsonType": "string"},
      "hook":               {"bsonType": "string"},
      "arc_id":             {"bsonType": "string"}
    }
  }
}
```

**注意**: `chapter` 是 int（不是 `chapter_number`）。V1 的 `chapterNumber` 直接映射。

**迁移**: 可以添加非 schema 字段（如 `content`, `word_count`, `version`）保存完整原文，schema 不拒绝超集。

**summary 生成策略**: 截取 content 前 200 字符 + "..."，迁移后可由 analytics 逐步优化。

---

## 6. timeline — 时间线

```json
{
  "$jsonSchema": {
    "required": ["project_id", "chapter"],
    "properties": {
      "project_id":           {"bsonType": "string"},
      "arc_id":               {"bsonType": "string"},
      "chapter":              {"bsonType": "int"},
      "date":                 {"bsonType": "string"},
      "event":                {"bsonType": "string"},
      "affected_characters":  {"bsonType": "array"},
      "world_changes":        {"bsonType": "array"},
      "importance":           {"bsonType": "int"}
    }
  }
}
```

**importance 分级**:
- 1 = 常规章节事件
- 2 = 世界观/历史背景
- 3 = 关键转折/重大事件（灾变、锚点）

---

## 7. foreshadow — 伏笔数据库

```json
{
  "$jsonSchema": {
    "required": ["project_id", "foreshadow_id", "content"],
    "properties": {
      "project_id":       {"bsonType": "string"},
      "foreshadow_id":    {"bsonType": "string"},
      "setup_chapter":    {"bsonType": "int"},
      "content":          {"bsonType": "string"},
      "planned_payoff":   {"bsonType": "string"},
      "payoff_chapter":   {"bsonType": "int"},
      "status":           {"bsonType": "string"},
      "type":             {"bsonType": "string"},
      "arc_id":           {"bsonType": "string"}
    }
  }
}
```

**status 枚举**: `pending` → `active` → `resolved` → `abandoned`

---

## 8. anti_repetition — 重复检测

```json
{
  "$jsonSchema": {
    "required": ["project_id", "chapter"],
    "properties": {
      "project_id":       {"bsonType": "string"},
      "chapter":          {"bsonType": "int"},
      "duplicate_score":  {"bsonType": "double"},
      "duplicate_items":  {"bsonType": "array"},
      "status":           {"bsonType": "string"},
      "checked_at":       {"bsonType": "string"}
    }
  }
}
```

---

---

## 9. world_state — 世界状态快照（V3 新增）

```json
{
  "$jsonSchema": {
    "required": ["project_id", "economy", "public_opinion", "capital_attention", "city_influence"],
    "properties": {
      "project_id":         {"bsonType": "string"},
      "economy":            {"bsonType": "string", "enum": ["bull", "bear", "stable", "crisis", "recovery"]},
      "public_opinion":     {"bsonType": "object", "additionalProperties": {"bsonType": "int"}},
      "capital_attention":  {"bsonType": "int", "minimum": 0, "maximum": 100},
      "city_influence":     {"bsonType": "int", "minimum": 0, "maximum": 100},
      "faction_power":      {"bsonType": "array"},
      "news_feed":          {"bsonType": "array"},
      "current_crisis":     {"bsonType": ["null", "object"]},
      "version":            {"bsonType": "int"}
    }
  }
}
```

**faction_power 元素结构**:
```json
{
  "faction_name": "string",
  "power_level": "int (0-100)",
  "attitude_to_protagonist": "string (友好/中立/敌对/警惕/合作)",
  "last_interaction": "int (章节号)"
}
```

**news_feed 元素结构**:
```json
{
  "headline": "string",
  "impact": "int (1-10)",
  "timestamp": "string (ISO format)"
}
```

**current_crisis 结构（非 null 时）**:
```json
{
  "type": "string (势力冲突/经济危机/身份曝光/灾难事件/家族斗争)",
  "severity": "int (1-10)",
  "involved_factions": ["string"],
  "deadline_chapter": "int"
}
```

---

## 10. character_states — 角色动态状态（V3 新增）

> **与 V2 characters collection 的关系**: `characters` 是角色档案（不变信息），`character_states` 是每章后更新的动态状态（变化信息）。两个 collection 通过 `character_id` 关联。

```json
{
  "$jsonSchema": {
    "required": ["project_id", "character_id", "current_state"],
    "properties": {
      "project_id":               {"bsonType": "string"},
      "character_id":             {"bsonType": "string"},
      "name":                     {"bsonType": "string"},
      "base_personality":         {"bsonType": "array"},
      "current_state": {
        "bsonType": "object",
        "required": ["emotion", "trust", "fatigue", "wealth", "combat_level"],
        "properties": {
          "emotion":     {"bsonType": "string", "enum": ["愤怒","悲伤","恐惧","喜悦","平静","焦虑","疯狂","兴奋","沮丧","警惕","绝望","希望"]},
          "trust":       {"bsonType": "int", "minimum": 0, "maximum": 100},
          "fatigue":     {"bsonType": "int", "minimum": 0, "maximum": 100},
          "wealth":      {"bsonType": "long"},
          "combat_level": {"bsonType": "int"},
          "influence":   {"bsonType": "int", "minimum": 0, "maximum": 100},
          "sanity":      {"bsonType": "int", "minimum": 0, "maximum": 100},
          "loyalty":     {"bsonType": "int", "minimum": 0, "maximum": 100},
          "morale":      {"bsonType": "int", "minimum": 0, "maximum": 100}
        }
      },
      "relationship_graph":       {"bsonType": "object"},
      "recent_memory":            {"bsonType": "array"},
      "long_term_goal":           {"bsonType": "array"},
      "hidden_flags":             {"bsonType": "array"},
      "last_updated_chapter":     {"bsonType": "int"},
      "version":                  {"bsonType": "int"}
    }
  }
}
```

**relationship_graph 结构**:
```json
{
  "<character_id>": {
    "relationship": "string (友好/敌对/暗恋/仇恨/合作/师徒/利用/畏惧/感激/鄙视)",
    "trust_score": "int (0-100)",
    "description": "string",
    "history": [{"chapter": "int", "event": "string", "delta": "int"}]
  }
}
```

**recent_memory 结构**（最多 5 条）:
```json
{
  "chapter": "int",
  "event": "string (一句话概括与该角色相关的关键事件)",
  "importance": "int (1-5)"
}
```

---

## 11. arc_plans — 动态 ARC 规划（V3 新增，增强版）

> **与 V2 arcs collection 的关系**: `arcs` 继续存在作为已完成的 ARC 归档。`arc_plans` 是四层动态规划体系，包含规划中和已完成的所有层级。它们不同步——arc_plans 是规划层，arcs 是归档层。

```json
{
  "$jsonSchema": {
    "required": ["project_id", "arc_id", "type", "title", "status"],
    "properties": {
      "project_id":       {"bsonType": "string"},
      "arc_id":           {"bsonType": "string"},
      "type":             {"bsonType": "string", "enum": ["world", "phase", "beat", "chapter"]},
      "title":            {"bsonType": "string"},
      "parent_arc_id":    {"bsonType": ["null", "string"]},
      "status":           {"bsonType": "string", "enum": ["planning", "active", "completed", "archived"]},
      "goal":             {"bsonType": "string"},
      "core_conflict":    {"bsonType": "string"},
      "start_chapter":    {"bsonType": "int"},
      "end_chapter":      {"bsonType": "int"},
      "twists":           {"bsonType": "array"},
      "ending_hook":      {"bsonType": "string"},
      "theme":            {"bsonType": "string"},
      "antagonist":       {"bsonType": "string"},
      "word_count_target": {"bsonType": "int"},
      "adjustment_reason": {"bsonType": "string"},
      "adjusted_at":      {"bsonType": "string"},
      "created_at":       {"bsonType": "string"},
      "version":          {"bsonType": "int"}
    }
  }
}
```

**type 层级说明**:
| type | 范围 | 说明 |
|------|------|------|
| `world` | 全书 | 终极 ARC，全书只有一个，500 万字目标 |
| `phase` | ~100 章 | 故事阶段，全书 5-6 个 |
| `beat` | ~20 章 | 故事节拍，每个 phase 下 3-5 个 |
| `chapter` | 1 章 | 单章目标，每个 beat 下 15-20 个 |

---

## 12. foreshadow_queue — 伏笔队列（V3 新增，升级版 foreshadow）

> **与 V2 foreshadow collection 的关系**: 功能升级。V3 的 `foreshadow_queue` 包含完整的 deadline/priority/urgency 系统。V2 的 `foreshadow` 会逐步迁移到 V3 格式。

```json
{
  "$jsonSchema": {
    "required": ["project_id", "foreshadow_id", "content", "deadline_chapter"],
    "properties": {
      "project_id":         {"bsonType": "string"},
      "foreshadow_id":      {"bsonType": "string"},
      "content":            {"bsonType": "string"},
      "setup_chapter":      {"bsonType": "int"},
      "deadline_chapter":   {"bsonType": "int"},
      "priority":           {"bsonType": "string", "enum": ["high", "medium", "low"]},
      "type":               {"bsonType": "string", "enum": ["角色", "物品", "能力", "事件", "秘密"]},
      "status":             {"bsonType": "string", "enum": ["active", "pending", "resolved", "expired"]},
      "urgency":            {"bsonType": "double"},
      "resolved_chapter":   {"bsonType": "int"},
      "payoff_description": {"bsonType": "string"},
      "arc_id":             {"bsonType": "string"},
      "linked_foreshadow_ids": {"bsonType": "array"}
    }
  }
}
```

**urgency 计算**: `base_value(基于 deadline - current_chapter) + priority_bonus + type_bonus`，范围 0.0-10.0

| priority | deadline |
|---------|---------|
| high | 20 章内 |
| medium | 40 章内 |
| low | 80 章内 |

---

## 13. plot_debt — 剧情债务（V3 新增）

> 剧情债务是「对读者的承诺」。包括：未兑现的伏笔、角色承诺、剧情伏线、读者期待。与 foreshadow_queue 互补——foreshadow_queue 管具体伏笔，plot_debt 管更大的剧情承诺。

```json
{
  "$jsonSchema": {
    "required": ["project_id", "debt_id", "content", "created_chapter"],
    "properties": {
      "project_id":         {"bsonType": "string"},
      "debt_id":            {"bsonType": "string"},
      "content":            {"bsonType": "string"},
      "type":               {"bsonType": "string", "enum": ["伏笔未收", "角色承诺", "剧情伏线", "读者期待", "世界观未解", "关系未定"]},
      "created_chapter":    {"bsonType": "int"},
      "expected_payoff":    {"bsonType": "string"},
      "deadline_chapter":   {"bsonType": "int"},
      "severity":           {"bsonType": "string", "enum": ["critical", "major", "minor"]},
      "status":             {"bsonType": "string", "enum": ["open", "in_progress", "resolved", "abandoned"]},
      "resolved_chapter":   {"bsonType": "int"},
      "reader_attention":   {"bsonType": "double", "description": "读者关注度，基于提及频率推断，0.0-1.0"},
      "linked_foreshadow_ids": {"bsonType": "array"},
      "notes":              {"bsonType": "string"}
    }
  }
}
```

---

## 14. event_log — 事件溯源日志（V3 新增）

> Append-only 事件日志，所有写操作的权威记录。MongoDB 是唯一真相源，本地文件只是缓存层。

```json
{
  "$jsonSchema": {
    "required": ["event_id", "event_type", "project_id", "payload", "timestamp", "version"],
    "properties": {
      "event_id":           {"bsonType": "string"},
      "event_type":         {"bsonType": "string", "enum": [
        "CHAPTER_DRAFTED", "CHAPTER_EDITED", "CHARACTER_UPDATED",
        "WORLD_UPDATED", "ARC_CREATED", "ARC_ADJUSTED",
        "FORESHADOW_SET", "FORESHADOW_RESOLVED", "PLOT_DEBT_CREATED",
        "PLOT_DEBT_RESOLVED", "POWER_UPDATED", "FATIGUE_CHECKED",
        "CONTEXT_PACKET_GENERATED", "STATE_SNAPSHOT", "CHARACTER_STATE_UPDATED",
        "WORLD_SIM_UPDATED", "ROLBACK"
      ]},
      "project_id":         {"bsonType": "string"},
      "payload":            {"bsonType": "object"},
      "timestamp":          {"bsonType": "string"},
      "version":            {"bsonType": "int"}
    }
  }
}
```

**索引**:
```javascript
{event_type: 1, project_id: 1, version: 1}
{project_id: 1, version: 1}
{project_id: 1, timestamp: -1}
```

---

## 15. snapshot_store — 状态快照（V3 新增）

> 每 100 个 event_log 事件生成一个全库状态快照，避免回滚时从头重放所有事件。

```json
{
  "$jsonSchema": {
    "required": ["snapshot_id", "project_id", "event_version", "snapshot"],
    "properties": {
      "snapshot_id":        {"bsonType": "string"},
      "project_id":         {"bsonType": "string"},
      "event_version":      {"bsonType": "int"},
      "snapshot":           {"bsonType": "object"},
      "created_at":         {"bsonType": "string"}
    }
  }
}
```

---

## 16. anti_fatigue — 疲劳检测记录（V3 新增，升级版 anti_repetition）

> **与 V2 anti_repetition collection 的关系**: 功能升级。V3 的 `anti_fatigue` 包含七维疲劳检测、干预策略、与 arc-manager 的集成。V2 的 `anti_repetition` 保留作兼容，但新检测统一写入 `anti_fatigue`。

```json
{
  "$jsonSchema": {
    "required": ["project_id", "chapter", "scores", "overall_score"],
    "properties": {
      "project_id":       {"bsonType": "string"},
      "chapter":          {"bsonType": "int"},
      "overall_score":    {"bsonType": "double", "minimum": 0, "maximum": 1.0},
      "levels":           {"bsonType": "string", "enum": ["safe", "warning", "critical", "emergency"]},
      "scores":           {"bsonType": "object"},
      "duplicate_items":  {"bsonType": "array"},
      "intervention_suggestions": {"bsonType": "array"},
      "arc_impact":       {"bsonType": "object"},
      "status":           {"bsonType": "string", "enum": ["pass", "warn", "intervene"]},
      "checked_at":       {"bsonType": "string"}
    }
  }
}
```

**scores 对象结构**:
```json
{
  "爽点重复率": {"value": 0.0-1.0, "weight": 0.25},
  "台词重复率": {"value": 0.0-1.0, "weight": 0.10},
  "情绪曲线分析": {"value": 0.0-1.0, "weight": 0.15},
  "装逼密度": {"value": 0.0-1.0, "weight": 0.10},
  "打脸模板匹配": {"value": 0.0-1.0, "weight": 0.20},
  "战斗模式分析": {"value": 0.0-1.0, "weight": 0.10},
  "地图场景复用": {"value": 0.0-1.0, "weight": 0.10}
}
```

---

## V3 额外坑点

| 坑 | 后果 | 解决 |
|----|------|------|
| character_states 的 `wealth` 是 long 不是 int | WriteError code 121 | 神豪流金额可能 > 21 亿（int 上限），必须用 long |
| world_state 每章版本号递增冲突 | 版本不一致 | 写前用 `$set` 而非 `$inc` |
| event_log append 性能 | 100 万事件后查询慢 | 定期创建 snapshot 后 purge 旧日志 |
| 两个 log 写同一 project 的版本号竞争 | 版本冲突 | 用 `findOneAndUpdate` 原子递增 |
| plot_debt 与 foreshadow_queue 数据交叉 | 重复/矛盾 | 用 `linked_foreshadow_ids` 关联，不要存两份 |
| **V2 → V3 迁移**: arcs→arc_plans 数据不对齐 | 旧 ARC 在旧集合，新 ARC 在新集合 | arcs 的 data 读入 arc_plans 设为 type=beat，status=completed |

## 通用坑点汇总

| 坑 | 后果 | 解决 |
|----|------|------|
| `created_at` 传了 datetime 而非 string | WriteError code 121 | `datetime.now(timezone.utc).isoformat()` |
| `target_words` 传了 float/long | WriteError code 121 | 显式 `int(...)` |
| `power_system` 传了 dict 而非 array | WriteError code 121 | 包装为 `[dict]` |
| `chapter` 传了 `chapter_number`（string key） | WriteError code 121 | 用 `chapter` 作为 key |
| 非 schema 字段过多导致文档超大 | 可正常写入，但查询变慢 | schema 不拒绝超集，合理即可 |
| 版本历史插入异常中断 | history 写入为无事务 insert_many | 不保证原子性，但主集合事务保证 |
