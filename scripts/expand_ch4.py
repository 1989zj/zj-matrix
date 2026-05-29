#!/usr/bin/env python3
"""扩充第4章至2500+字，修复节奏空洞"""
import sys, re
sys.path.insert(0, '/root/novel_factory/scripts')
from memory_service import MemoryService

mem = MemoryService()
pid = '966a03c8'

def count_chinese(text):
    return len(re.findall(r'[\u4e00-\u9fff]', text))

# 当前第4章
ch4 = mem.get_chapter(pid, 4)
c4 = ch4.get('edited_content') or ch4.get('content', '')

# 分段落
paras = c4.split('\n\n')

# 定位关键插入点
new_paras = []
skip_next = False

for i, p in enumerate(paras):
    new_paras.append(p)
    
    # 插入点1: "城墙、护矿卫、紧闭的城门，全都不见了。" 之后
    # 加一段沈尘的身体状态和溪沟环境
    if '全都不见了' in p and not any('全都不见了' in pp for pp in paras[:i]):
        new_paras.append('''他在溪沟里躺了一会，让正午的太阳把湿透的麻衣晒到半干。左肩被弩箭擦过的地方结了痂，但痂的边缘发红——灵矿废液还在往皮肉里渗。他用指甲刮掉一层痂壳，挤出来的血是暗褐色的，带着一股铁锈般的腥气。''')
        
        new_paras.append('''不致命。但会拖慢愈合的速度。矿场的老矿奴说过，灵矿废液入血之后，伤口一个月内都不会完全结痂。他现在没有一个月的时间。''')
    
    # 插入点2: "他在凹洞里生了一小堆火。" 之后
    # 加饥饿和疲劳描写
    if '他在凹洞里生了一小堆火' in p:
        new_paras.append('''他从昨天下午到现在只喝过几口溪水。胃已经饿过了那股绞痛的劲儿，现在只剩下一层麻木的空洞感。他把手伸进麻衣夹层摸了一圈——除了石蟾蜍和那块晶石，什么都没有。''')
        
        new_paras.append('''凹洞的石壁上长着几丛灰白色的地衣。他在矿场里见过老矿奴吃这种东西——嚼起来像泡了水的锯末，但至少能让胃里有东西。他揪了一把塞进嘴里，嚼了半炷香的时间才咽下去。''')
    
    # 插入点3: "他失败了四十七次" → 具体化几次失败
    if '他失败了四十七次' in p:
        new_paras.append('''前面十次连灵气都聚不起来。他的经脉被异域灵气撑过之后，就像一根被拉变形的皮筋，回弹的速度比正常修士慢了十倍。灵气的流动断断续续——运到手腕时散了，运到指尖时又散了。''')
        
        new_paras.append('''第十一次到第二十次，他勉强把灵气推到了食指第二指节，然后整个人开始发抖——不是累的，是丹田里那道时间裂隙在反噬。异域灵气在他体内逗留得太久了，开始侵蚀经脉内壁。每一次催动灵气，都像用砂纸在血管里来回搓。''')
        
        new_paras.append('''第二十一次到第四十七次，他不数了。他只是反复地看晶石上的符文，反复地摹写。火光把他的影子投在凹洞的石壁上，弓着腰，像一只不知疲倦的虫子。''')
    
    # 插入点4: "沈尘盯着指尖上散去的光点，嘴角动了一下。" → 加他的心境
    if '沈尘盯着指尖上散去的光点，嘴角动了一下' in p:
        new_paras.append('''不是因为快成功了。是因为在光丝碎裂的那一瞬间，他的指尖感受到了一种从未有过的东西——不是灵力，不是异域灵气，是某种更底层的规则。就像一个人摸了一辈子的水，忽然在某一刻摸到了水分子的边缘。''')
        
        new_paras.append('''他知道了方向。剩下的只是时间和次数。''')
    
    # 插入点5: "后天凌晨" → 改时间感觉 + 加氛围，但保留石碑描写
    if '后天凌晨，他在凹洞里被石碑的震动惊醒' in p:
        # 删掉刚加的旧版本（含"后天凌晨"的段落）
        new_paras.pop()
        # 加入氛围段落 + 保留的石碑描写（去掉"后天凌晨"前缀）
        new_paras.append('''他不知道练了多久。火堆灭了又生，生了又灭。最后一次添柴的时候树枝还是湿的，烧出来的烟呛得他睁不开眼。他靠在石壁上闭了一会眼睛。''')
        new_paras.append('''再睁眼的时候，天还黑着。不是深夜那种黑——是黎明前最暗的那一段，连虫鸣都停了。''')
        # 保留原文的石碑描写，但去掉时间前缀
        remaining = p.replace('后天凌晨，', '', 1)
        new_paras.append(remaining)

# 组装
c4_expanded = '\n\n'.join(new_paras)

# 清理多余空行
c4_expanded = re.sub(r'\n{4,}', '\n\n\n', c4_expanded)

wc = count_chinese(c4_expanded)
print(f"扩充后第4章: {wc}字")

# 写回
db = mem.db
db['chapters'].update_one(
    {'project_id': pid, 'chapter': 4},
    {'$set': {
        'content': c4_expanded.strip(),
        'edited_content': c4_expanded.strip(),
        'word_count': wc
    }}
)
print("✓ 已写回MongoDB")
