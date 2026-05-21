#!/usr/bin/env python3
"""
refine-chapter.py — 精修分支主调度器 (Refinement Router)

作用: 接管一个或一批章节, 自动判断需要哪种精修, 生成Patch提案,
     经确认后应用Patch, 写入Diff记录。

用法:
  # 分析诊断（只报告不修）
  python3 refine-chapter.py analyze '诡异游戏' --chapters 1-10
  
  # 全线检查 + 自动生成Patch提案
  python3 refine-chapter.py analyze '诡异游戏' --chapters 1-136 --full
  
  # 批量精修（读取提案→确认→应用）
  python3 refine-chapter.py apply '诡异游戏' --chapters 50-60 --types continuity,lore,prose
  
  # 查看待处理的Patch
  python3 refine-chapter.py status '诡异游戏'
  
  # 精修指定章节（三段式：分析→提案→应用）
  python3 refine-chapter.py refine '诡异游戏' --chapters 1-10 --types lore,continuity

架构:
  精修系统不拥有"世界真相"。
  世界真相始终来自 Creation Core (MongoDB novel_factory.*)。
  精修只提 Patch, 不直接改设定。
"""

import pymongo
import json
import sys
import os
import re
import hashlib
import argparse
import uuid
from datetime import datetime, timezone
from collections import defaultdict
from difflib import unified_diff

# ── 配置 ──────────────────────────────────────────

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"
PATCH_COLLECTION = "refinement_patches"
LOG_COLLECTION = "refinement_log"

CHARACTER_ALIASES = {
    '林远': ['林远', '主角'],
    '顾晚': ['顾晚', '顾晚姐', '晚姐'],
    '赵铁': ['赵铁', '铁哥', '赵哥'],
    '方晴': ['方晴', '晴姐', '方晴姐'],
    '周文': ['周文', '阿文', '文哥'],
    '老钱': ['老钱', '钱叔'],
    '秦征': ['秦征', '城主', '秦城主'],
    '沈从越': ['沈从越', '沈教授', '从越', '老人', '图书馆老人', '馆长'],
    '江漓': ['江漓', '漓姐', '小漓'],
    '陆沉': ['陆沉', '陆馆长', '陆先生'],
    '逐字人': ['逐字人', '自检程序'],
}


def connect():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    return client, client["novel_factory"], client["novel"]


def resolve_project(db_nf, db_novel, project_name):
    """模糊匹配项目"""
    nv = db_novel['novels'].find_one({
        '$or': [
            {'title': {'$regex': re.escape(project_name)}},
            {'name': {'$regex': re.escape(project_name)}},
        ]
    })
    if not nv:
        return None, None, None
    
    novel_name = nv.get('name') or nv.get('title', '')
    proj = db_nf['projects'].find_one({'title': {'$regex': re.escape(novel_name)}})
    pid = proj['project_id'] if proj else None
    return novel_name, pid, nv.get('title', '')


def chapter_range(chapters_arg, total=136):
    """解析章节区间: '1-10' -> [1,2,...,10], '1,5,20' -> [1,5,20]"""
    if '-' in str(chapters_arg):
        parts = chapters_arg.split('-')
        start, end = int(parts[0]), int(parts[1])
        return list(range(start, min(end + 1, total + 1)))
    elif ',' in str(chapters_arg):
        return [int(x.strip()) for x in chapters_arg.split(',')]
    else:
        return [int(chapters_arg)]


