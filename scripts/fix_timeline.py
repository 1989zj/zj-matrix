#!/usr/bin/env python3
"""修复九域证道时间线：重编号 + 填day字段 + 旧Ch3按新章节分发"""
import sys, json
sys.path.insert(0, '/root/novel_factory/scripts')
from memory_service import MemoryService

mem = MemoryService()
pid = '966a03c8'
tl = mem.db['timeline']

# ===== 1. 章节号映射 =====
# 旧 → 新
ch_map = {
    # Ch1,2 unchanged
    3: 3,   # 旧Ch3前半 → 新Ch3（默认，个别事件可能进Ch4）
    4: 5,   # 旧Ch4 → 新Ch5
    5: 6,   # 旧Ch5 → 新Ch6
    6: 7,   # 旧Ch6 → 新Ch7
    7: 8,
    8: 9,
    9: 10,
    10: 11,
    11: 12,
    12: 13,
    13: 14,
    15: 16,  # 旧15 → 新16
}

# ===== 2. 时间线：从章节内容推断 =====
# Ch1: Day 1 (矿场挖矿→石碑入体→幻象→觉醒→周浑巡查)
# Ch2: Day 1 夜 (窃听→逃跑→界壁裂缝→跨境突破→石蟾蜍)
# 新Ch3: Day 2 (北坡→驿道→石蟾蜍语→追兵→逃入槐树林→跳护城河)
# 新Ch4: Day 3-4 (界壁遁形→苍云镇骚乱→密林→练印诀→追踪血迹→瀑布)
# 新Ch5: Day 4-5 (瀑布遇顾长夜→暗河→矿坑休整→敛息术→夜谈)
# 新Ch6: Day 5-7 (鹰愁涧伏击→时间异能→供奉团→三天赶路→青云城前)
# 新Ch7: Day 7-8 (入城→灵纹城墙→青云塔→阶层观察)
# 之后: 每个章节约1-3天

day_map = {
    1: 1,
    2: 1,
    3: 2,
    4: 3,
    5: 4,
    6: 5,
    7: 7,
    8: 8,
    9: 10,
    10: 12,
    11: 14,
    12: 15,
    13: 17,
    14: 19,
    15: 21,
    16: 22,
}

# ===== 3. 旧第3章事件 → 新第3/4章分发 =====
# 基于事件内容判断属于新第3章（驿道篇）还是新第4章（密林篇）
old_ch3_to_new = {
    '周浑识破沈尘异常': 3,       # 驿道对峙
    '沈尘击杀周浑': 3,           # 驿道战斗
    '石蟾蜍口吐「顾长夜」': 3,   # 石蟾蜍在途中说话
    '沈尘焚尸逃离矿山': 4,       # 烧了矿监尸体后往西 → 属于密林篇过渡
    '沈尘踏上北荒之路': 4,       # 确立北荒目标 → 属于密林篇
}

# ===== 4. 执行更新 =====
count_renamed = 0
count_day = 0
count_split = 0

for doc in tl.find({'project_id': pid}):
    old_ch = doc.get('chapter', 0)
    obj_id = doc['_id']
    updates = {}
    
    # 4a. 重编号
    new_ch = ch_map.get(old_ch, old_ch)
    
    # 4b. 旧第3章事件按内容分发到新3或新4
    if old_ch == 3:
        event = doc.get('event', '')
        for keyword, target_ch in old_ch3_to_new.items():
            if keyword in event:
                new_ch = target_ch
                count_split += 1
                break
    
    if new_ch != old_ch:
        updates['chapter'] = new_ch
        count_renamed += 1
    
    # 4c. 填day
    day = day_map.get(new_ch, new_ch * 2)  # 兜底：每章约2天
    if doc.get('day') != day:
        updates['day'] = day
        count_day += 1
    
    if updates:
        tl.update_one({'_id': obj_id}, {'$set': updates})

print(f'✓ 重编号: {count_renamed}条')
print(f'✓ 填day: {count_day}条')
print(f'✓ 旧第3章拆分: {count_split}条')

# ===== 5. 验证 =====
print('\n=== 新timeline分布 ===')
from collections import Counter
ch_dist = Counter()
day_dist = {}
for doc in tl.find({'project_id': pid}).sort('_id', 1):
    ch = doc.get('chapter', 0)
    day = doc.get('day', '?')
    ch_dist[ch] += 1
    if ch not in day_dist:
        day_dist[ch] = set()
    day_dist[ch].add(day)

for ch in sorted(ch_dist):
    days = sorted(day_dist.get(ch, set()))
    print(f'  第{ch}章: {ch_dist[ch]}条 | Day {days}')

total = tl.count_documents({'project_id': pid})
print(f'\n共{total}条')
