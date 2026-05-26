#!/usr/bin/env python3
"""
起点小说 · 反重复/反模板化检测
纯 Python，零依赖，规则+统计驱动。
在 draft-writer 生成后、editor 审校前运行。
"""
import re
import json
from collections import Counter
from typing import List, Dict, Tuple

# ============================================================
# AI 高频模板化用语库
# ============================================================
AI_CLICHES = [
    # 面部微表情
    "眼中闪过", "嘴角浮现", "嘴角抽搐", "瞳孔收缩", "瞳孔放大",
    "眉头一皱", "眉头紧锁", "眉头舒展", "面色一沉", "面色一变",
    "眼神一凝", "眼神一亮", "眼神闪烁", "目光一凝", "目光闪烁",

    # 身体反应
    "心中一动", "心中一惊", "心中一凛", "心中一沉", "心中大定",
    "深吸一口气", "倒吸一口凉气", "倒吸一口冷气",
    "拳头紧握", "双拳紧握", "攥紧拳头",
    "后背发凉", "脊背发凉", "头皮发麻",
    "心头一颤", "心头一震",

    # 过渡/感叹
    "不得不说", "不可否认", "显而易见", "毫无疑问",
    "说来也怪", "说来话长", "果不其然", "不出所料",
    "令人惊讶的是", "更让人惊讶的是",

    # 动作描写的万能动词
    "缓缓开口", "淡淡一笑", "微微一笑", "冷笑一声",
    "轻描淡写地说", "不置可否", "若有所思",

    # 战斗描写
    "化作一道流光", "化作一道残影", "化作一道黑影",
    "电光火石之间", "转瞬之间", "眨眼之间",
    "一股强大的气势", "一股恐怖的气息", "一股威压",
]

# 句子结构重复检测参数
SLIDING_WINDOW = 3          # 连续 N 句检查
STRUCTURE_SIM_THRESH = 0.7  # 句子结构相似度阈值（0-1）

# 章节间重复检测参数
NGRAM_N = 8                 # 字符 n-gram 长度
INTER_CHAPTER_SIM_THRESH = 0.3  # 章节间相似度阈值


# ============================================================
# 工具函数
# ============================================================

def _split_sentences(text: str) -> List[str]:
    """按中文标点分句"""
    return [s.strip() for s in re.split(r'[。！？；\n]', text) if len(s.strip()) >= 5]


def _sentence_structure(s: str) -> str:
    """提取句子结构（保留标点位置，替换实词为占位符）"""
    # 替换中文实词为 X，保留虚词和标点
    s = re.sub(r'[\u4e00-\u9fff]+', 'X', s)
    # 进一步压缩连续的 X
    s = re.sub(r'X{2,}', 'XX', s)
    return s


def _structure_similarity(s1: str, s2: str) -> float:
    """两个句子结构的 Jaccard 相似度"""
    if not s1 or not s2:
        return 0.0
    # 按字符切分
    chars1, chars2 = set(s1), set(s2)
    if not chars1 or not chars2:
        return 0.0
    intersection = len(chars1 & chars2)
    union = len(chars1 | chars2)
    return intersection / union if union > 0 else 0.0


def _char_ngrams(text: str, n: int = NGRAM_N) -> List[str]:
    """提取字符 n-gram"""
    clean = re.sub(r'\s+', '', text)
    return [clean[i:i+n] for i in range(len(clean) - n + 1)]


def _ngram_overlap(text1: str, text2: str, n: int = NGRAM_N) -> float:
    """两个文本的字符 n-gram 重叠率"""
    ng1 = set(_char_ngrams(text1, n))
    ng2 = set(_char_ngrams(text2, n))
    if not ng1 or not ng2:
        return 0.0
    return len(ng1 & ng2) / min(len(ng1), len(ng2))


# ============================================================
# 检测函数
# ============================================================

def detect_ai_cliches(text: str) -> List[Dict]:
    """检测 AI 模板化用语"""
    results = []
    for phrase in AI_CLICHES:
        count = text.count(phrase)
        if count > 0:
            # 找第一个出现位置取上下文
            idx = text.find(phrase)
            start = max(0, idx - 15)
            end = min(len(text), idx + len(phrase) + 15)
            context = text[start:end].replace('\n', ' ')
            results.append({
                "phrase": phrase,
                "count": count,
                "context": f"...{context}...",
            })
    return results


