#!/usr/bin/env python3
"""修复九域证道第3-5章节奏问题：拆分第3章 + 修衔接 + 清理泄漏 + 重编号"""
import sys, re
sys.path.insert(0, '/root/novel_factory/scripts')
from memory_service import MemoryService

mem = MemoryService()
pid = '966a03c8'

def count_chinese(text):
    return len(re.findall(r'[\u4e00-\u9fff]', text))

def get_chapter(num):
    ch = mem.get_chapter(pid, num)
    return ch.get('edited_content') or ch.get('content', '') if ch else ''

# ========== 1. 拉取原始内容 ==========
c3_full = get_chapter(3)
c4_full = get_chapter(4)  
c5_full = get_chapter(5)

paras3 = c3_full.split('\n\n')

# 找断点: P70 "但那条缝的尽头，他看见了苍云镇的城墙。" 
# 这是天然分章点 - 黎明/城墙/视野窄缩，完美的章尾钩子
split_idx = None
for i, p in enumerate(paras3):
    if '苍云镇的城墙' in p and i > 60:
        split_idx = i
        break

if split_idx is None:
    print("ERROR: 找不到分章断点")
    sys.exit(1)

# 第3章第一部分: P1 到 split_idx（包含苍云镇城墙那一段）
c3_part1 = '\n\n'.join(paras3[:split_idx+1])
# 第3章第二部分: split_idx+1 到结尾
c3_part2 = '\n\n'.join(paras3[split_idx+1:])

print(f"拆点: P{split_idx+1}")
print(f"Part1: {count_chinese(c3_part1)}字")
print(f"Part2: {count_chinese(c3_part2)}字")

# ========== 2. 重写新第3章结尾（添加强钩子）==========
# 原结尾: "但那条缝的尽头，他看见了苍云镇的城墙。" → 太弱，加钩子
old_end = '但那条缝的尽头，他看见了苍云镇的城墙。'
new_c3_ending = '''但那条缝的尽头，他看见了苍云镇的城墙。

城墙脚下的尘土被晨风卷起来，在灰白色的天光里像一锅煮沸的粥。城门紧闭。不是宵禁的那种紧闭——门缝里塞着灵符，朱砂写的敕令在晨风里一闪一闪。城墙上站了比平时多三倍的守军，弩箭上弦，箭尖全都指向城外的驿道。

护矿卫的马蹄声在他身后越来越近。前面的城门进不去。左边的槐树林已经到了尽头——再往前就是没有遮蔽的驿道开阔带。

沈尘按住了腰间的石蟾蜍。石碑第八道裂痕在丹田里又张开了半寸，暗金色的光顺着他按住石蟾蜍的手指渗进了石皮。石蟾蜍的嘴无声地张合了一下。

他没看清它说了什么。但他看清了石碑给他看的东西——城墙底下，贴着护城河的石基，有一道很细的界壁裂缝。和在矿道里发现的那条一样，通往九域之间被遗忘的夹缝。

护城河的水是黑的。他吸了一口气，纵身跳了进去。

（本章完）'''

# 替换旧结尾
idx = c3_part1.rfind(old_end)
if idx == -1:
    # 尝试模糊匹配
    import difflib
    print("WARNING: 精确匹配失败，用模糊替换")
    # 直接替换最后两句
    c3_part1_lines = c3_part1.strip().split('\n')
    # 找包含"苍云镇的城墙"的段落
    for i, line in enumerate(c3_part1_lines):
        if '苍云镇的城墙' in line:
            c3_part1 = '\n'.join(c3_part1_lines[:i]) + '\n\n' + new_c3_ending
            break
else:
    c3_part1 = c3_part1[:idx] + new_c3_ending

# ========== 3. 重写新第4章开头和结尾 ==========
# 从护城河/界壁缝隙过渡到密林
new_c4_opening = '''护城河的水比他想的更深。沈尘一口气沉到了底，手指在石基上摸到了一道半掌宽的裂缝——不是砖缝，是空间本身被撕开的口子。冰凉的水灌进裂缝时发出了铁板被撕裂的声音。

他钻了进去。

界壁的夹缝不长。他在黑暗中爬了大约半炷香的时间，手掌磨在粗糙的空间壁上，掌心被割出了好几道口子。等他再爬出来的时候，阳光已经升到了正头顶。

不是苍云镇的阳光。是苍云山脉深处的阳光。界壁裂缝把他甩到了镇西二十里外的一条干涸溪沟里。城墙、护矿卫、紧闭的城门，全都不见了。

'''

# Part2 开头是 "第二天的傍晚，沈尘绕开了苍云镇，继续往西。"
# 这段现在需要衔接：他已经到镇西二十里外了，直接接密林
# 删除原来的 "第二天的傍晚……" 过渡段，替换上下文
c3_part2_paras = c3_part2.split('\n\n')
# P71 (原 index 0 in part2): "第二天的傍晚，沈尘绕开了苍云镇，继续往西。"
# P72: 苍云镇骚乱描述
# P73: "沈尘在人群的边缘站了一会……"
# 保留P72-P73的苍云镇骚乱作为他远远看到的景象，然后进密林

