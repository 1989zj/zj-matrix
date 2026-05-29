#!/usr/bin/env python3
"""彻底修复第5章：切除所有重复到达场景，直接从瀑布对峙开始"""
import sys, re
sys.path.insert(0, '/root/novel_factory/scripts')
from memory_service import MemoryService

mem = MemoryService()
pid = '966a03c8'

ch = mem.get_chapter(pid, 5)
c = ch.get('edited_content') or ch.get('content', '')
paras = c.split('\n\n')

# 找到 '"这块石头是我的。"' 的位置
for i, p in enumerate(paras):
    if '这块石头是我的' in p:
        start_idx = i
        break

# 第7段是顾长夜的外貌描写，需要保留
# P6: "他喝了三捧水，然后看见了那双脚。" 
# P7: "潭边有一块被冲刷光滑的青色巨石，一个少年盘腿坐在石上。灰色短衫..."
# P8: "少年没睁眼。"
# P9: '"这块石头是我的。"'

# 保留P7(外貌) + P8-onwards, 但P8与我们要加的\"潭边的少年没有睁眼\"重复
# 所以取P7 + 从P9开始的全部

# 从 P6 "他喝了三捧水" 到 P8 "少年没睁眼" 都在描述到达+发现的过程
# P7是纯外貌，可以从 '"这块石头是我的。"' 之前的一段恢复

# 方案：开头衔接句 + P7外貌段 + P9开始的对话及后续
body = '\n\n'.join(paras[start_idx:])
physical_desc = paras[start_idx - 2]  # "潭边有一块被冲刷光滑的青色巨石..."

new_c5 = '潭边的少年没有睁眼。\n\n' + physical_desc + '\n\n' + body

# 清除多余空行
new_c5 = re.sub(r'\n{4,}', '\n\n\n', new_c5)

wc = len(re.findall(r'[\u4e00-\u9fff]', new_c5))
print(f'修复后第5章: {wc}字')

# 验证
checks = ['这块石头是我的', '顾长夜', '暗河的尽头', '石蟾蜍喊的是顾长夜',
          '潭边的少年没有睁眼', '灰色短衫', '（本章完）']
for s in checks:
    status = '✓' if s in new_c5 else '❌'
    print(f'{status} {s[:30]}')

# 检查是否有重复元素
if '沈尘没有立刻现身' in new_c5:
    print('❌ 旧观察场景残留!')
if '第四天傍晚' in new_c5:
    print('❌ 冗余到达描述残留!')
else:
    print('✓ 无重复场景')

mem.db['chapters'].update_one(
    {'project_id': pid, 'chapter': 5},
    {'$set': {'content': new_c5.strip(), 'edited_content': new_c5.strip(), 'word_count': wc}}
)
print('✓ 已写回MongoDB')
