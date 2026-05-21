# 手动 Analytics & Refresh（替代子会话方案）

`novel-factory refresh` 的子会话方式可能超时或找不到项目。以下是在主 agent 中直接执行 refresh 的可靠方案。

## 适用场景

- `novel-factory refresh <项目名>` 超时或无响应
- 需要包含具体分析数据的格式化报告输出
- 需要在 refresh 后立即规划下一 ARC

## 完整操作步骤

### 步骤 1：连接 MongoDB 读取全量数据

```python
from pymongo import MongoClient
from collections import Counter, defaultdict

client = MongoClient('mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/')
db = client['novel_factory']

# 项目 ID 可从 projects 按 title 查询
pid = db['projects'].find_one({'title': '诡异游戏：我的规则别人看不见'})['project_id']
```

### 步骤 2：读取各 collection 统计

```python
# 总览
proj = db['projects'].find_one({'project_id': pid})

# ARC 详情
arcs = list(db['arcs'].find({'project_id': pid}).sort('arc_id', 1))
for a in arcs:
    print(f"{a['arc_id']}: ch{a['start_chapter']}-ch{a['end_chapter']}, {a['status']}")

# 角色
chars = list(db['characters'].find({'project_id': pid}))
for c in chars:
    print(f"{c['name']}: {c['status']}, arcs {c.get('arc_appearances', [])}")

# 章节统计
chapters = list(db['chapter_memory'].find({'project_id': pid}))

# ARC 按键值分组统计字数
arc_words = defaultdict(int)
arc_chapters = defaultdict(list)
emotions = Counter()
hooks_count = 0
for ch in chapters:
    arc = ch.get('arc_id', 'unknown')
    arc_words[arc] += ch.get('word_count', 0) or 0
    arc_chapters[arc].append(ch['chapter'])
    et = ch.get('emotion_tone', '')
    if et:
        emotions[et] += 1
    if ch.get('hook', ''):
        hooks_count += 1

# 时间线事件
tl_count = db['timeline'].count_documents({'project_id': pid})
tl_events = list(db['timeline'].find({'project_id': pid}).sort('chapter', 1))
chs_with_events = set(ev.get('chapter', 0) for ev in tl_events)

# 伏笔
fs = list(db['foreshadow'].find({'project_id': pid}))
```

### 步骤 3：计算关键指标

| 指标 | 计算方式 | 阈值 |
|------|---------|------|
| 情绪多样性 | `len(emotions)` | >1 避免单一 |
| 章末钩子覆盖率 | `hooks_count / total_chapters` | >80% |
| 伏笔回收率 | `paid_off / total_foreshadow` | >30% |
| 角色活跃度 | 每 ARC 角色变更数 | 应有角色退场/加入 |
| ARC 完整性 | ARC 章节数 vs 规划数 | ±10% |
| 平均字数 | `total_words / total_chapters` | 2000-3000 |

### 步骤 4：生成风险清单

```python
risks = []
if len(emotions) <= 1:
    risks.append(f'emotion_tone_uniform — {total_chapters}章全部是"{list(emotions.keys())[0] if emotions else "?"}"')
if hooks_count == 0:
    risks.append('hooks_empty — 0/{total_chapters}章有 hook 字段')
if len(fs) <= 1:
    risks.append('foreshadow_db_empty — 只有 {len(fs)} 个条目')
if all(a.get('status') == 'completed' for a in arcs):
    risks.append('no_active_arc — 所有 ARC 已完成，下一 ARC 未规划')
# 检查 ARC metadata
empty_meta = sum(1 for a in arcs if not a.get('core_conflict'))
if empty_meta > 0:
    risks.append(f'arc_metadata_empty — {empty_meta}/{len(arcs)}个ARC缺少core_conflict')
```

### 步骤 5：写入 MongoDB（analytics 结果）

注意 `checked_at` 字段必须为 **string** 类型（MongoDB schema 要求）：

```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc).isoformat()

analytics_doc = {
    'project_id': pid,
    'chapter': total_chapters,  # 最新章号
    'checked_at': now,          # ⚠️ 字符串，不是 datetime 对象
    'duplicate_score': 0.0,
    'duplicate_items': [],
    'analytics_report': {
        'total_chapters': total_chapters,
        'total_words': total_words,
        'avg_words_per_chapter': total_words // total_chapters,
        'arc_details': [...],
        'risks': risks,                    # 风险项列表
        'scores': {
            'foreshadow_recovery_rate': ...,
            'emotion_tone_diversity': ...,
            'chapter_hook_coverage': ...,
            'timeline_coverage': len(chs_with_events) / total_chapters,
        },
        'recommendations': [...]           # 建议列表
    },
    'status': 'refresh_completed'
}

# 删除旧的占位条目，写入新的
db['anti_repetition'].delete_many({'project_id': pid})
db['anti_repetition'].insert_one(analytics_doc)

# 更新项目时间戳
db['projects'].update_one(
    {'project_id': pid},
    {'$set': {'last_refresh_at': now, 'refresh_count': 1}}
)
```

### 步骤 6：输出格式化报告给用户

报告结构（自然语言输出，按优先级排序）：
1. 项目总览（字数/章数/ARC 完成数）
2. ✅ 绿灯指标
3. ⚠️ 风险项（按严重程度排序）
4. 💡 建议（按执行优先级排序）

## 注意事项

- **`checked_at` 必须是字符串**：MongoDB JSON Schema 要求 `bsonType: "string"`，传 datetime 会报 WriteError 121
- **项目名必须精确匹配**：在 projects 中按 title 查询时，用完整全名
- **`arc_appearances` 检查**：如果所有角色出现在所有 ARC 中，说明需要让角色退场
- **`hook` 字段为空不一定是风险**：V1 迁移的数据可能没有 hook 字段，新创作才需要补
- **`emotion_tone` 字段**：V1 迁移数据可能所有章都一样，不代表正文真的单调，但需要关注
- **仅 analytics 可手动写入**：这是只读分析层。对主数据（characters/arcs/world_bible）的修改仍必须走 memory-manager