# 找并替换开头
c3_part2_fixed = new_c4_opening
found_start = False
for p in c3_part2_paras:
    if not found_start:
        if '绕开了苍云镇' in p or '第二天' in p and '苍云镇' in p:
            found_start = True
            continue
        else:
            continue
    c3_part2_fixed += p.strip() + '\n\n'

# 改写结尾钩子
old_c4_end = '血迹在第四天的傍晚断了。'
new_c4_ending = '''血迹在第四天的傍晚断了。

不是消失了。是进了水——他听见了瀑布的声音。那是一种从高处砸进深潭的沉闷轰鸣，隔着半座山都能感觉到地面的震动。

沈尘循着水声摸过去。穿过一片挂满枯苔的崖壁缝隙后，一条三丈高的白练挂在面前。水雾扑面，潭水泛着青黑。

潭边有一块被冲刷光滑的青色巨石。石上坐着一个人。

（本章完）'''

idx2 = c3_part2_fixed.rfind(old_c4_end)
if idx2 != -1:
    c3_part2_fixed = c3_part2_fixed[:idx2] + new_c4_ending
else:
    print("WARNING: 找不到原第4章结尾，在末尾追加钩子")
    # 移除最后的（本章完）然后加新结尾
    c3_part2_fixed = re.sub(r'（本章完）\s*$', '', c3_part2_fixed.strip())
    c3_part2_fixed += '\n\n' + new_c4_ending

# ========== 4. 修复新第5章（原第4章）==========
# 问题1: 开头是"矿洞的烟尘还在肺里"→ 改成从瀑布场景衔接
# 问题2: 结尾有editor元注释 → 切除

# 修复开头
old_c5_opening = '苍云山脉的密林在子夜时分是不透光的。\n\n沈尘跑了整整两天。矿洞的烟尘还在肺里，每一次吸气管壁都像糊着一层炭渣。他是在第三天午后才停下来的——不是因为觉得追兵远了，是因为左腿终于撑不住了。'
new_c5_opening = '''沈尘没有立刻现身。

他蹲在崖壁缝隙的阴影里，盯着潭边青石上那个盘腿而坐的少年。灰色短衫，袖口扎紧，脚边放着一把没有鞘的铁剑。头发用草绳束在脑后，额前碎发被水雾打得湿漉漉的。

少年闭着眼，像一尊被瀑布冲刷了多年的石像。

沈尘的手摸上了腰间那把从矿监身上捡的短刀。他蹲了半炷香的时间。少年一动不动。瀑布的水声掩盖了他因为左腿抽痛而不小心碾碎的一截枯枝。

然后少年开口了。'''

# 保留从"摔倒的时候脸砸进腐叶层"开始的余下内容
c4_paras = c4_full.split('\n\n')
# 找到"摔倒的时候脸砸进腐叶层"的位置
fall_idx = None
for i, p in enumerate(c4_paras):
    if '脸砸进腐叶层' in p:
        fall_idx = i
        break

if fall_idx:
    # 从摔倒段落开始保留（保留顾长夜出场前的环境描写）
    c4_body = '\n\n'.join(c4_paras[fall_idx:])
    # 但需要改一下开头——去掉"摔倒的时候"
    c4_body = '他从昨天傍晚到现在没吃过东西，左腿每走一步都在打颤。' + c4_body[c4_body.find('摔倒的时候'):] if '摔倒的时候' in c4_body else c4_body
    
    c5_fixed = new_c5_opening + '\n\n' + c4_body
else:
    # 回退: 保留原开头但修改前两句
    c5_fixed = c4_full.replace(old_c5_opening, new_c5_opening.replace('\n\n', '\n'))
    if c5_fixed == c4_full:
        print("WARNING: 无法替换Ch5开头，保持原样")

# 切除editor元注释
# 匹配 "---\n\n说明：" 或 "修改说明" 等
c5_fixed = re.sub(r'\n---\n\n说明：.*$', '', c5_fixed, flags=re.DOTALL)
c5_fixed = re.sub(r'\n---\n说明：.*$', '', c5_fixed, flags=re.DOTALL)
# 也切除单独的"说明："段
c5_fixed = re.sub(r'\n\n说明：.+$', '', c5_fixed, flags=re.DOTALL)
# 确保有（本章完）
if '（本章完）' not in c5_fixed[-50:]:
    c5_fixed = c5_fixed.rstrip() + '\n\n（本章完）'

# ========== 5. 修复新第6章（原第5章）==========
# 问题: 末尾有摘要泄漏 + 与Ch5情绪不连贯