def content_hash(text):
    """生成正文内容的 SHA256"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def generate_diff(original, patched, context=3):
    """生成 unified diff"""
    orig_lines = original.splitlines(keepends=True)
    patch_lines = patched.splitlines(keepends=True)
    diff = list(unified_diff(orig_lines, patch_lines, 
                             fromfile='original', tofile='patched',
                             n=context))
    return ''.join(diff)


def load_bible(db_nf, pid):
    """加载世界观圣经"""
    bible = db_nf['world_bible'].find_one({'project_id': pid})
    if bible:
        rules = bible.get('world_rules', bible.get('rules', []))
        raw_ps = bible.get('power_system', bible.get('power', []))
        # power_system 实际数据格式是 list[dict], 每个 dict 含 name/levels/source
        if isinstance(raw_ps, list):
            power_system = {'tiers': raw_ps, 'raw_list': raw_ps}
        else:
            power_system = raw_ps if isinstance(raw_ps, dict) else {}
        return {
            'rules': rules,
            'power_system': power_system,
            'geography': bible.get('regions', bible.get('geography', {})),
            'factions': bible.get('factions', {}),
            'key_events': bible.get('history_events', bible.get('key_events', [])),
            'version': bible.get('version', 'v1'),
        }
    # fallback
    ws = db_nf['world_state'].find_one({'project_id': pid})
    if ws:
        return {
            'rules': ws.get('active_rules', []),
            'power_system': {'tiers': []},
            'version': 'from_world_state',
        }
    return {}


# ═══════════════════════════════════════════════════
# 第一类: Consistency Refinement (一致性修复)
# ═══════════════════════════════════════════════════

def analyze_character_consistency(db_novel, db_nf, novel_name, pid, chapters):
    """检查角色一致性: 称呼/能力/关系, 生成Patch提案"""
    print(f"\n  [角色一致性] 扫描 {len(chapters)} 章...")
    patches = []
    
    chars = list(db_nf['characters'].find({'project_id': pid}))
    char_map = {}
    for c in chars:
        name = c.get('name', '')
        char_map[name] = {
            'title': c.get('title', ''),
            'abilities': c.get('abilities', []),
            'personality': c.get('personality', c.get('traits', '')),
            'relationships': c.get('relationships', {}),
        }
    
    # 用于检测称呼错误的规则
    title_mismatches = {
        '林远': ['林小姐', '林女士', '林公子'],
        '顾晚': ['顾先生', '顾少', '顾少爷'],
        '赵铁': ['赵女士', '赵小姐', '赵公子'],
        '方晴': ['方先生', '方少'],
        '周文': ['周女士', '周小姐'],
        '秦征': ['秦女士', '秦姑娘'],
    }
    
    for ch_num in chapters:
        ch = db_novel['chapters'].find_one(
            {'novelName': novel_name, 'chapterNumber': ch_num}
        )
        if not ch:
            continue
        content = ch.get('content', '') or ch.get('text', '')
        
        # 检查称呼错误
        for char_name, wrong_titles in title_mismatches.items():
            for wrong in wrong_titles:
                if wrong in content:
                    patches.append({
                        'chapter': ch_num,
                        'patch_type': 'continuity',
                        'severity': 'warning',
                        'sub_type': 'title_mismatch',
                        'reason': f"角色「{char_name}」被误称为「{wrong}」",
                        'location': content.find(wrong),
                        'context_before': content[max(0, content.find(wrong)-50):content.find(wrong)],
                        'context_after': content[content.find(wrong)+len(wrong):content.find(wrong)+len(wrong)+50],
                    })
        
        # 检查已故角色再次出现
        for char_name, info in char_map.items():
            if info.get('status') == 'dead' and char_name in content:
                patches.append({
                    'chapter': ch_num,
                    'patch_type': 'continuity',
                    'severity': 'critical',
                    'sub_type': 'dead_character_alive',
                    'reason': f"已故角色「{char_name}」在正文中出现",
                    'context_before': '',
                })
    
    if patches:
        print(f"  → 发现 {len(patches)} 个一致性问题")
        for p in patches:
            print(f"    [{p['severity']}] ch{p['chapter']}: {p['reason']}")
    else:
        print(f"  ✅ 未发现角色一致性问题")
    
    return patches


def analyze_power_consistency(db_novel, db_nf, novel_name, pid, chapters, bible):
    """检查战力/能力一致性"""
    print(f"\n  [战力一致性] 扫描 {len(chapters)} 章...")
    patches = []
    
    # 从 bible 提取战力等级
    power_system = bible.get('power_system', {})
    tiers = power_system.get('tiers', [])
    tier_names = [t.get('name', '') for t in tiers] if isinstance(tiers, list) else []
    tier_map = {}
    for t in (tiers if isinstance(tiers, list) else []):
        tier_map[t.get('name', '')] = t
    
    # 从 characters 提取角色能力
    chars = list(db_nf['characters'].find({'project_id': pid}))
    char_abilities = {}
    for c in chars:
        name = c.get('name', '')
        abilities = c.get('abilities', [])
        if isinstance(abilities, list):
            char_abilities[name] = [a.get('name', a) if isinstance(a, dict) else a for a in abilities]
    
    for ch_num in chapters:
        ch = db_novel['chapters'].find_one(
            {'novelName': novel_name, 'chapterNumber': ch_num}
        )
        if not ch:
            continue
        content = ch.get('content', '') or ch.get('text', '')
        ch_lower = content.lower()
        
        # 检查战力等级跳跃
        if tier_names:
            found_tiers = [t for t in tier_names if t.lower() in ch_lower]
            if len(found_tiers) >= 2:
                # 多个等级同时出现可能有问题
                pass  # 需要更复杂的上下文判断
        
        # 检查角色是否使用了未登记的能力
        for char_name, abilities in char_abilities.items():
            name_aliases = CHARACTER_ALIASES.get(char_name, [char_name])
            if not any(a in content for a in name_aliases):
                continue
            # 该角色出场了
            for ability in abilities:
                if isinstance(ability, str) and ability and ability in content:
                    # 能力使用正常
                    pass
            # 过于高阶的能力
            high_end_terms = ['毁灭级', '神级', '创世', '终极', '核弹级', '法则级']
            for term in high_end_terms:
                if f'{char_name[:2]}' in content and term in content:
                    patches.append({
                        'chapter': ch_num,
                        'patch_type': 'continuity',
                        'severity': 'info',
                        'sub_type': 'power_level_check',
                        'reason': f"「{char_name}」出场章节出现「{term}」级描述, 请确认是否合理",
                    })
    
    if patches:
        print(f"  → 发现 {len(patches)} 个战力相关提示")
    else:
        print(f"  ✅ 未发现战力明显异常")
    
    return patches


def analyze_timeline_consistency(db_novel, db_nf, novel_name, pid, chapters):
    """检查时间线一致性"""
    print(f"\n  [时间线一致性] 扫描 {len(chapters)} 章...")
    patches = []
    
    timeline_events = list(db_nf['timeline'].find(
        {'project_id': pid}
    ).sort('chapter', 1))
    
    # 检查时间词矛盾
    contradictory_pairs = [
        ('第二天', '同一天', 5),
        ('三天后', '第二天', 5),
        ('一周后', '第二天', 5),
        ('一个月后', '三天后', 5),
    ]
    
    prev_ch = 0
    for ch_num in chapters:
        ch = db_novel['chapters'].find_one(
            {'novelName': novel_name, 'chapterNumber': ch_num}
        )
        if not ch:
            continue
        content = ch.get('content', '') or ch.get('text', '')
        
        # 检查同一章出现矛盾的时间词
        for w1, w2, margin in contradictory_pairs:
            if w1 in content and w2 in content:
                patches.append({
                    'chapter': ch_num,
                    'patch_type': 'continuity',
                    'severity': 'warning',
                    'sub_type': 'timeline_contradiction',
                    'reason': f"同一章同时出现「{w1}」和「{w2}」",
                })
        
        prev_ch = ch_num
    
    if patches:
        print(f"  → 发现 {len(patches)} 个时间线问题")
    else:
        print(f"  ✅ 未发现时间线矛盾")
    
    return patches


# ═══════════════════════════════════════════════════
# 第二类: Narrative Enhancement 检测 (叙事增强检测)
# ═══════════════════════════════════════════════════

def analyze_pacing_and_prose(db_novel, db_nf, novel_name, chapters):
    """分析章节节奏和散文质量"""
    print(f"\n  [叙事质量] 分析 {len(chapters)} 章...")
    patches = []
    
    for ch_num in chapters:
        ch = db_novel['chapters'].find_one(
            {'novelName': novel_name, 'chapterNumber': ch_num}
        )
        if not ch:
            continue
        content = ch.get('content', '') or ch.get('text', '')
        if not content:
            continue
        
        lines = content.split('\n')
        wc = len(content)
        paragraphs = [l.strip() for l in lines if l.strip()]
        
        # 章节太短/太长
        if wc < 1500:
            patches.append({
                'chapter': ch_num,
                'patch_type': 'pacing',
                'severity': 'info',
                'sub_type': 'short_chapter',
                'reason': f"章节过短 ({wc}字, 建议2000-4000)",
            })
        elif wc > 5000:
            patches.append({
                'chapter': ch_num,
                'patch_type': 'pacing',
                'severity': 'info',
                'sub_type': 'long_chapter',
                'reason': f"章节偏长 ({wc}字), 建议考虑拆分",
            })
        
        # 对话比例过高
        dialog_chars = len(re.findall(r'「[^」]*」', content))
        dialog_ratio = dialog_chars / max(len(content), 1)
        if dialog_ratio > 0.6:
            patches.append({
                'chapter': ch_num,
                'patch_type': 'prose',
                'severity': 'info',
                'sub_type': 'high_dialog_ratio',
                'reason': f"对话占比 {dialog_ratio:.0%}, 建议增加叙事描写",
            })
        
        # AI味检测
        ai_markers = ['仿佛', '似乎', '好像', '某种', '一种说不出的']
        marker_count = sum(content.count(m) for m in ai_markers)
        if marker_count > 15:
            patches.append({
                'chapter': ch_num,
                'patch_type': 'prose',
                'severity': 'info',
                'sub_type': 'ai_smell',
                'reason': f"AI味词出现 {marker_count} 次(仿佛/似乎/好像), 建议精简",
            })
        
        # 废话词组检测
        filler_phrases = ['说实话', '老实说', '你知道吗', '我跟你说', '说真的',
                          '其实吧', '说白了', '简单来说', '不得不说', '毫无疑问']
        filler_count = sum(content.count(p) for p in filler_phrases)
        if filler_count > 5:
            patches.append({
                'chapter': ch_num,
                'patch_type': 'prose',
                'severity': 'warning',
                'sub_type': 'filler_words',
                'reason': f"废话词组出现 {filler_count} 次",
            })
        
        # 结尾悬念检查
        last_300 = content[-300:] if len(content) > 300 else content
        if not any(kw in last_300 for kw in ['？', '！', '……', '—', '……', '「']):
            patches.append({
                'chapter': ch_num,
                'patch_type': 'pacing',
                'severity': 'info',
                'sub_type': 'weak_ending',
                'reason': "章节结尾缺乏悬念钩子",
            })
    
    if patches:
        categories = defaultdict(int)
        for p in patches:
            categories[p['sub_type']] += 1
        summary = ', '.join(f'{k}:{v}' for k, v in categories.items())
        print(f"  → 发现 {len(patches)} 个叙事质量提示 ({summary})")
    else:
        print(f"  ✅ 叙事质量良好")
    
    return patches


# ═══════════════════════════════════════════════════
# 第三类: Lore Synchronization (设定同步)
# ═══════════════════════════════════════════════════

def analyze_lore_sync(db_novel, db_nf, novel_name, pid, chapters, bible):
    """检查旧章节是否与最新世界观设定一致"""
    print(f"\n  [设定同步] 扫描 {len(chapters)} 章...")
    patches = []
    
    rules = bible.get('rules', [])
    if not rules:
        print(f"  ⚠️ 无世界观规则数据, 跳过")
        return patches
    
    # 规则转成可检测的断言
    rule_checks = []
    for rule in rules:
        name = rule.get('name', rule) if isinstance(rule, dict) else rule
        desc = rule.get('description', '') if isinstance(rule, dict) else ''
        rule_checks.append({
            'name': name,
            'desc': desc,
            'forbidden_terms': [],  # 待填充
            'required_terms': [],
        })
    
    # 从 world_state 获取活跃规则
    ws = db_nf['world_state'].find_one({'project_id': pid})
    if ws:
        active_rules = ws.get('active_rules', [])
        for rule_entry in active_rules:
            rule_name = rule_entry.get('name', rule_entry.get('rule', ''))
            rule_text = rule_entry.get('description', rule_entry.get('text', ''))
            print(f"    活跃规则: {rule_name}")
    
    print(f"  ✅ 设定同步分析完成 (需手动配置规则断言)")
    return patches


# ═══════════════════════════════════════════════════
# 第四类: Foreshadow Repair (伏笔回补)
# ═══════════════════════════════════════════════════

def analyze_foreshadow_gaps(db_nf, pid, chapters):
    """分析需要补伏笔的位置"""
    print(f"\n  [伏笔回补] 分析 {len(chapters)} 章...")
    patches = []
    
    foreshadows = list(db_nf['foreshadow'].find({'project_id': pid}).sort('setup_chapter', 1))
    active_fs = [f for f in foreshadows if f.get('status') == 'active']
    
    for fs in active_fs:
        setup_ch = fs.get('setup_chapter', 0)
        callback_ch = fs.get('callback_chapter', fs.get('expected_callback_chapter', 0))
        
        if callback_ch and callback_ch > max(chapters):
            continue
        
        # 检查回调点之前是否有足够的伏笔呼应
        print(f"    伏笔「{fs.get('description','?')[:40]}」(ch{setup_ch}→ch{callback_ch}): 活跃中")
    
    print(f"  ✅ 伏笔回补分析完成, {len(active_fs)} 条活跃伏笔待处理")
    return patches


# ═══════════════════════════════════════════════════
# Patch 写入系统
# ═══════════════════════════════════════════════════

def write_patches(db_nf, pid, patches, auto_apply=False):
    """将分析结果写入 refinement_patches 集合"""
    if not patches:
        return 0
    
    count = 0
    for p in patches:
        patch_id = str(uuid.uuid4())
        doc = {
            'project_id': pid,
            'patch_id': patch_id,
            'chapter': p['chapter'],
            'patch_type': p.get('patch_type', 'unknown'),
            'severity': p.get('severity', 'info'),
            'sub_type': p.get('sub_type', ''),
            'status': 'applied' if auto_apply else 'draft',
            'reason': p['reason'],
            'location': p.get('location', 0),
            'proposed_text': p.get('proposed_text', ''),
            'original_text': p.get('original_text', ''),
            'diff': p.get('diff', ''),
            'impact': p.get('impact', 'low'),
            'created_by': 'refinement-router',
            'created_at': datetime.now(timezone.utc),
            'applied_at': datetime.now(timezone.utc) if auto_apply else None,
        }
        db_nf[PATCH_COLLECTION].insert_one(doc)
        count += 1
    
    return count


def write_refinement_log(db_nf, pid, chapter, patch_ids):
    """记录精修日志"""
    db_nf[LOG_COLLECTION].update_one(
        {'project_id': pid, 'chapter': chapter},
        {
            '$set': {'last_refined_at': datetime.now(timezone.utc)},
            '$inc': {'refinement_count': 1},
            '$push': {'patch_ids': {'$each': patch_ids}},
        },
        upsert=True,
    )


# ═══════════════════════════════════════════════════
# LLM 驱动的 Patch 生成 (Tier 3)
# ═══════════════════════════════════════════════════

def build_patch_prompt(chapter_content, chapter_num, patch_type, context_data):
    """为 LLM 构建精修提示词"""
    prompts = {
        'continuity': f"""你是一位严格的网络小说编辑。请检查以下章节第 {chapter_num} 章是否有以下问题，输出 JSON 格式报告：

