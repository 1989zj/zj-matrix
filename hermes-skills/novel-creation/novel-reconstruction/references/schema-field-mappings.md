# MongoDB Schema 字段名映射 & 校验规则

本文件记录了 Phase 0 Reconstruction 过程中发现的 MongoDB `$jsonSchema` 实际字段名,
用于避免「按文档写的字段名→WriteError code 121」的坑。

## novel_factory.arcs

| 想法字段 | 实际字段 | 备注 |
|---------|---------|------|
| `name` | `title` | arcs 用 title, 不是 name |
| `description` | 无此字段 | 用 `goal` + `core_conflict` 替代 |
| `chapters` (数组) | 不存在 | 无 chapters 字段, 用 start/end + timeline 推算 |
| `status` | 存在 | 可用 |

**Schema required**: `project_id`, `arc_id`, `title`
**其他字段**: `goal`, `start_chapter`(int), `end_chapter`(int), `core_conflict`, `major_twists`(array), `ending_hook`, `theme`, `antagonist`, `word_count_target`

## novel_factory.foreshadow

| 想法字段 | 实际字段 | 备注 |
|---------|---------|------|
| `description` | `content` | 伏笔内容在 content, 不是 description |
| `callback_chapter` | `suggested_callback_ch` | 建议回收章节 |
| `expected_callback_chapter` | 不存在 | 用 suggested_callback_ch |
| `status` | 存在 | 值为 `pending`(默认) / `active` / `resolved` |
| `foreshadow_id` | 存在 | 如 `fsh_001_designer_escape_door` |
| `setup_chapter` | 存在 | int |
| `urgency` | 存在 | 值为 `🔴紧急(>80章)` 等（需标准化） |
| `planned_payoff` | 存在 | 字符串 |
| `primary_payoff` | 存在 | 字符串 |

**Schema required**: `project_id`, `foreshadow_id`, `content`

## novel_factory.foreshadow_queue

**Schema required**: `project_id`, `foreshadow_id`, `description`, `setup_chapter`

| 字段 | 类型 | 约束 |
|------|------|------|
| `urgency` | string | **enum**: `['low', 'medium', 'high', 'critical']` — 不能含 emoji |
| `deadline_chapter` | int | 可选 |
| `priority` | int | 可选 |

**标准化 urgency**:
- `🔴紧急(>80章)` → `critical`
- `🟡一般(50-80章)` → `medium`  
- `🟢不急(<50章)` → `low`

## novel_factory.event_log

**Schema required**: `project_id`, `event_type`, `chapter`, `timestamp`

| 字段 | 类型 | 约束 |
|------|------|------|
| `event_type` | string | **enum**: `chapter_started`, `chapter_generated`, `chapter_validated`, `editor_completed`, `world_updated`, `character_states_updated`, `foreshadow_created`, `foreshadow_resolved`, `snapshot_saved`, `arc_completed`, `project_created`, `resume_session`, `error` |
| `data` | object | 存放具体事件数据, 如 `{'summary': ..., 'source': 'reconstruction'}` |
| `version` | int | 可选, 现有数据为 1 |
| `timestamp` | **date** (datetime) | 必须是 Python datetime 对象, 不能是字符串! 即使现有数据存的是字符串 `"2026-05-18 08:41:02.127000"`, 但 `$jsonSchema` 要求 `bsonType: 'date'` |

**注意**: 现有 23 条 event_log 的 timestamp 是字符串格式,
但新增时必须传 datetime 对象。
如果传字符串会报 WriteError `'timestamp': type did not match, consideredType: string`。

## novel_factory.character_states

**Schema required**: `project_id`, `character`(string), `chapter`(int), `updated_at`(date)

## novel_factory.chapter_memory

**Schema required**: `project_id`, `chapter`(int)
**其他字段**: `title`(string), `summary`(string), `important_events`(array), `new_characters`(array), `power_changes`(array), `hook`(string), `characters`(array), `timeline`(array) — timeline 需迁移自 timeline 集合

## novel_factory.world_bible

**Schema required**: `project_id`
**所有设定字段必须为数组类型**: `world_rules`(array), `power_system`(array), `economy_system`(array), `factions`(array), `regions`(array), `forbidden_rules`(array)

## 通用注意事项

1. **project_id 过滤**: 多数 collection 用 `project_id` 区分项目, 但不是所有 collection 都有 `project_id` 索引。创建新 doc 时必须包含 `project_id`。
2. **int 类型**: chapter/start_chapter/end_chapter 必须为 int, 不能是字符串。
3. **timestamp 类型**: 要么 datetime 对象, 要么匹配格式。以 `$jsonSchema` 定义为准, 不以现有数据为准。
4. **enum 约束**: 字符串枚举值必须精确匹配（大小写敏感, 无 emoji）。
5. **array 字段**: 如果不能确定内容, 初始化为 `[]` 而非省略。