def detect_sentence_repetition(text: str) -> List[Dict]:
    """滑动窗口检测连续句子的结构重复"""
    sentences = _split_sentences(text)
    if len(sentences) < SLIDING_WINDOW:
        return []

    results = []
    for i in range(len(sentences) - SLIDING_WINDOW + 1):
        window = sentences[i:i + SLIDING_WINDOW]
        structures = [_sentence_structure(s) for s in window]

        # 检查窗口内任意两句的结构相似度
        for a in range(len(structures)):
            for b in range(a + 1, len(structures)):
                sim = _structure_similarity(structures[a], structures[b])
                if sim >= STRUCTURE_SIM_THRESH:
                    results.append({
                        "position": f"第 {i+1}-{i+SLIDING_WINDOW} 句",
                        "similarity": round(sim, 3),
                        "sentences": window,
                        "structures": structures,
                    })
                    break  # 同一个窗口只报一次
            else:
                continue
            break

    return results


def detect_inter_chapter_repetition(current: str, previous: List[str]) -> List[Dict]:
    """检测与前面章节的相似度"""
    results = []
    for i, prev_text in enumerate(previous):
        sim = _ngram_overlap(current, prev_text)
        if sim >= INTER_CHAPTER_SIM_THRESH:
            results.append({
                "chapter_ahead": i + 1,
                "similarity": round(sim, 3),
            })
    return results


# ============================================================
# 主入口
# ============================================================

def run_anti_rep(
    content: str,
    previous_chapters: List[str] = None,
) -> Dict:
    """
    执行反重复检测。

    参数:
        content: 当前章节正文
        previous_chapters: 前文章节正文列表（最近 N 章）

    返回:
        {
            "pass": bool,
            "score": float,       # 0-100，越高越好
            "cliche_count": int,
            "cliche_details": [...],
            "sentence_rep_count": int,
            "sentence_rep_details": [...],
            "inter_chapter_repetition": [...],
            "advice": str,
        }
    """
    if previous_chapters is None:
        previous_chapters = []

    # 1. AI 模板化检测
    cliches = detect_ai_cliches(content)

    # 2. 句内结构重复
    sentence_reps = detect_sentence_repetition(content)

    # 3. 章节间重复
    inter_reps = detect_inter_chapter_repetition(content, previous_chapters)

    # 计算评分
    total_cliche_count = sum(c["count"] for c in cliches)
    cliche_penalty = min(total_cliche_count * 3, 40)
    sentence_penalty = min(len(sentence_reps) * 10, 30)
    inter_penalty = min(len(inter_reps) * 15, 30)

    score = max(0, 100 - cliche_penalty - sentence_penalty - inter_penalty)
    passed = score >= 50

    # 建议
    advice_parts = []
    if total_cliche_count > 3:
        advice_parts.append(f"模板化用语 {total_cliche_count} 处，建议替换为具体描写")
    if sentence_reps:
        advice_parts.append(f"连续句结构重复 {len(sentence_reps)} 处，建议变换句式")
    if inter_reps:
        advice_parts.append(f"与前文章节相似度过高（{len(inter_reps)} 章），检查是否情节重复")

    return {
        "pass": passed,
        "score": round(score, 1),
        "cliche_count": total_cliche_count,
        "cliche_details": cliches,
        "sentence_rep_count": len(sentence_reps),
        "sentence_rep_details": sentence_reps,
        "inter_chapter_repetition": inter_reps,
        "advice": "；".join(advice_parts) if advice_parts else "无重大问题",
    }


# ============================================================
# CLI 测试
# ============================================================
if __name__ == "__main__":
    test_text = """
    林渡眼中闪过一道精光，嘴角浮现一丝笑意。他深吸一口气，缓缓开口：
    "来得正好。"
    对方瞳孔收缩，显然没料到他如此从容。林渡心中一动，知道自己赌对了。
    不得不说，这一次的冒险确实值得。他缓缓开口，仿佛一切尽在掌控。
    """

    result = run_anti_rep(test_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