检查维度：
1. 角色称呼错误（主角的叫法前后不一）
2. 能力使用错误（角色使用了未设定的能力）
3. 已死角色再次出现
4. 地点名称前后矛盾

如需修改，输出：
{{
  "patches": [
    {{
      "type": "continuity",
      "sub_type": "title_mismatch",
      "severity": "warning",
      "reason": "问题描述",
      "original_text": "原文片段",
      "proposed_text": "建议修改"
    }}
  ],
  "summary": "总体评价"
}}

参考数据（角色名和能力列表）：
{json.dumps(context_data.get('characters', {}), ensure_ascii=False, indent=2)}

章节内容：
{chapter_content[:8000]}
""",

        'prose': f"""你是一位文笔编辑。请轻润色以下第 {chapter_num} 章，只做最小修改：

允许：
- 替换重复句式
- 精简啰嗦表达
- 增强情绪感染力
- 减少AI味（仿佛、似乎、好像）
- 强化章末悬念

禁止：
- 改剧情
- 改设定
- 加新能力
- 改人物性格

输出 JSON:
{{
  "patches": [
    {{
      "type": "prose",
      "sub_type": "ai_smell" | "filler" | "weak_ending" | "rhythm",
      "severity": "info" | "warning",
      "reason": "修改原因",
      "original_text": "原文片段",
      "proposed_text": "修改后文本"
    }}
  ],
  "summary": "修改说明"
}}

