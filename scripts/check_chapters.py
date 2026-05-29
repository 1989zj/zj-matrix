#!/usr/bin/env python3
"""
章节自动检查器 — 修改章节后必须运行
检查项：
  1. 角色幽灵引用 — 名字出现在该角色正式登场之前，且上下文暗示已有交互
  2. 衔接断裂 — ChN结尾 → ChN+1开头逻辑不连贯
  3. 场景重复 — 连续章节中出现高度相似的描述段落
  4. 编辑器泄漏 — （本章完）以外的元注释、草稿摘要
"""
import sys, re, hashlib
sys.path.insert(0, '/root/novel_factory/scripts')
from memory_service import MemoryService

# ── 角色首次登场（物理出场，不含名字预言） ──
CHARACTER_INTRO = {
    '沈尘': 1,
    '顾长夜': 5,      # 物理出场在瀑布，Ch3石蟾蜍叫名字是伏笔，不算
    '石敢当': 9,
    '柳如烟': 9,
    '周元恺': 11,
    '赵元奎': 15,
    '秦霜': 15,
    '刀疤脸': 16,
    '八字胡': 16,
}

# 伏笔白名单：角色名字可以提前出现，但不暗示已有互动
FORESHADOW_OK = {
    '顾长夜': 3,  # Ch3石蟾蜍说名字，是伏笔
}

# 暗示已有交互的模式（出现这些=幽灵引用）
INTERACTION_PATTERNS = [
    r'{name}[的]?嘴里',        # X嘴里
    r'{name}[的]?口中',        # X口中
    r'{name}说过的?',          # X说过的
    r'{name}提过的?',          # X提过的
    r'{name}之前说',           # X之前说
    r'{name}讲过',             # X讲过
    r'{name}告诉过?',          # X告诉过
    r'{name}说那',             # X说那
    r'按{name}[的]?说法',     # 按X的说法
    r'照{name}[的]?话',       # 照X的话
    r'{name}教[过会]',         # X教过/会
    r'{name}嘱咐',             # X嘱咐
    r'记得{name}说',           # 记得X说
]

# ── 编辑器泄漏特征 ──
LEAK_PATTERNS = [
    r'说明[：:].*原文中',
    r'模糊表达已替换',
    r'确认[：:].*所有修改项',
    r'AI模板化',
    r'草稿摘要',
    r'（注[：:]',
    r'【注[：:]',
]


def load_chapters(mem, pid):
    """返回 {章节号: {title, content_cleaned, word_count}}"""
    chs = {}
    for n in range(1, 17):
        ch = mem.get_chapter(pid, n)
        c = ch.get('edited_content') or ch.get('content', '')
        # 去掉（本章完）
        c_clean = re.sub(r'（本章完）\s*$', '', c).strip()
        chs[n] = {
            'title': ch.get('title', ''),
            'content': c_clean,
            'word_count': len(re.findall(r'[\u4e00-\u9fff]', c_clean)),
        }
    return chs


def check_ghost_references(chapters):
    """检查 1：角色幽灵引用"""
    issues = []
    for ch_num in sorted(chapters.keys()):
        content = chapters[ch_num]['content']
        for name, intro_ch in CHARACTER_INTRO.items():
            if ch_num >= intro_ch:
                continue  # 已登场
            # 伏笔白名单
            if name in FORESHADOW_OK and ch_num >= FORESHADOW_OK[name]:
                continue
            if name not in content:
                continue
            # 该名字在本章出现，检查是否暗示已有交互
            for pat in INTERACTION_PATTERNS:
                p = pat.replace('{name}', re.escape(name))
                m = re.search(p, content)
                if m:
                    # 获取上下文
                    start = max(0, m.start() - 30)
                    end = min(len(content), m.end() + 30)
                    ctx = content[start:end].replace('\n', ' ')
                    issues.append(
                        f'幽灵引用: 第{ch_num}章出现「{name}」的交互引用, '
                        f'但{name}第{intro_ch}章才登场。上下文: ...{ctx}...'
                    )
                    break  # 只报告一次
    return issues


def check_transitions(chapters):
    """检查 2：衔接断裂"""
    issues = []
    ch_nums = sorted(chapters.keys())
    for i in range(len(ch_nums) - 1):
        ch_a = ch_nums[i]
        ch_b = ch_nums[i + 1]
        end_text = chapters[ch_a]['content']
        start_text = chapters[ch_b]['content']

        # 取结尾和开头的关键内容
        end_lines = [l for l in end_text.split('\n') if l.strip()]
        start_lines = [l for l in start_text.split('\n') if l.strip()]

        if not end_lines or not start_lines:
            continue

        end_last = end_lines[-1]
        start_first = start_lines[0]

        # 检测断裂信号：
        # 1. ChN结尾是动作/决定，ChN+1开头展示完全不同的时间/地点且无过渡
        # 这个需要语义判断，暂用启发式规则

        # 2. 检测时间倒流：如果两章都明确提了时间/天数
        day_a = re.findall(r'第([一二三四五六七八九十百千万\d]+)天', end_text)
        day_b = re.findall(r'第([一二三四五六七八九十百千万\d]+)天', start_text[:200])

        # 3. 检测地点突变（如果结尾在A地点，开头在B地点且无位移说明）
        # 简化：用结尾和开头各取30字做相似度，相似度过高的警告（可能场景重复）
        end_tail = end_text[-80:] if len(end_text) > 80 else end_text
        start_head = start_text[:80] if len(start_text) > 80 else start_text

        # 不在这里报衔接断裂（太容易误报），只在相似度异常时提示
        pass  # 衔接检查暂用场景重复检查替代

    return issues


