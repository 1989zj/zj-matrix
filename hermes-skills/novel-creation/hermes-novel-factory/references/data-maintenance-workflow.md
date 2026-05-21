# V3 数据维护与质量审计工作流（Data Maintenance & Audit）

> 最后更新：2026-05-18
> V2→V3 迁移后的数据审计 + V3 新增集合的日常维护

## 适用场景

- V2→V3 迁移后做全量数据摸底
- 已有小说正文 >50 章但从未做过质量审计
- 续写新 ARC 前（建议先跑一次审计）
- 怀疑有角色消失/伏笔丢失/时间线断裂
- **V3 新增**：event_log 断裂、snapshot 陈旧、world_state 不一致

## V3 新增审计项目

V3 新增了 6 个 collection/系统，每个都要做专项审计：

| Collection | 审计项 | 检查内容 |
|-----------|--------|---------|
| `event_log` | 连续性 | 版本号是否连续？有无断层？ |
| `snapshot_store` | 时效性 | 最新快照覆盖了多少 events？ |
| `world_state` | 一致性 | 与最新章节内容是否矛盾？ |
| `character_states` | 时效性 | 所有角色状态是否更新到最新章？ |
| `foreshadow_queue` | 完整性 | 到期伏笔是否已回收？新伏笔是否已入队？ |
| `anti_fatigue` | 报告 | 最新疲劳检测报告是否有警告？ |

## 审计脚本模板