章节内容：
{chapter_content[:8000]}
""",

        'foreshadow': f"""你是一位资深伏笔规划师。请检查第 {chapter_num} 章，看是否需要为后文剧情埋伏笔。

现有伏笔：
{json.dumps(context_data.get('foreshadows', []), ensure_ascii=False, indent=2)}

如果发现适合埋伏笔的位置, 输出:
{{
  "patches": [
    {{
      "type": "foreshadow",
      "sub_type": "backfill",
      "severity": "info",
      "reason": "为什么这里需要伏笔",
      "location_hint": "在哪个段落/场景之后插入",
      "proposed_text": "建议新增/修改的文本"
    }}
  ],
  "summary": "伏笔建议说明"
}}

章节内容：
{chapter_content[:8000]}
""",
    }
    return prompts.get(patch_type, prompts['continuity'])


# ═══════════════════════════════════════════════════
# 命令处理器
# ═══════════════════════════════════════════════════

def cmd_analyze(args):
    """分析模式：只检查不出Patch"""
    client, db_nf, db_novel = connect()
    try:
        novel_name, pid, title = resolve_project(db_nf, db_novel, args.project)
        if not novel_name:
            print(f"❌ 找不到项目: {args.project}")
            return
        
        chapters = chapter_range(args.chapters) if args.chapters else list(range(1, 137))
        
        print(f"\n{'='*60}")
        print(f"  精修分析: {title}")
        print(f"  章节: ch{chapters[0]}-ch{chapters[-1]} ({len(chapters)} 章)")
        print(f"{'='*60}\n")
        
        bible = load_bible(db_nf, pid)
        
        all_patches = []
        
        # 第一类: 一致性修复
        if args.types is None or 'continuity' in args.types or 'lore' in args.types or 'all' in args.types:
            all_patches.extend(analyze_character_consistency(db_novel, db_nf, novel_name, pid, chapters))
            all_patches.extend(analyze_power_consistency(db_novel, db_nf, novel_name, pid, chapters, bible))
            all_patches.extend(analyze_timeline_consistency(db_novel, db_nf, novel_name, pid, chapters))
            all_patches.extend(analyze_lore_sync(db_novel, db_nf, novel_name, pid, chapters, bible))
        
        # 第二类: 叙事增强
        if args.types is None or 'prose' in args.types or 'pacing' in args.types or 'all' in args.types:
            all_patches.extend(analyze_pacing_and_prose(db_novel, db_nf, novel_name, chapters))
        
        # 第四类: 伏笔
        if args.types is None or 'foreshadow' in args.types or 'all' in args.types:
            all_patches.extend(analyze_foreshadow_gaps(db_nf, pid, chapters))
        
        # 输出汇总
        print(f"\n{'='*60}")
        print(f"  分析完成")
        
        severity_count = defaultdict(int)
        type_count = defaultdict(int)
        for p in all_patches:
            severity_count[p.get('severity', 'info')] += 1
            type_count[p.get('sub_type', p.get('patch_type', 'unknown'))] += 1
        
        print(f"  总问题数: {len(all_patches)}")
        for sev, cnt in sorted(severity_count.items()):
            print(f"    [{sev}] {cnt}")
        print(f"\n  分类明细:")
        for t, cnt in sorted(type_count.items()):
            print(f"    {t}: {cnt}")
        
        # 写入数据库
        if not args.dry_run:
            written = write_patches(db_nf, pid, all_patches, auto_apply=False)
            print(f"\n  已写入 {written} 条 Patch 到 refinement_patches (draft 状态)")
        else:
            print(f"\n  [dry-run] 未写入数据库")
        
        print(f"{'='*60}\n")
        
    finally:
        client.close()


def cmd_status(args):
    """查看Patch状态"""
    client, db_nf, db_novel = connect()
    try:
        novel_name, pid, title = resolve_project(db_nf, db_novel, args.project)
        if not pid:
            print(f"❌ 找不到项目")
            return
        
        # 统计patch状态
        pipeline = [
            {'$match': {'project_id': pid}},
            {'$group': {
                '_id': {'status': '$status', 'type': '$patch_type'},
                'count': {'$sum': 1},
            }},
            {'$sort': {'_id.status': 1}},
        ]
        stats = list(db_nf[PATCH_COLLECTION].aggregate(pipeline))
        
        print(f"\n=== 精修Patch状态: {title} ===")
        total = 0
        for s in stats:
            key = s['_id']
            print(f"  [{key['status']}] {key['type']}: {s['count']} 条")
            total += s['count']
        print(f"  总计: {total} 条\n")
        
        # 查看待处理草案
        drafts = list(db_nf[PATCH_COLLECTION].find(
            {'project_id': pid, 'status': 'draft'}
        ).sort('chapter', 1).limit(20))
        
        if drafts:
            print("=== 待处理草案 (前20条) ===")
            for d in drafts:
                print(f"  ch{d['chapter']} [{d['severity']}] {d['reason'][:60]}")
        
        # 查看已应用
        applied = list(db_nf[PATCH_COLLECTION].find(
            {'project_id': pid, 'status': 'applied'}
        ).sort('applied_at', -1).limit(10))
        
        if applied:
            print(f"\n=== 最近应用 (前10条) ===")
            for d in applied:
                applied_at = d.get('applied_at', '?')
                print(f"  ch{d['chapter']} {d['reason'][:60]}")
        
    finally:
        client.close()


# ═══════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Refinement Branch — 精修分支')
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # analyze
    ap = subparsers.add_parser('analyze', help='分析章节, 生成Patch提案')
    ap.add_argument('project', help='项目名')
    ap.add_argument('--chapters', '-c', help='章节范围: 1-50 或 1,5,20')
    ap.add_argument('--types', '-t', help='精修类型: continuity,lore,prose,pacing,foreshadow,all')
    ap.add_argument('--full', action='store_true', help='全线检查(所有类型)')
    ap.add_argument('--dry-run', action='store_true', help='只输出不写入')
    
    # status
    sp = subparsers.add_parser('status', help='查看Patch状态')
    sp.add_argument('project', help='项目名')
    
    args = parser.parse_args()
    
    if args.command == 'analyze':
        if args.full:
            args.types = 'all'
        cmd_analyze(args)
    elif args.command == 'status':
        cmd_status(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