def check_duplicate_scenes(chapters):
    """检查 3：连续章节场景重复"""
    issues = []
    ch_nums = sorted(chapters.keys())
    for i in range(len(ch_nums) - 1):
        ch_a = ch_nums[i]
        ch_b = ch_nums[i + 1]
        content_a = chapters[ch_a]['content']
        content_b = chapters[ch_b]['content']

        # 将每个章节切成段落，比较相邻两章的段落相似度
        paras_a = [p.strip() for p in content_a.split('\n\n') if len(p.strip()) > 30]
        paras_b = [p.strip() for p in content_b.split('\n\n') if len(p.strip()) > 30]

        # 取 ChN 结尾段 和 ChN+1 开头段 比较
        if paras_a and paras_b:
            tail_p = paras_a[-1]
            head_p = paras_b[0]
            # 简单相似度：共同子串长度
            common = _longest_common_substring(tail_p, head_p)
            if len(common) > 40:
                issues.append(
                    f'疑似场景重复: 第{ch_a}章结尾与第{ch_b}章开头有大段重复 '
                    f'({len(common)}字): "{common[:60]}..."'
                )

            # 额外：检查 ChN+1 前3段是否和 ChN 前3段相似（可能是完全重复的章节）
            if len(paras_a) >= 3 and len(paras_b) >= 3:
                common2 = _longest_common_substring(paras_a[-3], paras_b[0])
                if len(common2) > 60:
                    issues.append(
                        f'严重场景重复: 第{ch_a}章结尾段与第{ch_b}章开头段重复 '
                        f'({len(common2)}字): "{common2[:60]}..."'
                    )

    return issues


def check_editor_leaks(chapters):
    """检查 4：编辑器泄漏"""
    issues = []
    for ch_num in sorted(chapters.keys()):
        content = chapters[ch_num]['content']
        for pat in LEAK_PATTERNS:
            for m in re.finditer(pat, content):
                start = max(0, m.start() - 20)
                end = min(len(content), m.end() + 30)
                ctx = content[start:end].replace('\n', ' ')
                issues.append(
                    f'编辑器泄漏: 第{ch_num}章包含编辑元注释: ...{ctx}...'
                )
    return issues


def _longest_common_substring(s1, s2):
    """返回最长公共子串"""
    m, n = len(s1), len(s2)
    if m == 0 or n == 0:
        return ''
    # 简化版，只处理较短文本
    max_len = min(m, n, 200)
    best = ''
    for i in range(0, m, 10):
        for j in range(0, n, 10):
            k = 0
            while i + k < m and j + k < n and s1[i + k] == s2[j + k] and k < max_len:
                k += 1
            if k > len(best):
                best = s1[i:i + k]
    return best


def main():
    pid = '966a03c8'
    mem = MemoryService()
    # 参数：指定章节范围，默认全部
    if len(sys.argv) >= 3:
        start, end = int(sys.argv[1]), int(sys.argv[2])
    else:
        start, end = 1, 16

    chapters = {}
    for n in range(start, end + 1):
        ch = mem.get_chapter(pid, n)
        if not ch:
            continue
        c = ch.get('edited_content') or ch.get('content', '')
        c_clean = re.sub(r'（本章完）\s*$', '', c).strip()
        chapters[n] = {
            'title': ch.get('title', ''),
            'content': c_clean,
            'word_count': len(re.findall(r'[\u4e00-\u9fff]', c_clean)),
        }

    all_issues = []
    all_issues.extend(check_ghost_references(chapters))
    all_issues.extend(check_duplicate_scenes(chapters))
    all_issues.extend(check_editor_leaks(chapters))
    # 衔接检查暂时跳过（需要语义模型）

    print(f'检查范围: 第{start}-{end}章 ({len(chapters)}章)')
    wc_all = sum(ch['word_count'] for ch in chapters.values())
    print(f'总字数: {wc_all}')
    print()

    if not all_issues:
        print('✓ 全部通过，未发现问题')
        return 0

    print(f'发现 {len(all_issues)} 个问题:\n')
    for i, issue in enumerate(all_issues, 1):
        print(f'[{i}] {issue}\n')

    return len(all_issues)


if __name__ == '__main__':
    sys.exit(min(main(), 255))
