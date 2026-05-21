#!/usr/bin/env python3
"""
novel-judge.py — Novel Review Pipeline (评审系统)

独立于创作系统的评审分支。只负责判决，不参与创作。
评审人格、Prompt、评分体系完全独立。

用法:
  # 全维度评审
  python3 novel-judge.py review '诡异游戏' --chapters 1-136
  
  # 只评审前三章（黄金三章高规格）
  python3 novel-judge.py review '诡异游戏' --chapters 1-3 --golden
  
  # 只看某个维度
  python3 novel-judge.py review '诡异游戏' --dimension hook,pacing,ai_smell
  
  # 只看最终裁决（不输出详细评分）
  python3 novel-judge.py review '诡异游戏' --verdict-only
  
  # 生成重写Patch
  python3 novel-judge.py patch '诡异游戏' --chapter 2 --issue hook
  
  # 查看历史评审
  python3 novel-judge.py history '诡异游戏'
"""

import sys
import json
import re
import hashlib
import os
from datetime import datetime, timezone
from collections import defaultdict, Counter

# ─── MongoDB 连接 ─────────────────────────────────────────

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"

def get_db():
    import pymongo
    c = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    return c['novel_factory'], c['novel']

# ─── 辅助工具 ──────────────────────────────────────────────

_CHARACTER_ALIASES = {
    '林远': ['林远', '主角', '他'],
    '顾晚': ['顾晚', '顾晚姐'],
    '周文': ['周文'],
    '赵铁': ['赵铁', '铁哥'],
    '方晴': ['方晴', '方少'],
    '秦征': ['秦征'],
    '陆沉': ['陆沉'],
    '老钱': ['老钱'],
    '沈从越': ['沈从越'],
    '逐字人': ['逐字人', 'Word Eraser'],
    '江漓': ['江漓'],
}

_AI_SMELL_PATTERNS = {
    '空洞描写': [
        r'空气仿佛', r'仿佛凝固', r'仿佛被', r'似乎有',
        r'好像有', r'不由得', r'不知不觉', r'突然间',
        r'就在这时', r'这一刻', r'那一瞬间',
    ],
    '废话总结': [
        r'说实话', r'说白了', r'不得不说', r'老实说',
        r'换句话说', r'简单来说', r'总的来说',
    ],
    '机械情绪': [
        r'心中涌起', r'内心充满', r'心底涌出', r'一种说不出的',
        r'一种莫名的', r'有一种', r'感到一股',
    ],
    '重复句式': [
        r'他知道', r'他知道自己', r'他明白', r'他清楚',
    ],
    "AI过渡": [
        r'随着', r'伴随着', r'与此同时', r'另一方面',
    ],
}

# ─── LLM 评估引擎 ──────────────────────────────────────────

_LLM_CONFIG = {
    'api_url': 'https://api.deepseek.com/v1/chat/completions',
    'model': 'deepseek-v4-flash',
    'temperature': 0.2,
    'max_tokens': 2000,
}

def _get_api_key():
    """从 Hermes 配置读取 DeepSeek API key"""
    config_path = os.path.expanduser('~/.hermes/config.yaml')
    config = open(config_path).read()
    m = re.search(r'api_key:\s*(\S+)', config)
    return m.group(1).strip() if m else None