```python
from pymongo import MongoClient
from collections import defaultdict
from datetime import datetime
import re

client = MongoClient('mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin')
db = client['novel_factory']
pid = 'proj_gui-yi-you-xi_d3acfcdd'  # 替换为目标 project_id

# =====================================================
# 1. V2 遗产审计：角色出场检查（与 V2 版一致）
# =====================================================
char_identities = {
    '林远': ['林远'],
    '顾晚': ['顾晚'],
    '赵铁': ['赵铁', '铁哥'],
    '方晴': ['方晴'],
    '周文': ['周文'],
    '老钱': ['老钱', '钱叔'],
    '秦征': ['秦征', '城主'],
    '沈从越': ['沈从越', '沈教授', '从越'],
    '江漓': ['江漓'],
    '陆沉': ['陆沉', '图书馆老人', '馆长'],
    '逐字人': ['逐字人', 'Word Eraser'],
}

all_chapters = list(db['chapter_memory'].find(
    {'project_id': pid},
    {'chapter': 1, 'title': 1, 'summary': 1, 'content': 1, 'arc_id': 1}
).sort('chapter', 1))

char_in_content = defaultdict(set)
char_in_summary = defaultdict(set)

for c in all_chapters:
    ch = c['chapter']
    content = c.get('content', '') or ''
    summary = c.get('summary', '') or ''
    for char_name, aliases in char_identities.items():
        for alias in aliases:
            if alias in content:
                char_in_content[char_name].add(ch)
            if alias in summary:
                char_in_summary[char_name].add(ch)

print('=== 角色出场审计 ===')
print(f"{'角色':<8} {'正文登场':<6} {'摘要提及':<6} {'漏报':<6}")
for char_name in sorted(char_identities.keys()):
    in_c = len(char_in_content[char_name])
    in_s = len(char_in_summary[char_name])
    missing = in_c - in_s
    flag = '⚠️ 从未登场' if in_c == 0 else f'🔧 缺{missing}章' if missing > 0 else '✅'
    print(f"{char_name:<8} {in_c:<6} {in_s:<6} {missing:<6} {flag}")

# =====================================================
# 2. V3 新增审计：event_log 连续性检查
# =====================================================
print('\n=== Event Log 连续性审计 ===')
events = list(db['event_log'].find(
    {'project_id': pid},
    {'version': 1, 'event_type': 1, 'timestamp': 1}
).sort('version', 1))

if events:
    first_v = events[0]['version']
    last_v = events[-1]['version']
    total_events = len(events)
    expected = last_v - first_v + 1
    gaps = expected - total_events
    status = '✅ 连续' if gaps == 0 else f'⚠️ 缺失 {gaps}/{expected} 条事件'
    print(f"版本范围: {first_v} ~ {last_v}")
    print(f"应有 {expected} 条, 实际 {total_events} 条 → {status}")
    print(f"事件类型分布: {dict(Counter(e['event_type'] for e in events))}")
    print(f"时间跨度: {events[0].get('timestamp', '?')[:19]} ~ {events[-1].get('timestamp', '?')[:19]}")
else:
    print('⚠️ event_log 为空——event sourcing 未启用')

# =====================================================
# 3. V3 新增审计：snapshot 时效性
# =====================================================
print('\n=== Snapshot 时效性审计 ===')
snapshots = list(db['snapshot_store'].find(
    {'project_id': pid}
).sort('version', -1).limit(3))

if snapshots:
    latest = snapshots[0]
    print(f"最新 snapshot: version={latest['version']}, 生成于 {datetime.fromtimestamp(latest.get('generated_at',0)).isoformat()}")
    print(f"已落后 {last_v - latest['version']} events")
    if last_v - latest['version'] > 100:
        print('⚠️ snapshot 已过期，需要生成新快照')
else:
    print('⚠️ snapshot_store 为空——需要初始化')

# =====================================================
# 4. V3 新增审计：world_state 一致性检查
# =====================================================
print('\n=== World State 审计 ===')
ws = db['world_state'].find_one({'project_id': pid})
if ws:
    ws_version = ws.get('version', 0)
    ws_chapter = ws.get('current_chapter', 0)
    last_chapter = all_chapters[-1]['chapter'] if all_chapters else 0
    diff = last_chapter - ws_chapter
    if diff > 0:
        print(f'⚠️ world_state 落后 {diff} 章（state@ch{ws_chapter}, 最新@ch{last_chapter}）')
    else:
        print(f'✅ world_state 已更新到 ch{ws_chapter}')
    print(f"经济: {ws.get('economy', {}).get('level', 'N/A')}")
    print(f"势力: {[f['name'] for f in ws.get('factions', [])]}")
else:
    print('⚠️ world_state 未初始化')

# =====================================================
# 5. V3 新增审计：foreshadow_queue 完整性
# =====================================================
print('\n=== Foreshadow Queue 审计 ===')
foreshadows = list(db['foreshadow_queue'].find({'project_id': pid}).sort('setup_chapter', 1))
last_ch = all_chapters[-1]['chapter'] if all_chapters else 0

fulfilled = [f for f in foreshadows if f.get('status') == 'fulfilled']
pending = [f for f in foreshadows if f.get('status') != 'fulfilled']

print(f"总伏笔数: {len(foreshadows)}, 已回收: {len(fulfilled)}, 待处理: {len(pending)}")

for f in foreshadows:
    ftype = f.get('foreshadow_type', '?')
    status = f.get('status', 'planned')
    setup = f.get('setup_chapter', 0)
    due = f.get('expected_callback_chapter', 0)
    deadline = f.get('deadline_type', 'soft')
    pending_ch = last_ch - setup

    if status == 'fulfilled':
        marker = '✅ 已回收'
    elif due > 0 and last_ch > due:
        marker = f'🔴 逾期 {last_ch - due} 章 ({deadline})'
    elif pending_ch > 80:
        marker = '🟡 等待太久了'
    else:
        marker = '🟢 正常'

    print(f"  {marker} ch{setup} → ch{due if due else '?'}: [{ftype}] {f.get('description','')[:60]}")

# =====================================================
# 6. 时间线密度
# =====================================================
print('\n=== 时间线密度审计 ===')
all_chapters_db = list(db['chapter_memory'].find(
    {'project_id': pid},
    {'chapter': 1}
).sort('chapter', 1))
total_chs = len(all_chapters_db)

timeline_entries = list(db['timeline'].find({'project_id': pid}))
events_per_ch = defaultdict(int)
for entry in timeline_entries:
    events_per_ch[entry.get('chapter', 0)] += 1

min_events = min(events_per_ch.values()) if events_per_ch else 0
zero_events = set(range(1, total_chs+1)) - set(events_per_ch.keys())
print(f"总章数: {total_chs}, timeline 事件数: {len(timeline_entries)}")
print(f"每章最少事件: {min_events}, 零事件章节: {len(zero_events)}")
if zero_events:
    print(f"零事件章节: {sorted(zero_events)[:20]}{'...' if len(zero_events) > 20 else ''}")

# =====================================================
# 7. anti_fatigue 报告
# =====================================================
print('\n=== Anti-Fatigue 审计 ===')
fatigue = list(db['anti_fatigue'].find({'project_id': pid}).sort('createdAt', -1).limit(1))
if fatigue:
    f = fatigue[0]
    print(f"生成时间: {f.get('createdAt', '?')}")
    print(f"疲劳指数: {f.get('fatigue_level', 'N/A')}")
    alerts = f.get('alerts', [])
    if alerts:
        print(f"告警数: {len(alerts)}")
        for a in alerts[:5]:
            print(f"  ⚠️ {a.get('type', '?')}: {a.get('message', '')[:80]}")
    else:
        print('✅ 无告警')
else:
    print('anti_fatigue 未运行')

print('\n=== 审计完成 ===')
```