# 切除末尾泄漏
c6_fixed = c5_full
# 删除 "---\n\n天火域供奉追兵..." 这段摘要
c6_fixed = re.sub(r'\n---\n\n天火域供奉追兵.+$', '', c6_fixed, flags=re.DOTALL)
# 也删除末尾独立的摘要段
c6_fixed = re.sub(r'\n\n天火域供奉追兵.+?（第五章完）', '\n\n（本章完）', c6_fixed, flags=re.DOTALL)
# 确保有（本章完）
if '（本章完）' not in c6_fixed[-30:]:
    c6_fixed = c6_fixed.rstrip() + '\n\n（本章完）'

# 修复与Ch5的情绪连贯：Ch5结尾是沈尘发现石蟾蜍喊的是顾长夜，产生怀疑
# Ch6开头两人正常赶路 —— 加一两句过渡
old_c6_start = "峡谷入口处立着一块风化的石碑，上面刻着三个字——鹰愁涧。\n\n沈尘在溪边蹲下，捧水洗脸。"
if old_c6_start in c6_fixed:
    transition = "峡谷入口处立着一块风化的石碑，上面刻着三个字——鹰愁涧。\n\n天还没亮他们就离开了矿坑。顾长夜走在前面带路，沈尘跟在后面三步远，一路上谁也没说话。石蟾蜍在矿坑里喊出的那个名字还堵在他嗓子眼里——但他没有问。在这片连矿场东家都不敢进的深山老林里，比起一个来历不明的名字，更紧迫的是身后越来越近的追兵。\n\n沈尘在溪边蹲下，捧水洗脸。"
    c6_fixed = c6_fixed.replace(old_c6_start, transition, 1)

print(f"\n=== 字数统计 ===")
print(f"新第3章: {count_chinese(c3_part1)}字")
print(f"新第4章: {count_chinese(c3_part2_fixed)}字")
print(f"新第5章: {count_chinese(c5_fixed)}字")
print(f"新第6章: {count_chinese(c6_fixed)}字")

# ========== 6. 写回 MongoDB ==========
# 策略: 先删旧的第3-15章，再写入新的第3-6章 + 重编号7-16

db = mem.db
chapters_col = db['chapters']

# 6a. 备份旧数据（只做内存备份，不写文件）
old_chapters = {}
for n in range(3, 16):
    ch = chapters_col.find_one({'project_id': pid, 'chapter': n})
    if ch:
        old_chapters[n] = ch

# 6b. 删除第3-15章
chapters_col.delete_many({'project_id': pid, 'chapter': {'$gte': 3, '$lte': 15}})

# 6c. 写入新第3章
title3 = '驿道残阳石蟾初语'
chapters_col.insert_one({
    'project_id': pid,
    'chapter': 3,
    'title': title3,
    'content': c3_part1.strip(),
    'edited_content': c3_part1.strip(),
    'word_count': count_chinese(c3_part1),
})

# 6d. 写入新第4章
title4 = '界壁遁形密林窥踪'
chapters_col.insert_one({
    'project_id': pid,
    'chapter': 4,
    'title': title4,
    'content': c3_part2_fixed.strip(),
    'edited_content': c3_part2_fixed.strip(),
    'word_count': count_chinese(c3_part2_fixed),
})

# 6e. 写入新第5章
title5 = '瀑布青石暗河同行'  # 保留原意
chapters_col.insert_one({
    'project_id': pid,
    'chapter': 5,
    'title': title5,
    'content': c5_fixed.strip(),
    'edited_content': c5_fixed.strip(),
    'word_count': count_chinese(c5_fixed),
})

# 6f. 写入新第6章
title6 = '鹰愁涧畔水镜窥踪'  # 保留原标题
chapters_col.insert_one({
    'project_id': pid,
    'chapter': 6,
    'title': title6,
    'content': c6_fixed.strip(),
    'edited_content': c6_fixed.strip(),
    'word_count': count_chinese(c6_fixed),
})

# 6g. 重编号: 原7-15 → 新7-15（不需要移动，原6就是新7）
# 原第6章不变，保持为第7章
# 原第7章 → 第8章
for old_num in range(6, 16):
    if old_num in old_chapters:
        new_num = old_num + 1
        old = old_chapters[old_num]
        chapters_col.insert_one({
            'project_id': pid,
            'chapter': new_num,
            'title': old.get('title', ''),
            'content': old.get('content', ''),
            'edited_content': old.get('edited_content', old.get('content', '')),
            'word_count': old.get('word_count', 0),
        })
        print(f"  重编号: 原第{old_num}章 → 第{new_num}章")

# 更新project进度
db['projects'].update_one(
    {'project_id': pid},
    {'$set': {'current_chapter': 16}}
)

print("\n✓ 全部完成！")
print(f"  新第3章: {title3}")
print(f"  新第4章: {title4}")
print(f"  新第5章: {title5}")
print(f"  新第6章: {title6}")
print(f"  第7-16章: 从原第6-15章重编号")
