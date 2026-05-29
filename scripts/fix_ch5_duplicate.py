#!/usr/bin/env python3
"""修复第5章：切除重复的观察场景，保留原文+改衔接句"""
import sys, re
sys.path.insert(0, '/root/novel_factory/scripts')
from memory_service import MemoryService

mem = MemoryService()
pid = '966a03c8'

ch = mem.get_chapter(pid, 5)
c = ch.get('edited_content') or ch.get('content', '')
paras = c.split('\n\n')

# 问题：P1-P5 是我加的观察场景，P6-P13 是原文的到达场景，两者重复
# 解决：删 P1-P5，只改 P6 开头做衔接
# 
# P6 原文: "他从昨天傍晚到现在没吃过东西，左腿每走一步都在打颤。摔倒的时候脸砸进腐叶层..."
# 改成: "沈尘从崖壁缝隙的阴影里走出来。他从昨天傍晚到现在没吃过东西..."

old_p6 = '他从昨天傍晚到现在没吃过东西，左腿每走一步都在打颤。摔倒的时候脸砸进腐叶层'
new_p6 = '沈尘从崖壁缝隙的阴影里走出来。他从昨天傍晚到现在没吃过东西，左腿每走一步都在打颤。摔倒的时候脸砸进腐叶层'

c_fixed = new_p6 + c[c.index(old_p6) + len(old_p6):]

# 去掉可能残留的分隔线前面多余空行
c_fixed = re.sub(r'\n{4,}---', '\n\n---', c_fixed)

wc = len(re.findall(r'[\u4e00-\u9fff]', c_fixed))
print(f'修复后第5章: {wc}字')

# 验证：检查是否还有重复场景
if '沈尘没有立刻现身' in c_fixed:
    print('⚠ 仍有旧观察场景残留!')
elif '沈尘从崖壁缝隙的阴影里走出来' in c_fixed:
    print('✓ 衔接句已就位')
else:
    print('❌ 衔接句未找到')

# 检查对话是否完整
for keyword in ['这块石头是我的', '顾长夜', '暗河的尽头', '石蟾蜍喊的是顾长夜']:
    if keyword in c_fixed:
        print(f'✓ 保留: {keyword}')
    else:
        print(f'❌ 缺失: {keyword}')

# 写回
mem.db['chapters'].update_one(
    {'project_id': pid, 'chapter': 5},
    {'$set': {
        'content': c_fixed.strip(),
        'edited_content': c_fixed.strip(),
        'word_count': wc
    }}
)
print('✓ 已写回MongoDB')