def _call_llm(prompt, system_msg=None):
    """调用 DeepSeek API，返回解析后的 JSON"""
    if system_msg is None:
        system_msg = "你是一个专业的中国网络小说编辑。严格、客观、公正地评审每一章。输出必须是合法的 JSON 对象。"
    
    import urllib.request as _urllib, json as _json, time as _time
    
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("在 ~/.hermes/config.yaml 中找不到 API key")
    
    data = _json.dumps({
        'model': _LLM_CONFIG['model'],
        'messages': [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': _LLM_CONFIG['temperature'],
        'max_tokens': _LLM_CONFIG['max_tokens'],
    }).encode()
    
    req = _urllib.Request(
        _LLM_CONFIG['api_url'], data=data,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    
    last_err = None
    for attempt in range(3):
        try:
            resp = _urllib.urlopen(req, timeout=60)
            result = _json.loads(resp.read())
            content = result['choices'][0]['message']['content']
            return _json.loads(content)
        except (_json.JSONDecodeError, KeyError) as e:
            last_err = f"JSON 解析失败: {e}\nRaw: {content[:500] if 'content' in dir() else 'N/A'}"
        except _urllib.URLError as e:
            last_err = f"API 错误: {e}"
        _time.sleep(2)
    
    raise ValueError(f"LLM 调用失败 (3次重试): {last_err}")

def _llm_evaluate(chapter_texts, rubric, system_extra=""):
    """
    通用 LLM 评审函数。
    
    chapter_texts: {ch_num: full_text}
    rubric: 评分标准描述字符串
    system_extra: 额外的 system message 指导
    
    返回: {ch_num: {score: N, issues: [...]}, overall: N}
    """
    chapters_json = json.dumps(chapter_texts, ensure_ascii=False, indent=2)
    
    prompt = f"""请对以下章节正文进行评审。

评分标准（0-10）：
{rubric}

请为每一章单独评分，输出格式如下：
{{
  "1": {{"score": <0-10>, "issues": ["问题1", "问题2"], "strengths": ["优点1"]}},
  "2": {{"score": <0-10>, "issues": [...], "strengths": [...]}},
  ...
  "overall": <各章平均分>,
  "overall_issues": ["整体性问题"]
}}

章节正文：
{chapters_json}
"""
    
    system = f"你是一个专业的中国网络小说编辑。{system_extra}严格评分，不要给虚高分数。6分=及格，7分=良好，8分=优秀，9分=顶级。输出必须是合法的 JSON 对象。"
    
    return _call_llm(prompt, system)

def load_chapter_content(novel_db, novel_name, chapter_num):
    """从 novel.chapters 或 novel_factory 加载章节内容"""
    nf, novel = get_db()
    
    # 优先从 novel.chapters 读取 - 尝试精确匹配
    ch = novel['chapters'].find_one({'novelName': novel_name, 'chapterNumber': chapter_num})
    if ch and ch.get('content'):
        return ch['content']
    
    # 尝试正则匹配（用户可能输入了简称）
    ch = novel['chapters'].find_one({'novelName': {'$regex': novel_name[:6]}, 'chapterNumber': chapter_num})
    if ch and ch.get('content'):
        return ch['content']
    
    # 从 novel_factory 查找正文
    # 通常正文在 novel 数据库的 chapters 集合，但诡异游戏可能在别处
    return None

def load_chapter_metadata(nf_db, pid, chapter_num):
    """从 chapter_memory 加载章节元数据"""
    return nf_db['chapter_memory'].find_one({'project_id': pid, 'chapter': chapter_num})

def get_project_id(nf_db, novel_name):
    """查找项目 ID"""
    for pid in nf_db['projects'].distinct('project_id', {'title': {'$regex': novel_name[:6]}}):
        return pid
    
    projects = list(nf_db['projects'].find({'title': {'$regex': novel_name[:6]}}))
    if projects:
        return projects[0]['project_id']
    
    # 实在找不到，全量扫描 chapter_memory
    cm = nf_db['chapter_memory'].find_one()
    if cm:
        return cm.get('project_id')
    return None

def safe_int(v, default=0):
    if isinstance(v, int):
        return v
    try:
        return int(v) if v else default
    except (ValueError, TypeError):
        return default

# ─── 维度评审函数 ──────────────────────────────────────────

def review_hook(chapters_meta, chapters_content, pid, novel_name):
    """Hook Review — LLM 版：评估每章开头的钩子强度"""
    if not chapters_content:
        print("    ⚠️ 无全文，回退到关键词评分")
        return _legacy_review_hook(chapters_meta, pid, novel_name)
    
    # 取每章前 800 字作为开头评估
    openings = {}
    for ch_num, text in chapters_content.items():
        openings[ch_num] = text[:800]
    
    rubric = """Hook（开头钩子）— 评估每章开场的吸引力：

• 0-3: 开场平淡无奇，无悬念/冲突/疑问，读者会立刻离开
• 4-6: 有一定信息量但缺乏让人「想知道接下来」的冲动
• 7-8: 有明显钩子——悬念、冲突、疑问、或强烈情绪代入
• 9-10: 开头让读者无法停止阅读，必须知道后面发生了什么

子维度：
- curiosity: 是否让读者产生「为什么」「怎么办」的疑问
- tension: 是否有紧张/冲突/危险感
- mystery: 是否有未解之谜
- emotional_pull: 是否让读者对角色产生情感投入
- pacing: 信息密度和节奏是否合适
- dopamine_density: 是否有爽点/满足感"""

    try:
        result = _llm_evaluate(openings, rubric, "重点检查前三章的开头钩子。")
    except ValueError as e:
        print(f"    ⚠️ LLM 评估失败 ({e})，回退到关键词评分")
        return _legacy_review_hook(chapters_meta, pid, novel_name)
    
    # 转换格式以兼容下游代码
    avg = result.get('overall', 0)
    detail = {}
    for ch_num in chapters_meta:
        ch = result.get(str(ch_num), {})
        detail[ch_num] = {
            'scores': ch,
            'average': ch.get('score', 5),
            'issues': ch.get('issues', []),
            'passed': ch.get('score', 5) >= 5.0,
        }
    
    issue_count = sum(len(v.get('issues', [])) for v in result.values() if isinstance(v, dict))
    
    return {
        'score': avg,
        'detail': detail,
        'passed': avg >= 5.0,
        'issue_count': issue_count,
        'method': 'llm',
    }

def _legacy_review_hook(chapters_meta, pid, novel_name):
    results = {}
    total_score = 0
    dims = 0
    
    dim_names = ['curiosity', 'tension', 'mystery', 'emotional_pull', 'pacing', 'dopamine_density']
    
    for ch_num in sorted(chapters_meta.keys()):
        meta = chapters_meta[ch_num]
        summary = (meta.get('summary') or meta.get('hook') or '')[:200]
        title = meta.get('title', f'第{ch_num}章')
        
        scores = {}
        issues = []
        
        # --- 机械化评分 (0-10) ---
        
        # 1. Curiosity — 是否有悬念/疑问
        q_words = ['为什么', '秘密', '真相', '是谁', '是什么', '？', '...', '难道', '究竟']
        q_count = sum(1 for w in q_words if w in summary)
        scores['curiosity'] = min(q_count * 2, 10)
        if scores['curiosity'] < 3 and ch_num <= 3:
            issues.append('开头缺乏疑问/悬念')
        
        # 2. Tension — 是否有冲突/危险
        t_words = ['危险', '追杀', '战斗', '杀', '死亡', '致命', '危机', '紧急', '陷阱', '冲突']
        t_count = sum(1 for w in t_words if w in summary)
        scores['tension'] = min(t_count * 2, 10)
        if scores['tension'] < 2 and ch_num <= 3:
            issues.append('缺乏紧张感')
        
        # 3. Mystery — 是否有未解之谜
        m_words = ['神秘', '未知', '奇怪', '诡异', '异样', '不可', '谜', '异常', '古怪']
        m_count = sum(1 for w in m_words if w in summary)
        scores['mystery'] = min(m_count * 2, 10)
        if scores['mystery'] < 2 and ch_num <= 3:
            issues.append('缺乏悬疑元素')
        
        # 4. Emotional Pull — 情感共鸣
        e_words = ['愤怒', '恐惧', '绝望', '希望', '感动', '背叛', '爱情', '友情', '信任', '牺牲']
        e_count = sum(1 for w in e_words if w in summary)
        scores['emotional_pull'] = min(e_count * 2, 10)
        if scores['emotional_pull'] < 2 and ch_num <= 3:
            issues.append('情感拉扯不足')
        
        # 5. Pacing — 节奏判断 (摘要字数密度)
        s_len = len(summary)
        if s_len > 100:
            scores['pacing'] = 7 + min((s_len - 100) // 50, 3)
        else:
            scores['pacing'] = max(s_len // 20, 3)
        
        # 6. Dopamine Density — 爽点密度
        d_words = ['突破', '获得', '升级', '秒杀', '打脸', '碾压', '赚钱', '觉醒', '逆袭', '震惊', 
                   '暴打', '碾压', '宝藏', '奇遇', '赢了', '成功', '击败']
        d_count = sum(1 for w in d_words if w in summary)
        scores['dopamine_density'] = min(d_count * 2, 10)
        if scores['dopamine_density'] < 2 and ch_num <= 3:
            issues.append('爽点不足')
        
        # 综合
        avg = sum(scores.values()) / len(scores)
        total_score += avg
        dims += 1
        
        results[ch_num] = {
            'title': title,
            'scores': scores,
            'average': round(avg, 1),
            'issues': issues,
            'passed': avg >= 5.0,
        }
    
    overall = round(total_score / dims, 1) if dims else 0
    return {
        'score': overall,
        'detail': results,
        'passed': overall >= 5.0,
        'issue_count': sum(len(r['issues']) for r in results.values()),
    }


def review_pacing(chapters_meta, chapters_content, pid, novel_name):
    """Pacing Review — LLM 版：评估节奏与冲突密度"""
    if not chapters_content:
        print("    ⚠️ 无全文，回退到关键词评分")
        return _legacy_review_pacing(chapters_meta, pid, novel_name)
    
    rubric = """Pacing（节奏与冲突密度）— 评估叙事节奏：

• 0-3: 节奏拖沓，无冲突/事件，读者会无聊弃书
• 4-6: 有一定事件推进，但节奏平淡，缺乏张力起伏
• 7-8: 节奏紧凑，冲突和缓急交替自然
• 9-10: 节奏精准，每一段都有推进力，冲突密度完美

子维度：
- event_density: 事件密度（每章有多少关键事件发生）
- conflict_density: 冲突密度（矛盾/对抗/压力）
- progression: 剧情推进感（有明确的发展和变化）"""

    try:
        result = _llm_evaluate(chapters_content, rubric, "关注前3章的节奏控制，黄金三章必须足够紧凑。")
    except ValueError as e:
        print(f"    ⚠️ LLM 评估失败 ({e})，回退到关键词评分")
        return _legacy_review_pacing(chapters_meta, pid, novel_name)
    
    avg = result.get('overall', 0)
    detail = {}
    for ch_num in chapters_meta:
        ch = result.get(str(ch_num), {})
        scores = {k: ch.get(k, 5) for k in ['event_density', 'conflict_density', 'progression']}
        detail[ch_num] = {
            'scores': scores,
            'average': ch.get('score', 5),
            'issues': ch.get('issues', []),
            'passed': ch.get('score', 5) >= 5.0,
        }
    
    return {
        'score': avg,
        'detail': detail,
        'passed': avg >= 5.0,
        'issue_count': sum(len(v.get('issues', [])) for v in result.values() if isinstance(v, dict)),
        'method': 'llm',
    }

def _legacy_review_pacing(chapters_meta, pid, novel_name):
    """Pacing & Conflict Density — 关键词版（回退）"""
    results = {}
    total_score = 0
    dims = 0
    
    for ch_num in sorted(chapters_meta.keys()):
        meta = chapters_meta[ch_num]
        summary = (meta.get('summary') or '')[:300]
        timeline = meta.get('timeline', [])
        
        scores = {}
        issues = []
        
        # 事件密度 — 时间线事件数量
        ev_count = len(timeline) if isinstance(timeline, list) else 0
        if ev_count >= 3:
            scores['event_density'] = 8 + min((ev_count - 3), 2)
        elif ev_count >= 1:
            scores['event_density'] = 5 + ev_count
        else:
            scores['event_density'] = 3
            issues.append('无时间线事件')
        
        # 冲突密度
        c_words = ['冲突', '对峙', '战斗', '追杀', '争吵', '对抗', '打斗', '陷阱', '逃跑', '伏击',
                   '偷袭', '刺杀', '围剿', '逃亡']
        c_count = sum(1 for w in c_words if w in summary)
        scores['conflict_density'] = min(c_count * 2.5, 10)
        if c_count == 0:
            issues.append('无冲突元素')
        elif c_count <= 1:
            issues.append('冲突不足')
        
        # 变化/推进感
        p_words = ['改变', '发现', '揭露', '进入', '突破', '获得', '新', '终于', '成功']
        p_count = sum(1 for w in p_words if w in summary)
        scores['progression'] = min(p_count * 1.5, 10)
        if p_count == 0:
            issues.append('剧情无推进')
        
        avg = sum(scores.values()) / len(scores)
        total_score += avg
        dims += 1
        
        results[ch_num] = {
            'scores': scores,
            'average': round(avg, 1),
            'issues': issues,
            'passed': avg >= 5.0,
        }
    
    overall = round(total_score / dims, 1) if dims else 0
    return {
        'score': overall,
        'detail': results,
        'passed': overall >= 5.0,
        'issue_count': sum(len(r['issues']) for r in results.values()),
    }


def review_retention(chapters_meta, chapters_content, pid, novel_name):
    """Retention Review — LLM 版：评估章末钩子和下一章驱动力"""
    if not chapters_content:
        print("    ⚠️ 无全文，回退到关键词评分")
        return _legacy_review_retention(chapters_meta, pid, novel_name)
    
    # 取每章最后 500 字评估章末钩子
    endings = {}
    for ch_num, text in chapters_content.items():
        endings[ch_num] = text[-500:] if len(text) > 500 else text
    
    rubric = """Retention（留存力）— 评估每章结尾和追读驱动力：

• 0-3: 章末无钩子，读者没有继续读下一章的冲动
• 4-6: 章末有事件但缺少悬念/疑问，可看可不看
• 7-8: 章末有明显悬念/反转/疑问句，让人想翻页
• 9-10: 章末制造了强烈的「必须知道接下来」的冲动

子维度：
- hook_strength: 章末钩子强度（悬念/反转/疑问）
- drive: 下一章驱动力（读者想知道什么）
- chapter_ending_quality: 章节结尾的节奏和情绪处理"""

    try:
        result = _llm_evaluate(endings, rubric, "前三章的章末钩子决定留存率，严格评分。")
    except ValueError as e:
        print(f"    ⚠️ LLM 评估失败 ({e})，回退到关键词评分")
        return _legacy_review_retention(chapters_meta, pid, novel_name)
    
    avg = result.get('overall', 0)
    detail = {}
    critical_risks = []
    for ch_num in chapters_meta:
        ch = result.get(str(ch_num), {})
        score = ch.get('score', 5)
        issues = ch.get('issues', [])
        detail[ch_num] = {
            'score': score,
            'issues': issues,
            'passed': score >= 5.0,
        }
        if ch_num <= 3 and score < 5:
            critical_risks.append({
                'chapter': ch_num,
                'risk': 'critical' if score < 3 else 'medium',
                'reason': f'黄金章留存风险: 章末钩子得分 {score}/10',
            })
    
    return {
        'score': avg,
        'detail': detail,
        'critical_risks': critical_risks,
        'risks': critical_risks,
        'passed': avg >= 5.0,
        'issue_count': len([v for v in result.values() if isinstance(v, dict) and v.get('issues')]),
        'method': 'llm',
    }

def _legacy_review_retention(chapters_meta, pid, novel_name):
    """Retention Review — 关键词版（回退）"""
    results = {}
    issues = []
    total_score = 0
    
    meta_list = sorted(chapters_meta.items())
    for i, (ch_num, meta) in enumerate(meta_list):
        hook = (meta.get('hook') or meta.get('summary') or '')
        
        score = 0
        ch_issues = []
        
        # 1. 是否有章末钩子
        if hook:
            # 从最后200字判断钩子强度
            last_200 = hook[-200:] if len(hook) > 200 else hook
            q_words = ['为什么', '是谁', '是什么', '怎么办', '难道', '难道说', '秘密', '真相', '究竟', '等待']
            q_count = sum(1 for w in q_words if w in last_200)
            score += min(q_count * 2.5, 5)
            if q_count == 0:
                ch_issues.append('章末缺少悬念钩子')
        else:
            score += 1
            ch_issues.append('缺少章末钩子')
        
        # 2. 是否有下一章驱动力
        d_words = ['然后', '接下来', '下一步', '必须', '需要', '决定', '准备', '计划', '寻找']
        d_count = sum(1 for w in d_words if w in hook[-300:])
        score += min(d_count * 2, 5)
        if d_count == 0:
            ch_issues.append('缺乏明确的下一章驱动力')
        
        results[ch_num] = {
            'score': round(score, 1),
            'issues': ch_issues,
            'passed': score >= 5.0,
        }
        total_score += score
        
        if i < len(meta_list) - 1:  # 非最后一章
            if ch_issues:
                issues.append({
                    'chapter': ch_num,
                    'risk': 'high' if score < 3 else 'medium',
                    'reason': ch_issues[0],
                })
    
    # 前3章特别检查
    for ch_num in [1, 2, 3]:
        if ch_num in results and results[ch_num]['score'] < 5:
            issues.append({
                'chapter': ch_num,
                'risk': 'critical',
                'reason': f'黄金章留存风险: 章末钩子得分 {results[ch_num]["score"]}/10',
            })
    
    overall = round(total_score / len(results), 1) if results else 0
    return {
        'score': overall,
        'detail': results,
        'critical_risks': [i for i in issues if i.get('risk') == 'critical'],
        'risks': issues,
        'passed': overall >= 5.0,
        'issue_count': len(issues),
    }


def review_ai_smell(chapters_meta, pid, novel_name):
    """AI Smell Review — AI味检测（纯规则，无需 LLM）"""
    results = {}
    total_issues = 0
    severity_scores = []
    
    for ch_num in sorted(chapters_meta.keys()):
        meta = chapters_meta[ch_num]
        summary = (meta.get('summary') or '')
        hook = (meta.get('hook') or '')
        text = summary + ' ' + hook
        
        ch_issues = {}
        ch_total = 0
        
        for smell_type, patterns in _AI_SMELL_PATTERNS.items():
            count = 0
            for pattern in patterns:
                matches = re.findall(pattern, text)
                count += len(matches)
            if count > 0:
                ch_issues[smell_type] = count
                ch_total += count
        
        # 评分: 每处AI味扣1分，最多扣到0
        score = max(10 - ch_total, 0)
        
        results[ch_num] = {
            'score': score,
            'ai_smells': ch_issues,
            'total_hits': ch_total,
            'passed': score >= 6.0,
        }
        total_issues += ch_total
        
        if ch_total > 0:
            severity = 'high' if ch_total >= 5 else ('medium' if ch_total >= 3 else 'low')
            severity_scores.append((ch_num, severity, ch_total))
    
    # 前3章特别注意
    golden_issues = sum(results.get(c, {}).get('total_hits', 0) for c in [1, 2, 3])
    golden_warning = None
    if golden_issues > 5:
        golden_warning = f'前三章AI味共 {golden_issues} 处，建议优先清理'
    
    overall = round(sum(r['score'] for r in results.values()) / len(results), 1) if results else 10
    return {
        'score': overall,
        'detail': results,
        'golden_three_warning': golden_warning,
        'total_ai_smells': total_issues,
        'high_severity_chapters': [c for c, s, n in severity_scores if s == 'high'],
        'passed': overall >= 6.0,
    }


def review_market(chapters_meta, pid, novel_name):
    """Market Review — 平台适配评审（番茄/起点/女频）"""
    results = {}
    
    # 从 summary 和 hook 提取特征
    all_text = ''
    for meta in chapters_meta.values():
        all_text += (meta.get('summary') or '') + ' '
        all_text += (meta.get('hook') or '') + ' '
    
    # 番茄模式 (爽点驱动)
    fanqie_score = 0
    fanqie_words = ['秒杀', '打脸', '碾压', '觉醒', '暴打', '捡漏', '逆袭', '突破', '升级', '赚钱', '打脸', '震惊全场']
    fanqie_count = sum(1 for w in fanqie_words if w in all_text)
    fanqie_score = min(fanqie_count / 5, 10)
    
    # 起点模式 (设定/世界观驱动)
    qidian_score = 0
    qidian_words = ['规则', '系统', '世界', '维度', '能力', '觉醒', '阶位', '权柄', '根源', '定律', '法则']
    qidian_count = sum(1 for w in qidian_words if w in all_text)
    qidian_score = min(qidian_count / 8, 10)
    
    # 女频模式 (情绪/关系驱动)
    nvping_score = 0
    nvping_words = ['他', '她', '爱情', '心跳', '温柔', '冷漠', '眼泪', '微笑', '拥抱', '守护', '拒绝', '误会']
    nvping_count = sum(1 for w in nvping_words if w in all_text)
    nvping_score = min(nvping_count / 10, 10)
    
    # 综合适配建议
    max_platform = max(fanqie_score, qidian_score, nvping_score)
    if max_platform == fanqie_score:
        best_platform = '番茄'
    elif max_platform == qidian_score:
        best_platform = '起点'
    else:
        best_platform = '女频'
    
    return {
        'scores': {
            'fanqie': round(fanqie_score, 1),
            'qidian': round(qidian_score, 1),
            'nvping': round(nvping_score, 1),
        },
        'best_platform': best_platform,
        'score': round(max_platform, 1),
        'passed': max_platform >= 5.0,
    }


def review_character_charm(chapters_meta, chapters_content, pid, novel_name):
    """Character Charm Review — LLM 版：基于正文评估角色魅力"""
    if not chapters_content:
        print("    ⚠️ 无全文，回退到关键词评分")
        return _legacy_review_character_charm(chapters_meta, pid, novel_name)
    
    rubric = """Character Charm（角色魅力）— 评估小说中角色的吸引力和辨识度：

• 0-3: 角色扁平模板化，无辨识度，读者记不住
• 4-6: 角色有基本人设但缺乏魅力/记忆点
• 7-8: 角色有鲜明性格和记忆点，读者能共情/喜欢/讨厌
• 9-10: 角色极具魅力，读者会因为角色而追书

评估维度：
- distinctiveness: 角色辨识度（说话风格/行为模式与众不同）
- motivation: 动机清晰度（角色凭什么这么做事）
- emotional_impact: 角色引发的情绪共鸣（喜欢/心疼/愤怒/期待）
- depth: 角色厚度（有矛盾、有成长空间、不单薄）
- memorability: 是否让人记住（有梗、有标签、有经典场面）"""

    # 取所有章节全文
    try:
        result = _llm_evaluate(chapters_content, rubric, "评估角色在正文中的实际表现，而非设定文件。")
    except ValueError as e:
        print(f"    ⚠️ LLM 评估失败 ({e})，回退到关键词评分")
        return _legacy_review_character_charm(chapters_meta, pid, novel_name)
    
    avg = result.get('overall', 0)
    detail = {}
    for ch_num in chapters_meta:
        ch = result.get(str(ch_num), {})
        detail[ch_num] = {
            'score': ch.get('score', 5),
            'factors': [
                f"辨识度: {ch.get('distinctiveness', 'N/A')}/10",
                f"动机: {ch.get('motivation', 'N/A')}/10",
                f"情绪共鸣: {ch.get('emotional_impact', 'N/A')}/10",
                f"厚度: {ch.get('depth', 'N/A')}/10",
                f"记忆度: {ch.get('memorability', 'N/A')}/10",
            ],
            'issues': ch.get('issues', []),
            'passed': ch.get('score', 5) >= 6.0,
        }
    
    low_charm = [str(k) for k, v in result.items() if isinstance(v, dict) and v.get('score', 5) < 6]
    
    return {
        'score': avg,
        'detail': detail,
        'low_charm_characters': low_charm,
        'passed': avg >= 6.0,
        'method': 'llm',
    }

def _legacy_review_character_charm(chapters_meta, pid, novel_name):
    """Character Charm Review — 关键词版（回退）"""
    nf, _ = get_db()
    characters = list(nf['characters'].find({'project_id': pid}))
    
    charm_scores = {}
    total_score = 0
    
    for char in characters:
        name = char.get('name', '?')
        score = 0
        factors = []
        
        # 五维检测
        if char.get('personality') and len(char.get('personality', [])) >= 2:
            score += 2
            factors.append('有性格设定')
        else:
            factors.append('缺少性格深度')
        
        if char.get('goals') or char.get('motivation'):
            score += 2
            factors.append('有明确动机')
        else:
            factors.append('缺少动机')
        
        if char.get('backstory'):
            score += 2
            factors.append('有背景故事')
        else:
            factors.append('缺少背景故事')
        
        if char.get('character_arc') or char.get('growth'):
            score += 2
            factors.append('有成长弧')
        else:
            factors.append('缺少成长弧')
        
        if char.get('flaws') or char.get('taboos'):
            score += 2
            factors.append('有缺点/禁忌')
        else:
            factors.append('缺少缺陷（趋近完美NPC）')
        
        charm_scores[name] = {
            'score': score,
            'max': 10,
            'factors': factors,
            'passed': score >= 6,
        }
        total_score += score
    
    overall = round(total_score / len(charm_scores), 1) if charm_scores else 0
    low_charm = [n for n, d in charm_scores.items() if d['score'] < 6]
    
    return {
        'score': overall,
        'detail': charm_scores,
        'low_charm_characters': low_charm,
        'passed': overall >= 6.0,
    }


def review_emotion(chapters_meta, chapters_content, pid, novel_name):
    """Emotion Review — LLM 版：评估情绪密度和情感共鸣"""
    if not chapters_content:
        print("    ⚠️ 无全文，回退到关键词评分")
        return _legacy_review_emotion(chapters_meta, pid, novel_name)
    
    rubric = """Emotion（情绪密度）— 评估小说中的情感冲击力：

• 0-3: 情绪平淡如水，读者全程无感
• 4-6: 有少量情绪描写，但缺乏深度和感染力
• 7-8: 有明显的情绪高潮和低谷，能让读者共情
• 9-10: 情绪极具感染力，读者会跟着哭/笑/紧张

评估维度：
- positive_emotion: 积极情绪（希望、温暖、感动、自豪）
- negative_emotion: 消极情绪（恐惧、愤怒、悲伤、绝望）  
- intense_emotion: 强烈情绪（震惊、震撼、意外、不可思议）
- emotional_pacing: 情绪起伏节奏（张弛有度还是持续平淡）"""

    try:
        result = _llm_evaluate(chapters_content, rubric, "前三章需要在前500字内就有情绪冲击力。")
    except ValueError as e:
        print(f"    ⚠️ LLM 评估失败 ({e})，回退到关键词评分")
        return _legacy_review_emotion(chapters_meta, pid, novel_name)
    
    avg = result.get('overall', 0)
    detail = {}
    for ch_num in chapters_meta:
        ch = result.get(str(ch_num), {})
        detail[ch_num] = {
            'score': ch.get('score', 5),
            'positive': ch.get('positive_emotion', 0),
            'negative': ch.get('negative_emotion', 0),
            'intense': ch.get('intense_emotion', 0),
            'total_emotions': ch.get('positive_emotion', 0) + ch.get('negative_emotion', 0) + ch.get('intense_emotion', 0),
            'issues': ch.get('issues', []),
            'passed': ch.get('score', 5) >= 4.0,
        }
    
    return {
        'score': avg,
        'detail': detail,
        'passed': avg >= 4.0,
        'issue_count': sum(1 for v in result.values() if isinstance(v, dict) and v.get('issues')),
        'method': 'llm',
    }

def _legacy_review_emotion(chapters_meta, pid, novel_name):
    """Emotion Review — 关键词版（回退）"""
    results = {}
    total_score = 0
    
    pos_words = ['希望', '感动', '温暖', '信任', '勇气', '喜悦', '幸福', '自豪', '感激']
    neg_words = ['恐惧', '愤怒', '绝望', '悲伤', '背叛', '痛苦', '焦虑', '仇恨', '无奈', '孤独']
    int_words = ['震惊', '意外', '不可思议', '难以置信', '惊讶', '震撼']
    
    for ch_num in sorted(chapters_meta.keys()):
        meta = chapters_meta[ch_num]
        summary = (meta.get('summary') or '')
        hook = (meta.get('hook') or '')
        text = summary + ' ' + hook
        
        pos_c = sum(1 for w in pos_words if w in text)
        neg_c = sum(1 for w in neg_words if w in text)
        int_c = sum(1 for w in int_words if w in text)
        
        # 情绪总分: 积极+消极+惊喜
        emo_total = pos_c + neg_c + int_c
        
        # 前3章需要更强的情绪冲击
        is_golden = ch_num <= 3
        threshold = 3 if is_golden else 2
        
        score = min(emo_total * 2, 10)
        issues = []
        if emo_total < threshold:
            issues.append('情绪密度不足')
        
        results[ch_num] = {
            'score': score,
            'positive': pos_c,
            'negative': neg_c,
            'intense': int_c,
            'total_emotions': emo_total,
            'issues': issues,
            'passed': score >= 4.0,
        }
        total_score += score
    
    overall = round(total_score / len(results), 1) if results else 0
    return {
        'score': overall,
        'detail': results,
        'passed': overall >= 4.0,
        'issue_count': sum(1 for r in results.values() if r['issues']),
    }


def review_readability(chapters_meta, pid, novel_name):
    """Readability Review — 可读性检查（句式、段落、对话比例）"""
    results = {}
    
    for ch_num in sorted(chapters_meta.keys()):
        meta = chapters_meta[ch_num]
        text = (meta.get('summary') or '')
        
        # 简单可读性指标
        s_len = len(text)
        sentences = re.split(r'[。！？\n]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        avg_sentence_len = s_len / max(len(sentences), 1)
        
        # 对话比例估算 (引号内字数)
        dialogue_chars = len(''.join(re.findall(r'「[^」]*」|"[^"]*"|『[^』]*』', text)))
        dialogue_ratio = dialogue_chars / max(s_len, 1)
        
        score = 7  # 基础分
        issues = []
        
        if avg_sentence_len > 80:
            score -= 2
            issues.append('句子偏长')
        elif avg_sentence_len < 10:
            score -= 1
            issues.append('句子过短')
        
        if dialogue_ratio > 0.6:
            score -= 2
            issues.append('对话比例过高')
        
        score = max(score, 0)
        results[ch_num] = {
            'score': score,
            'avg_sentence_length': round(avg_sentence_len, 1),
            'dialogue_ratio': round(dialogue_ratio, 2),
            'issues': issues,
            'passed': score >= 5,
        }
    
    overall = round(sum(r['score'] for r in results.values()) / len(results), 1) if results else 7
    return {
        'score': overall,
        'detail': results,
        'passed': overall >= 5,
        'issue_count': sum(1 for r in results.values() if r['issues']),
    }


# ─── 裁决系统 ──────────────────────────────────────────────

def make_verdict(dimensions, golden_only=False):
    """综合裁决：通过/条件通过/打回"""
    passed_dims = sum(1 for d in dimensions.values() if d.get('passed', False))
    total_dims = len(dimensions)
    
    # 定义各维度权重
    weights = {
        'hook': 0.25,
        'retention': 0.20,
        'pacing': 0.15,
        'emotion': 0.10,
        'ai_smell': 0.10,
        'market': 0.05,
        'character_charm': 0.10,
        'readability': 0.05,
    }
    
    weighted_score = sum(
        dimensions[d].get('score', 0) * weights.get(d, 0.1)
        for d in dimensions
    )
    
    if golden_only:
        # 黄金三章标准更严
        critical_fail = (
            dimensions.get('hook', {}).get('score', 10) < 4
            or dimensions.get('retention', {}).get('score', 10) < 4
        )
        if critical_fail or weighted_score < 5:
            verdict = 'reject'
        elif weighted_score < 7:
            verdict = 'conditional_pass'
        else:
            verdict = 'pass'
    else:
        if weighted_score < 4:
            verdict = 'reject'
        elif weighted_score < 6:
            verdict = 'conditional_pass'
        else:
            verdict = 'pass'
    
    # 收集所有需要重写的章节
    rewrite_patches = generate_rewrite_patches(dimensions)
    
    return {
        'verdict': verdict,
        'weighted_score': round(weighted_score, 1),
        'passed_dimensions': f'{passed_dims}/{total_dims}',
        'failed_dimensions': [d for d, v in dimensions.items() if not v.get('passed', False)],
        'critical_issues': extract_critical_issues(dimensions),
        'rewrite_patches': rewrite_patches,
    }


def extract_critical_issues(dimensions):
    """从所有维度提取 critical 级别问题"""
    issues = []
    
    # Hook 严重扣分
    hook = dimensions.get('hook', {})
    if hook.get('score', 10) < 4:
        issues.append({'dimension': 'hook', 'severity': 'critical', 'message': '黄金三章严重不足，留存率极低'})
    elif hook.get('score', 10) < 6:
        issues.append({'dimension': 'hook', 'severity': 'high', 'message': '前三章吸引力不足'})
    
    # Retention 严重扣分
    ret = dimensions.get('retention', {})
    if ret.get('score', 10) < 4:
        issues.append({'dimension': 'retention', 'severity': 'critical', 'message': '章末严重缺乏钩子，追读率低'})
    
    # AI味
    ai = dimensions.get('ai_smell', {})
    if ai.get('score', 10) < 5:
        issues.append({'dimension': 'ai_smell', 'severity': 'high', 'message': f'AI味过重({ai.get("total_ai_smells",0)}处)'})
    
    # 节奏
    pacing = dimensions.get('pacing', {})
    if pacing.get('score', 10) < 4:
        issues.append({'dimension': 'pacing', 'severity': 'high', 'message': '节奏失控，冲突密度低'})
    
    return issues


def generate_rewrite_patches(dimensions):
    """根据评审结果生成重写 Patch 建议"""
    patches = []
    
    hook_detail = dimensions.get('hook', {}).get('detail', {})
    for ch_num, detail in hook_detail.items():
        if not detail.get('passed', True):
            low_scores = [k for k, v in detail.get('scores', {}).items() if v < 4]
            for dim in low_scores:
                suggestion_map = {
                    'curiosity': '在开头增加悬念/疑问，提前抛出核心秘密',
                    'tension': '提早引入冲突/危机，打破平静开局',
                    'mystery': '添加神秘元素，让读者产生「为什么会这样」的好奇',
                    'emotional_pull': '增加情绪拉扯（愤怒/同情/期待），让读者代入',
                    'pacing': '加快节奏，减少铺垫段落',
                    'dopamine_density': '提前释放爽点，让读者在前500字就「爽到」',
                }
                patches.append({
                    'chapter': ch_num,
                    'dimension': 'hook',
                    'sub_dimension': dim,
                    'suggestion': suggestion_map.get(dim, f'提升{dim}评分'),
                    'priority': 'high' if ch_num <= 3 else 'medium',
                })
    
    ret_detail = dimensions.get('retention', {}).get('detail', {})
    for ch_num, detail in ret_detail.items():
        if detail.get('score', 10) < 5:
            patches.append({
                'chapter': ch_num,
                'dimension': 'retention',
                'sub_dimension': 'chapter_end_hook',
                'suggestion': '章末补充悬念/疑问句，制造「下一章见」驱动力',
                'priority': 'critical' if ch_num <= 3 else 'high',
            })
    
    ai_detail = dimensions.get('ai_smell', {}).get('detail', {})
    for ch_num, detail in ai_detail.items():
        if detail.get('total_hits', 0) >= 5:
            patches.append({
                'chapter': ch_num,
                'dimension': 'ai_smell',
                'sub_dimension': 'ai_pattern',
                'suggestion': f'清理{detail.get("total_hits")}处AI味词（空洞描写/机械情绪/废话总结）',
                'priority': 'high',
            })
    
    return patches


# ─── 报告生成 ──────────────────────────────────────────────

def generate_report(pid, novel_name, scope, dimensions, verdict):
    """生成完整评审报告"""
    report = {
        'project_id': pid,
        'novel_name': novel_name,
        'review_id': hashlib.md5(f'{pid}_{datetime.now().isoformat()}'.encode()).hexdigest()[:12],
        'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'scope': scope,
        'dimension_scores': {k: {
            'score': v.get('score', 0),
            'passed': v.get('passed', False),
            'issue_count': v.get('issue_count', 0),
        } for k, v in dimensions.items()},
        'overall_score': verdict['weighted_score'],
        'verdict': verdict['verdict'],
        'critical_issues': verdict['critical_issues'],
        'rewrite_patches': verdict['rewrite_patches'],
        'passed_dimensions': verdict['passed_dimensions'],
        'failed_dimensions': verdict['failed_dimensions'],
    }
    
    # Visual summary
    bar = []
    for name, info in report['dimension_scores'].items():
        s = info['score']
        bar_line = f"  {name:<18s} {'█' * int(s)}{'░' * (10 - int(s))} {s:.1f}/10 {'✅' if info['passed'] else '❌'}"
        bar.append(bar_line)
    report['visual_summary'] = '\n'.join(bar)
    
    return report


def print_report(report):
    """打印人类可读报告"""
    print('=' * 55)
    print(f'  Novel Judge Report — {report["novel_name"]}')
    print(f'  Review ID: {report["review_id"]}')
    print(f'  Time: {report["reviewed_at"]}')
    print(f'  Scope: {report["scope"]}')
    print('=' * 55)
    
    verdict = report['verdict']
    verdict_icon = '✅' if verdict == 'pass' else ('🟡' if verdict == 'conditional_pass' else '❌')
    print(f'\n  {verdict_icon} Verdict: {verdict.upper()} (Score: {report["overall_score"]}/10)')
    print(f'  Passed: {report["passed_dimensions"]}, Failed: {len(report["failed_dimensions"])}')
    
    print(f'\n  {"─" * 48}')
    print(report['visual_summary'])
    print(f'  {"─" * 48}')
    
    if report['critical_issues']:
        print(f'\n  🔴 CRITICAL ISSUES:')
        for issue in report['critical_issues']:
            print(f'    [{issue["severity"].upper()}] [{issue["dimension"]}] {issue["message"]}')
    
    if report['rewrite_patches']:
        print(f'\n  📝 REWRITE PATCHES ({len(report["rewrite_patches"])}建议):')
        for patch in report['rewrite_patches'][:10]:
            print(f'    [{patch["priority"].upper()}] ch{patch["chapter"]} ({patch["dimension"]}): {patch["suggestion"][:80]}')
        if len(report['rewrite_patches']) > 10:
            print(f'    ... 还有 {len(report["rewrite_patches"]) - 10} 条')
    
    print(f'\n  {"=" * 55}\n')


# ─── 主流程 ──────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Novel Judge — AI 小说质检系统')
    sub = parser.add_subparsers(dest='command')
    
    # review
    review_parser = sub.add_parser('review', help='执行全维度评审')
    review_parser.add_argument('novel_name', help='小说名称')
    review_parser.add_argument('--chapters', default='1-3', help='章节范围 (e.g. 1-136, 1-3)')
    review_parser.add_argument('--golden', action='store_true', help='黄金三章模式（3倍严格）')
    review_parser.add_argument('--dimension', default=None, help='指定维度 (逗号分隔)')
    review_parser.add_argument('--verdict-only', action='store_true', help='只输出裁决')
    
    # patch
    patch_parser = sub.add_parser('patch', help='生成重写 Patch')
    patch_parser.add_argument('novel_name', help='小说名称')
    patch_parser.add_argument('--chapter', required=True, help='指定章节')
    patch_parser.add_argument('--issue', required=True, help='问题类型')
    
    # history
    sub.add_parser('history', help='查看历史评审')
    
    args = parser.parse_args()
    
    if args.command == 'review':
        do_review(args)
    elif args.command == 'patch':
        do_patch(args)
    elif args.command == 'history':
        do_history(args)
    else:
        parser.print_help()


def do_review(args):
    nf, novel = get_db()
    
    pid = get_project_id(nf, args.novel_name)
    if not pid:
        print('❌ 找不到项目')
        return
    
    # 解析章节范围
    try:
        parts = args.chapters.split('-')
        if len(parts) == 2:
            ch_start, ch_end = int(parts[0]), int(parts[1])
        else:
            ch_start = ch_end = int(parts[0])
    except (ValueError, IndexError):
        ch_start, ch_end = 1, 3
    
    chapter_nums = list(range(ch_start, ch_end + 1))
    
    # 加载章节元数据
    chapters_meta = {}
    for ch_num in chapter_nums:
        meta = load_chapter_metadata(nf, pid, ch_num)
        if meta:
            # 清理 _id 不可序列化问题
            if '_id' in meta:
                meta['_id'] = str(meta['_id'])
            chapters_meta[ch_num] = meta
    
    if not chapters_meta:
        print(f'❌ 未找到章节数据 (ch{ch_start}-{ch_end})')
        return
    
    # 加载章节正文
    print(f'  加载章节正文...')
    chapters_content = {}
    for ch_num in chapter_nums:
        content = load_chapter_content(novel, args.novel_name, ch_num)
        if content:
            chapters_content[ch_num] = content
    
    if chapters_content:
        print(f'  已加载 {len(chapters_content)} 章正文')
    else:
        print(f'  ⚠️ 未加载到正文，将使用关键词回退模式')
    
    print(f'\n  ─── Novel Judge System 启动 ───')
    print(f'  项目: {args.novel_name}')
    print(f'  范围: ch{ch_start}-{ch_end} ({len(chapters_meta)}章)')
    print(f'  模式: {"黄金三章高规格" if args.golden else "标准"}')
    
    # 选择要运行的维度
    all_dimensions = ['hook', 'pacing', 'retention', 'ai_smell', 'market', 'character_charm', 'emotion', 'readability']
    
    if args.dimension:
        selected = [d.strip() for d in args.dimension.split(',')]
    else:
        selected = all_dimensions
    
    dimensions = {}
    
    for dim in selected:
        if dim == 'hook':
            print(f'\n  评审维度: Hook（黄金三章/开头检查）...')
            dimensions[dim] = review_hook(chapters_meta, chapters_content, pid, args.novel_name)
            print(f'    Score: {dimensions[dim]["score"]}/10 {"✅" if dimensions[dim]["passed"] else "❌"}')
            
        elif dim == 'pacing':
            print(f'  评审维度: Pacing（节奏与冲突密度）...')
            dimensions[dim] = review_pacing(chapters_meta, chapters_content, pid, args.novel_name)
            print(f'    Score: {dimensions[dim]["score"]}/10 {"✅" if dimensions[dim]["passed"] else "❌"}')
            
        elif dim == 'retention':
            print(f'  评审维度: Retention（留存/章末钩子）...')
            dimensions[dim] = review_retention(chapters_meta, chapters_content, pid, args.novel_name)
            print(f'    Score: {dimensions[dim]["score"]}/10 {"✅" if dimensions[dim]["passed"] else "❌"}')
            if dimensions[dim].get('critical_risks'):
                for r in dimensions[dim]['critical_risks']:
                    print(f'    🔴 ch{r["chapter"]}: {r["reason"]}')
                    
        elif dim == 'ai_smell':
            print(f'  评审维度: AI Smell（AI味检测）...')
            dimensions[dim] = review_ai_smell(chapters_meta, pid, args.novel_name)
            print(f'    Score: {dimensions[dim]["score"]}/10 {"✅" if dimensions[dim]["passed"] else "❌"}')
            print(f'    总AI味: {dimensions[dim]["total_ai_smells"]}处')
            if dimensions[dim].get('golden_three_warning'):
                print(f'    ⚠️ {dimensions[dim]["golden_three_warning"]}')
                
        elif dim == 'market':
            print(f'  评审维度: Market（平台适配）...')
            dimensions[dim] = review_market(chapters_meta, pid, args.novel_name)
            s = dimensions[dim]['scores']
            print(f'    番茄: {s["fanqie"]}/10  起点: {s["qidian"]}/10  女频: {s["nvping"]}/10')
            print(f'    最佳适配: {dimensions[dim]["best_platform"]}')
            
        elif dim == 'character_charm':
            print(f'  评审维度: Character Charm（角色魅力）...')
            dimensions[dim] = review_character_charm(chapters_meta, chapters_content, pid, args.novel_name)
            print(f'    Score: {dimensions[dim]["score"]}/10')
            if dimensions[dim].get('low_charm_characters'):
                print(f'    ⚠️ 魅力不足: {", ".join(dimensions[dim]["low_charm_characters"])}')
                
        elif dim == 'emotion':
            print(f'  评审维度: Emotion（情绪密度）...')
            dimensions[dim] = review_emotion(chapters_meta, chapters_content, pid, args.novel_name)
            print(f'    Score: {dimensions[dim]["score"]}/10 {"✅" if dimensions[dim]["passed"] else "❌"}')
            
        elif dim == 'readability':
            print(f'  评审维度: Readability（可读性）...')
            dimensions[dim] = review_readability(chapters_meta, pid, args.novel_name)
            print(f'    Score: {dimensions[dim]["score"]}/10 {"✅" if dimensions[dim]["passed"] else "❌"}')
    
    if not dimensions:
        print('❌ 未执行任何维度')
        return
    
    # 裁决
    golden_mode = args.golden or (ch_start <= 3 and ch_end >= 1)
    verdict = make_verdict(dimensions, golden_only=golden_mode)
    
    # 生成报告
    scope = f'ch{ch_start}-{ch_end}' if ch_start != ch_end else f'ch{ch_start}'
    report = generate_report(pid, args.novel_name, scope, dimensions, verdict)
    
    if not args.verdict_only:
        print()
        print_report(report)
    else:
        print(f'\n  Verdict: {verdict["verdict"].upper()} (Score: {verdict["weighted_score"]}/10)')
        print(f'  Failed: {", ".join(verdict["failed_dimensions"]) if verdict["failed_dimensions"] else "None"}')
    
    # 保存到 review_reports 集合
    try:
        nf['review_reports'].insert_one(report)
        print(f'  ✅ 评审报告已保存 (review_id: {report["review_id"]})')
    except Exception as e:
        print(f'  ⚠️ 保存失败: {e}')
    
    return report


def do_patch(args):
    """生成重写 Patch"""
    print(f'  📝 生成重写 Patch — ch{args.chapter}, 问题: {args.issue}')
    print('  ⚡ 此功能需要 delegate_task 配合 LLM 生成完整 Patch')
    print('  机械化提取建议:')
    print(f'    ch{args.chapter}: 针对 "{args.issue}" 问题生成局部修复方案')
    print(f'    Patch 类型: {args.issue}')
    print(f'    建议通过 novel-refinement-branch skill 应用')


def do_history(args):
    """查看历史评审"""
    nf, _ = get_db()
    pid = get_project_id(nf, args.novel_name)
    
    reports = list(nf['review_reports'].find(
        {'project_id': pid}
    ).sort('reviewed_at', -1).limit(5))
    
    if not reports:
        print(f'  📭 无历史评审记录')
        return
    
    print(f'  📊 最近评审 ({len(reports)}条):')
    for r in reports:
        print(f'    {r.get("review_id")[:8]} | {r.get("verdict"):>8s} | {r.get("overall_score"):.1f}/10 | {r.get("scope"):s} | {str(r.get("reviewed_at",""))[:19]}')


if __name__ == '__main__':
    main()