## V3 新增修复流程

### 修复 1: event_log 断层

如果 event_log 版本号不连续（有跳过）：

```python
# 重建 event_log 连续性：找出缺失版本号，尝试从其他 collection 补全
existing_versions = set(e['version'] for e in db['event_log'].find({'project_id': pid}, {'version': 1}))
all_versions = set(range(min(existing_versions), max(existing_versions) + 1))
missing = sorted(all_versions - existing_versions)
print(f"缺失版本: {missing}")
# 仅记录断层，不自动补全（防止编造历史）
```

**不自动补全 event_log 的缺失版本**——event sourcing 的核心原则是不可篡改历史。如果发现断层，记录并考虑从最近的 snapshot 重建。

### 修复 2: snapshot 过期

如果最新 snapshot 已经落后 >100 events：

```python
# 从最新 snapshot 重放事件
latest_snapshot = db['snapshot_store'].find_one(
    {'project_id': pid}, sort=[('version', -1)]
)
events_to_replay = list(db['event_log'].find({
    'project_id': pid,
    'version': {'$gt': latest_snapshot['version']}
}).sort('version', 1))
print(f"需重放 {len(events_to_replay)} 条事件")
# 生成新 snapshot
# 注：重放逻辑较为复杂，建议直接用 memory-manager 的生成函数
```

### 修复 3: world_state 与最新章节不一致

1. 读最后 3 章内容，提取世界状态变化
2. 与 world_state 对比
3. 如果矛盾：**以正文为准**，更新 world_state

⚠ 不要「脑补」world_state——只根据正文实际内容更新。

## V2 审计项目（保留）

### 角色别名对照表

| 角色 | 正文中可能的别名 | 摘要中缺少 |
|------|-----------------|-----------|
| 沈从越 | 沈从越、沈教授、从越 | 大概率缺 |
| 陆沉 | 陆沉、图书馆老人、馆长 | 正文未登场则缺 |
| 逐字人 | 逐字人、Word Eraser | 正文未登场则缺 |
| 赵铁 | 赵铁、铁哥 | 大概率缺前半段 |
| 老钱 | 老钱、钱叔 | 大概率缺前半段 |
| 秦征 | 秦征、城主 | 大概率缺前半段 |
| 方晴 | 方晴 | 大概率缺前半段 |

### 退场检测流程（V2 兼容）

1. 用字符名 + 别名扫描所有章节 content
2. 对每个角色，找到最后有戏份的章节（含对话引号或长动作描述的句子）
3. 区分"正文出场" vs "只是被回忆/旁白提及"
4. 在 timeline 中添加不超过正文信息的事件

### 伏笔紧急度分级（V2 兼容——V3 已由 foreshadow_queue 自动管理）

| 等待章数 | 紧急度 | 建议回收时机 |
|---------|--------|-------------|
| >80 章 | 🔴 紧急 | 最近 15 章内用闪回+新线索重提 |
| 50-80 章 | 🟡 中等 | 当前 ARC 前半段通过对话重提 |
| 30-50 章 | 🟢 正常 | 当前 ARC 中后段做转折助推器 |
| 10-30 章 | 🟢 近期 | 当前 ARC 后半段或下一 ARC |
| <10 章 | 🟢 最新 | 当前章或下一章 |

## 重要陷阱

- **event_log 不可手动编辑**：event sourcing 的核心原则是不可篡改。如果发现错误，写一条修正 event（`event_type: correction`），不要直接 DELETE/UPDATE。
- **snapshot 过期不可跳过**：snapshot 太旧时从它重放 events 会很慢。建议在 100 events 间隔自动触发。
- **world_state 更新必须以正文为依据**：审计员编造 world_state 会导致后续 ARC 的世界信息不准确。
- **不要直接修改 foreshadow_queue.status**：那是写作时由 foreshadow-manager 自然触发的。审计只做计划不做回收。
- **anti_fatigue 报高疲劳但小说类型为悬疑恐怖**：悬疑的持续紧张是类型特点，不一定是 bug。审计时要检查 projects.genre。
- **角色审计只补摘要不补正文**：摘要的字符限制（~200字）意味着只能追加角色名单。
- **首次出场标记 ★**：如"方晴★"让 ARC planner 知道这是该角色的正式登场。
- **编造退场事件是大忌**：如果正文只写到「赵铁在仓库整理物资」，就不能在 timeline 里写"赵铁离开烬城"。
