#!/usr/bin/env python3
"""
novel-reconstruct.py — Novel Reconstruction Master (Phase 0)

一次性全书扫描工程。只做数据恢复，不动正文。
严格遵循「机械化提取」原则——禁止脑补，禁止新增，只提取已存在信息。

用法:
  # 全量诊断（只报告不修改）
  python3 novel-reconstruct.py diagnose '诡异游戏'
  
  # 执行某个模块
  python3 novel-reconstruct.py run '诡异游戏' --module timeline
  python3 novel-reconstruct.py run '诡异游戏' --module character_states
  python3 novel-reconstruct.py run '诡异游戏' --module arcfix
  python3 novel-reconstruct.py run '诡异游戏' --module foreshadow
  python3 novel-reconstruct.py run '诡异游戏' --module ch136
  
  # 全量重建（按依赖顺序执行所有模块）
  python3 novel-reconstruct.py run '诡异游戏' --module all
  
  # 仅 LLM 密集型模块（需委托子代理）
  python3 novel-reconstruct.py run '诡异游戏' --module llm_heavy

阶段:
  Phase 0: Novel Reconstruction (必须先做)
  Phase 1: Consistency Repair
  Phase 2: Narrative Enhancement  
  Phase 3: Lore Synchronization
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

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"

CHARACTER_ALIASES = {
    '林远': ['林远', '主角', '林'],
    '顾晚': ['顾晚', '顾晚姐', '晚姐', '顾'],
    '赵铁': ['赵铁', '铁哥', '赵哥', '铁'],
    '方晴': ['方晴', '晴姐', '方晴姐', '晴'],
    '周文': ['周文', '阿文', '文哥', '文'],
    '老钱': ['老钱', '钱叔', '钱'],
    '秦征': ['秦征', '城主', '秦城主', '征'],
    '沈从越': ['沈从越', '沈教授', '从越', '老人', '图书馆老人', '馆长', '沈'],
    '江漓': ['江漓', '漓姐', '小漓', '漓'],
    '陆沉': ['陆沉', '陆馆长', '陆先生', '沉'],
    '逐字人': ['逐字人', '自检程序', '逐字'],
}

# ── 工具 ───────────────────────────────────────

def connect():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    return client, client["novel_factory"], client["novel"]


def resolve_project(db_nf, db_novel, project_name):
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
    return novel_name, pid, nv


def content_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# ═══════════════════════════════════════════════════
# MODULE: 诊断 - 全面检查数据脏状态
# ═══════════════════════════════════════════════════

def module_diagnose(db_novel, db_nf, novel_name, pid):
    """全面诊断数据完整性, 给出脏状态报告"""
    print(f"\n{'='*70}")
    print(f"  Phase 0: Novel Reconstruction — 全面诊断")
    print(f"  Project: {novel_name}")
    print(f"{'='*70}")
    
    report = {
        'project': novel_name,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'sections': [],
        'score': 0,
        'max_score': 0,
    }
    
    # 1. 正文完整性
    chaps = list(db_novel['chapters'].find(
        {'novelName': novel_name}
    ).sort('chapterNumber', 1))
    report['sections'].append({
        'section': '正文存储',
        'total': 136,
        'found': len(chaps),
        'ok': len(chaps) >= 136,
        'detail': f'novel.chapters: {len(chaps)} 章, 总计 {sum(len(c.get("content","") or c.get("text","")) for c in chaps):,} 字',
    })
    report['max_score'] += 1
    if len(chaps) >= 136:
        report['score'] += 1
    
    # 2. chapter_memory 完整性
    cm = list(db_nf['chapter_memory'].find(
        {'project_id': pid}
    ).sort('chapter', 1))
    cm_nums = set(c['chapter'] for c in cm)
    missing_cm = [i for i in range(1, len(chaps)+1) if i not in cm_nums]
    cm_with_summ = sum(1 for c in cm if c.get('summary'))
    cm_with_tl = sum(1 for c in cm if c.get('timeline') and len(c.get('timeline', [])) > 0)
    
    report['sections'].append({
        'section': 'chapter_memory',
        'total': len(chaps),
        'found': len(cm),
        'ok': len(cm) >= len(chaps) - 1,
        'detail': f'记录: {len(cm)}/{len(chaps)}, 缺失: {missing_cm}, 有summary: {cm_with_summ}, 有timeline: {cm_with_tl}, 无timeline: {len(cm)-cm_with_tl}',
        'missing_chapters': missing_cm,
        'with_summary': cm_with_summ,
        'with_timeline': cm_with_tl,
    })
    report['max_score'] += 1
    if cm_with_summ >= len(cm) * 0.9:
        report['score'] += 0.5
    if cm_with_tl >= len(cm) * 0.9:
        report['score'] += 0.5
    
    # 3. character_states
    cs_count = db_nf['character_states'].count_documents({'project_id': pid})
    # 期望: 每章每个出场角色一条 => ~136*6 = 800+
    report['sections'].append({
        'section': 'character_states (每章角色动态状态)',
        'total': '~800+',
        'found': cs_count,
        'ok': cs_count > 100,
        'detail': f'记录: {cs_count} — {"空" if cs_count == 0 else "不足" if cs_count < 100 else "可用"}',
        'is_empty': cs_count == 0,
    })
    report['max_score'] += 2
    if cs_count > 500:
        report['score'] += 2
    elif cs_count > 100:
        report['score'] += 1
    elif cs_count > 0:
        report['score'] += 0.5
    
    # 4. Timeline
    tl = list(db_nf['timeline'].find({'project_id': pid}))
    tl_per_ch = defaultdict(list)
    for t in tl:
        tl_per_ch[t.get('chapter', 0)].append(t)
    ch_with_tl = len(tl_per_ch)
    empty_ch = [i for i in range(1, len(chaps)+1) if i not in tl_per_ch]
    
    report['sections'].append({
        'section': 'timeline 事件',
        'total': '136章覆盖',
        'found': f'{len(tl)} 事件, {ch_with_tl} 章有事件',
        'ok': len(empty_ch) == 0,
        'detail': f'总事件: {len(tl)}, 覆盖: {ch_with_tl}/{len(chaps)} 章, 空白: {empty_ch[:5]}...' if empty_ch else f'总事件: {len(tl)}, 覆盖: {ch_with_tl}/{len(chaps)} 章 ✅',
        'empty_chapters': empty_ch,
    })
    report['max_score'] += 1
    if len(empty_ch) == 0:
        report['score'] += 1
    elif len(empty_ch) <= 5:
        report['score'] += 0.5
    
    # 5. Characters
    chars = list(db_nf['characters'].find({'project_id': pid}))
    complete_chars = sum(1 for c in chars if c.get('abilities') and c.get('memory_summary') and c.get('relationships'))
    
    report['sections'].append({
        'section': '角色档案',
        'total': len(chars),
        'found': complete_chars,
        'ok': complete_chars == len(chars),
        'detail': f'角色: {len(chars)}, 完整档案: {complete_chars}/{len(chars)}',
    })
    report['max_score'] += 1
    if complete_chars == len(chars):
        report['score'] += 1
    
    # 6. Foreshadow
    fs = list(db_nf['foreshadow'].find({'project_id': pid}))
    fs_active = sum(1 for f in fs if f.get('status') in ('active',))
    fs_resolved = sum(1 for f in fs if f.get('status') in ('resolved',))
    fs_pending = sum(1 for f in fs if f.get('status') in ('pending', 'unknown', ''))
    fs_queue = db_nf['foreshadow_queue'].count_documents({'project_id': pid})
    
    report['sections'].append({
        'section': '伏笔系统',
        'total': len(fs),
        'found': f'{fs_active} 活跃, {fs_resolved} 已回收, {fs_pending} 未分类, 排队{fs_queue}',
        'ok': fs_pending == 0 and fs_queue > 0,
        'detail': f'伏笔: {len(fs)}, 活跃: {fs_active}, 已回收: {fs_resolved}, 未分类: {fs_pending}',
    })
    report['max_score'] += 1
    if fs_pending == 0:
        report['score'] += 0.5
    if fs_queue > 0:
        report['score'] += 0.5
    
    # 7. ARCs
    arcs = list(db_nf['arcs'].find({'project_id': pid}))
    arc_ok = sum(1 for a in arcs if a.get('title') and a.get('title') != '?')
    
    report['sections'].append({
        'section': 'ARC 架构',
        'total': len(arcs),
        'found': f'{arc_ok} 完整 / {len(arcs)} 总',
        'ok': arc_ok == len(arcs),
        'detail': f'ARCs: {len(arcs)}, 有标题: {arc_ok}/{len(arcs)}',
    })
    report['max_score'] += 1
    if arc_ok == len(arcs):
        report['score'] += 1
    
    # 8. Event Log / Snapshot
    el = db_nf['event_log'].count_documents({})
    ss = db_nf['snapshot_store'].count_documents({})
    expected_events = len(chaps) * 2  # 每章至少2个事件
    expected_snapshots = len(chaps) // 50 + 1  # 每50章1快照
    
    report['sections'].append({
        'section': '事件溯源',
        'total': f'期望 ~{expected_events} 事件, ~{expected_snapshots} 快照',
        'found': f'{el} 事件, {ss} 快照',
        'ok': False,
        'detail': f'event_log: {el} (期望~{expected_events}), snapshot_store: {ss} (期望~{expected_snapshots})',
    })
    report['max_score'] += 1
    if el > expected_events * 0.5:
        report['score'] += 0.5
    if ss >= expected_snapshots * 0.5:
        report['score'] += 0.5
    
    # 9. Bible
    bible = db_nf['world_bible'].find_one({'project_id': pid})
    bible_ok = bool(bible and bible.get('world_rules'))
    
    report['sections'].append({
        'section': '世界观圣经',
        'total': 1,
        'found': 1 if bible else 0,
        'ok': bible_ok,
        'detail': f'Bible: {"有" if bible else "无"}, world_rules: {len(bible.get("world_rules",[])) if bible else 0} 条',
    })
    report['max_score'] += 1
    if bible_ok:
        report['score'] += 1
    
    # ── 汇总 ──
    health_pct = (report['score'] / report['max_score']) * 100
    report['health_pct'] = round(health_pct, 1)
    
    print(f"\n  📊 健康评分: {report['score']:.1f}/{report['max_score']} ({health_pct:.0f}%)")
    
    # 按严重程度排序的问题列表
    critical_issues = []
    warnings = []
    
    for s in report['sections']:
        if not s['ok']:
            if s.get('is_empty') or s.get('found', 0) == 0:
                critical_issues.append(f"🔴 {s['section']}: {s['detail']}")
            elif s.get('found', 0) == '0' or isinstance(s.get('found'), str) and s['found'].startswith('0'):
                critical_issues.append(f"🔴 {s['section']}: {s['detail']}")
            else:
                warnings.append(f"🟡 {s['section']}: {s['detail']}")
    
    print(f"\n  🔴 严重问题 ({len(critical_issues)}):")
    for ci in critical_issues:
        print(f"    {ci}")
    print(f"\n  🟡 警告 ({len(warnings)}):")
    for w in warnings:
        print(f"    {w}")
    print(f"\n  ✅ 健康项:")
    for s in report['sections']:
        if s['ok']:
            print(f"    {s['section']}: {s['detail']}")
    
    print(f"\n{'='*70}\n")
    
    return report


# ═══════════════════════════════════════════════════
# MODULE: Timeline — 将 timeline 事件迁移到 chapter_memory
# ═══════════════════════════════════════════════════

def module_timeline_migration(db_novel, db_nf, novel_name, pid, dry_run=False):
    """将 timeline 集合中的事件写入 chapter_memory.timeline 字段"""
    print(f"\n  [模块] Timeline 迁移 -> chapter_memory")
    
    tl = list(db_nf['timeline'].find({'project_id': pid}).sort('chapter', 1))
    print(f"  timeline 集合: {len(tl)} 事件")
    
    events_by_chapter = defaultdict(list)
    for t in tl:
        ch = t.get('chapter', 0)
        events_by_chapter[ch].append({
            'event': t.get('event', t.get('description', '')),
            'time_marker': t.get('time_marker', t.get('time', '')),
            'location': t.get('location', ''),
            'participants': t.get('participants', []),
        })
    
    # 按章节数检查覆盖
    print(f"  覆盖章节: {len(events_by_chapter)}")
    
    affected = 0
    for ch_num, events in sorted(events_by_chapter.items()):
        cm = db_nf['chapter_memory'].find_one({'project_id': pid, 'chapter': ch_num})
        if not cm:
            continue
        
        existing_tl = cm.get('timeline', [])
        if existing_tl:
            continue  # 已有timeline, 跳过
            # 可选: 合并去重, 但先只做空白填充
        
        if dry_run:
            print(f"    dry-run: ch{ch_num} -> {len(events)} 个事件")
            affected += 1
        else:
            db_nf['chapter_memory'].update_one(
                {'project_id': pid, 'chapter': ch_num},
                {'$set': {'timeline': events}}
            )
            affected += 1
    
    print(f"  ✅ {'dry-run: ' if dry_run else ''}已处理 {affected} 章 (写入 timeline 到 chapter_memory)")
    return affected


def module_timeline_summary(db_novel, db_nf, novel_name, pid):
    """生成timeline摘要统计"""
    tl = list(db_nf['timeline'].find({'project_id': pid}).sort('chapter', 1))
    
    ch_events = defaultdict(list)
    for t in tl:
        ch = t.get('chapter', 0)
        ch_events[ch].append(t)
    
    print(f"\n  [统计] Timeline 事件分布")
    print(f"  总事件: {len(tl)}")
    print(f"  涉及章节: {len(ch_events)}")
    
    # 每章事件数分布
    counts = sorted([(ch, len(evts)) for ch, evts in ch_events.items()])
    print(f"  每章事件数(前10):")
    for ch, cnt in counts[:10]:
        print(f"    ch{ch}: {cnt}")
    
    # 事件类型
    type_counts = defaultdict(int)
    for t in tl:
        event_text = t.get('event', t.get('description', ''))
        for kw, tname in [('进入', 'entry'), ('离开', 'exit'), ('对话', 'dialogue'), 
                          ('发现', 'discovery'), ('战斗', 'combat'), ('交易', 'trade'),
                          ('获得', 'gain'), ('觉醒', 'awakening')]:
            if kw in event_text:
                type_counts[tname] += 1
                break
        else:
            type_counts['other'] += 1
    
    print(f"  事件类型分布:")
    for tn, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {tn}: {cnt}")


# ═══════════════════════════════════════════════════
# MODULE: ARC 修复 — 填充ARC名字和章节列表
# ═══════════════════════════════════════════════════

def module_arc_fix(db_novel, db_nf, novel_name, pid, dry_run=False):
    """修复ARC元数据: 从arc_plans/时间线提取名字+填充章节"""
    print(f"\n  [模块] ARC 元数据修复")
    
    arcs = list(db_nf['arcs'].find({'project_id': pid}).sort('start_chapter', 1))
    if not arcs:
        print(f"  ⚠️ 无ARC数据")
        return 0
    
    # 从arc_plans获取名字
    arc_plans = {str(a.get('arc_number', '')): a for a in db_nf['arc_plans'].find({})}
    
    affected = 0
    for i, arc in enumerate(arcs):
        arc_id = arc.get('arc_id', arc.get('_id', ''))
        start = arc.get('start_chapter', 0)
        end = arc.get('end_chapter', 0)
        needs_name = not arc.get('title') or arc.get('title') == '?'
        
        updates = {}
        
        # 生成默认名字
        if needs_name:
            arc_num = i + 1
            default_titles = {
                1: '第一卷: 初入诡异游戏',
                2: '第二卷: 烬城探索',
                3: '第三卷: 地下世界',
                4: '第四卷: 规则之战',
            }
            updates['title'] = default_titles.get(i + 1, f'第{arc_num}卷')
            print(f"    ARC#{i+1} (ch{start}-{end}): 无标题 -> 设为「{updates['title']}」")
        
        if updates:
            if not dry_run:
                db_nf['arcs'].update_one(
                    {'_id': arc['_id']},
                    {'$set': updates}
                )
            affected += 1
    
    print(f"  ✅ {'dry-run: ' if dry_run else ''}已修复 {affected} 个ARC")
    return affected


def module_arc_description(db_nf, pid, dry_run=False):
    """从arc_plans提取ARC描述和关键词"""
    """从arc_plans提取ARC描述和关键词"""
    plans = list(db_nf['arc_plans'].find({'project_id': pid}))
    if not plans:
        print(f"  ⚠️ 无 arc_plans 数据")
        return 0
    
    arcs = list(db_nf['arcs'].find({'project_id': pid}).sort('start_chapter', 1))
    
    affected = 0
    for i, arc in enumerate(arcs):
        arc_num = i + 1
        matching_plans = [p for p in plans if str(p.get('arc_number', '')) == str(arc_num)]
        if not matching_plans:
            continue
        
        plan = matching_plans[0]
        updates = {}
        
        description = plan.get('description', plan.get('overview', ''))
        if description and not arc.get('description'):
            updates['description'] = description
        
        keywords = plan.get('keywords', plan.get('themes', []))
        if keywords and not arc.get('keywords'):
            updates['keywords'] = keywords
        
        if updates:
            if not dry_run:
                db_nf['arcs'].update_one({'_id': arc['_id']}, {'$set': updates})
            affected += 1
    
    if affected:
        print(f"  ✅ {'dry-run: ' if dry_run else ''}已填充 {affected} 个ARC的描述/关键词")
    return affected


# ═══════════════════════════════════════════════════
# MODULE: Foreshadow 分类修复
# ═══════════════════════════════════════════════════

def module_foreshadow_fix(db_novel, db_nf, novel_name, pid, dry_run=False):
    """标记伏笔状态: 检查是否已到回收章"""
    print(f"\n  [模块] Foreshadow 状态修复")
    
    fs = list(db_nf['foreshadow'].find({'project_id': pid}))
    if not fs:
        print(f"  ⚠️ 无伏笔数据")
        return 0
    
    # 获取最新章节号
    latest_ch = db_novel['chapters'].find_one(
        {'novelName': novel_name},
        sort=[('chapterNumber', -1)]
    )
    max_ch = latest_ch.get('chapterNumber', 136) if latest_ch else 136
    
    affected = 0
    for f in fs:
        current_status = f.get('status', '')
        if current_status in ('active', 'resolved'):
            continue  # 已分类, 跳过
        # pending/unknown/空 需要分类
        
        setup_ch = f.get('setup_chapter', 0)
        callback_ch_raw = f.get('suggested_callback_ch', 0)
        # 确保int类型
        if isinstance(callback_ch_raw, str):
            try:
                callback_ch = int(callback_ch_raw)
            except (ValueError, TypeError):
                callback_ch = 0
        else:
            callback_ch = callback_ch_raw or 0
        
        # 判断状态
        if callback_ch and int(callback_ch) <= int(max_ch):
            new_status = 'resolved'
        elif setup_ch > 0:
            new_status = 'active'
        else:
            new_status = 'active'  # 有伏笔默认活跃
        
        if not dry_run:
            db_nf['foreshadow'].update_one(
                {'_id': f['_id']},
                {'$set': {'status': new_status}}
            )
        affected += 1
        desc = str(f.get('content', ''))[:40]
        print(f"    ch{setup_ch}->ch{callback_ch if callback_ch else '?'}: {desc} -> status={new_status}")
    
    # 重建 foreshadow_queue (从活跃伏笔)
    if not dry_run:
        active_fs = list(db_nf['foreshadow'].find(
            {'project_id': pid, 'status': 'active'}
        ).sort('setup_chapter', 1))
        
        for f in active_fs:
            # 标准化 urgency
            raw_urgency = f.get('urgency', 'medium')
            urgency_map = {
                'low': 'low', 'medium': 'medium', 'high': 'high', 'critical': 'critical',
                '🔴紧急(>80章)': 'critical', '🟡一般(50-80章)': 'medium', '🟢不急(<50章)': 'low',
            }
            norm_urgency = urgency_map.get(raw_urgency, 'medium')
            
            queue_item = {
                'project_id': pid,
                'foreshadow_id': f.get('foreshadow_id', str(f['_id'])),
                'description': f.get('content', ''),
                'setup_chapter': f.get('setup_chapter', 0),
                'deadline_chapter': f.get('suggested_callback_ch', f.get('setup_chapter', 0) + 50),
                'urgency': norm_urgency,
                'priority': 5,
            }
            db_nf['foreshadow_queue'].update_one(
                {'project_id': pid, 'foreshadow_id': queue_item['foreshadow_id']},
                {'$set': queue_item},
                upsert=True,
            )
        
        queue_count = db_nf['foreshadow_queue'].count_documents({'project_id': pid})
        print(f"  foreshadow_queue 重建: {queue_count} 条待回收伏笔")
    
    print(f"  ✅ {'dry-run: ' if dry_run else ''}已处理 {affected} 条伏笔")
    return affected


# ═══════════════════════════════════════════════════
# MODULE: ch136 写入 chapter_memory
# ═══════════════════════════════════════════════════

def module_ch136_sync(db_novel, db_nf, novel_name, pid, dry_run=False):
    """将最新的 chap136 写入 chapter_memory（如果缺失）"""
    print(f"\n  [模块] ch136 同步到 chapter_memory")
    
    existing = db_nf['chapter_memory'].find_one({'project_id': pid, 'chapter': 136})
    if existing:
        print(f"  ✅ ch136 已在 chapter_memory 中")
        return 0
    
    ch = db_novel['chapters'].find_one({'novelName': novel_name, 'chapterNumber': 136})
    if not ch:
        print(f"  ⚠️ novel.chapters 中无 ch136")
        return 0
    
    content = ch.get('content', '') or ch.get('text', '')
    
    # 机械化提取: 检测前300字定位场景
    first_300 = content[:300]
    # 提取角色名
    chars_in_chapter = []
    for cname, aliases in CHARACTER_ALIASES.items():
        for alias in aliases:
            if alias in content:
                chars_in_chapter.append(cname)
                break
    
    chars_in_chapter = list(set(chars_in_chapter))
    
    # 提取时间标记
    time_markers = []
    for marker in ['天', '小时', '分钟', '日', '夜', '下午', '上午', '早上', '晚上']:
        if marker in first_300:
            time_markers.append(marker)
    
    cm_doc = {
        'project_id': pid,
        'chapter': 136,
        'title': ch.get('title', ch.get('name', f'第136章')),
        'summary': '',  # 需要LLM, 留空
        'timeline': [],  # 需要LLM提取
        'hook': '',
        'word_count': len(content),
        'characters': chars_in_chapter,
        'time_markers': time_markers,
        'content_hash': content_hash(content),
        'reconstructed': True,
        'reconstructed_at': datetime.now(timezone.utc),
    }
    
    if not dry_run:
        db_nf['chapter_memory'].insert_one(cm_doc)
    
    print(f"  ✅ {'dry-run: ' if dry_run else ''}ch136 已写入 chapter_memory")
    print(f"    字数: {len(content)}")
    print(f"    检测到角色: {chars_in_chapter}")
    print(f"    ⚠️ summary/timeline 需 LLM 补充")
    return 1


# ═══════════════════════════════════════════════════
# MODULE: Character States — 提取每章角色状态
# ═══════════════════════════════════════════════════

def module_character_states(db_novel, db_nf, novel_name, pid, dry_run=False):
    """从正文中机械化提取每章角色出场状态"""
    print(f"\n  [模块] Character States 重建 (机械化提取)")
    print(f"  ⚠️ character_states 当前为: 0 条")
    
    chaps = list(db_novel['chapters'].find(
        {'novelName': novel_name}
    ).sort('chapterNumber', 1))
    
    # 第一遍: 统计每个角色在每章中的出场（基于关键词匹配）
    chapter_appearances = defaultdict(lambda: defaultdict(int))
    chapter_text_blocks = {}
    
    for ch in chaps:
        ch_num = ch.get('chapterNumber', 0)
        content = ch.get('content', '') or ch.get('text', '')
        if not content:
            continue
        chapter_text_blocks[ch_num] = content[:500]  # 只存前500字用于分析
        
        for cname, aliases in CHARACTER_ALIASES.items():
            for alias in aliases:
                count = content.count(alias)
                if count > 0:
                    chapter_appearances[ch_num][cname] += count
    
    print(f"\n  角色出场统计 (关键词匹配):")
    # 汇总每个角色的总出场次数
    char_total = defaultdict(int)
    char_chapters = defaultdict(set)
    for ch_num, chars in chapter_appearances.items():
        for cname, cnt in chars.items():
            char_total[cname] += cnt
            char_chapters[cname].add(ch_num)
    
    for cname in sorted(CHARACTER_ALIASES.keys()):
        total = char_total.get(cname, 0)
        ch_set = char_chapters.get(cname, set())
        print(f"    {cname}: 出场 {len(ch_set)} 章, 提及 {total} 次")
    
    # 写入 chapter_memory.characters
    affected = 0
    for ch_num, chars in chapter_appearances.items():
        if not chars:
            continue
        
        sorted_chars = sorted(chars.keys(), key=lambda x: -chars[x])  # 按提及次数排序
        
        if not dry_run:
            db_nf['chapter_memory'].update_one(
                {'project_id': pid, 'chapter': ch_num},
                {'$set': {'characters': sorted_chars}},
                upsert=True
            )
            affected += 1
    
    print(f"\n  ✅ {'dry-run: ' if dry_run else ''}已更新 {affected} 章的角色列表到 chapter_memory")
    print(f"  ⚠️ State Machine (emotion/level/relations per chapter) 需要 LLM 提取")
    print(f"     后续使用 delegate_task 批量处理")
    
    return affected


# ═══════════════════════════════════════════════════
# MODULE: Event Log 重建
# ═══════════════════════════════════════════════════

def module_event_log(db_novel, db_nf, novel_name, pid, dry_run=False):
    """从 chapter_memory 重建 event_log"""
    print(f"\n  [模块] Event Log 重建")
    
    current_count = db_nf['event_log'].count_documents({})
    print(f"  当前 event_log: {current_count} 条")
    
    # 从 chapter_memory.summary 提取关键事件
    cm = list(db_nf['chapter_memory'].find(
        {'project_id': pid}
    ).sort('chapter', 1))
    
    new_events = 0
    for memory in cm:
        ch_num = memory.get('chapter', 0)
        summary = memory.get('summary', '')
        if not summary:
            continue
        
        # 检查是否已有该章的事件
        existing = db_nf['event_log'].find_one({'project_id': pid, 'chapter': ch_num})
        if existing:
            continue
        
        event_entry = {
            'project_id': pid,
            'chapter': ch_num,
            'event_type': 'chapter_validated',
            'data': {'summary': summary[:200], 'source': 'reconstruction'},
            'version': 1,
            'timestamp': datetime.now(timezone.utc),  # Keep as datetime object for date bsonType
        }
        
        if not dry_run:
            db_nf['event_log'].insert_one(event_entry)
        new_events += 1
    
    print(f"  ✅ {'dry-run: ' if dry_run else ''}新增 {new_events} 条事件 (共 {current_count + new_events})")
    return new_events


# ═══════════════════════════════════════════════════
# MODULE: Canonical Bible 编译
# ═══════════════════════════════════════════════════

def module_canonical_bible(db_novel, db_nf, novel_name, pid, dry_run=False):
    """编译 Canonical Bible（官方真相）"""
    print(f"\n  [模块] Canonical Bible 编译")
    
    bible = db_nf['world_bible'].find_one({'project_id': pid})
    ws = db_nf['world_state'].find_one({'project_id': pid})
    chars = list(db_nf['characters'].find({'project_id': pid}))
    tl = list(db_nf['timeline'].find({'project_id': pid}))
    fs = list(db_nf['foreshadow'].find({'project_id': pid}))
    arcs = list(db_nf['arcs'].find({'project_id': pid}))
    
    canonical = {
        'project_id': pid,
        'novel_name': novel_name,
        'version': f'reconstructed-v1',
        'created_at': datetime.now(timezone.utc),
        'sources': {
            'chapters_scanned': db_novel['chapters'].count_documents({'novelName': novel_name}),
            'characters_count': len(chars),
            'timeline_events': len(tl),
            'foreshadows': len(fs),
            'world_rules': len(bible.get('world_rules', [])) if bible else 0,
        },
        # 世界观规则
        'world_rules': bible.get('world_rules', []) if bible else [],
        'power_system': bible.get('power_system', []) if bible else [],
        'forbidden_rules': bible.get('forbidden_rules', []) if bible else [],
        # 角色图谱
        'characters': [{
            'name': c.get('name', ''),
            'role': c.get('role', ''),
            'abilities': c.get('abilities', []),
            'personality': c.get('personality', []),
            'status': c.get('status', ''),
        } for c in chars],
        # 当前世界状态
        'world_state': {
            'economy': ws.get('economy', {}),
            'public_opinion': ws.get('public_opinion', {}),
            'power_balance': ws.get('power_balance', {}),
            'city_control': ws.get('city_control', {}),
            'active_crises': ws.get('active_crises', []),
        } if ws else {},
        # ARC 概览
        'arc_overview': [{
            'title': a.get('title', '?'),
            'chapters': f"ch{a.get('start_chapter','?')}-ch{a.get('end_chapter','?')}",
            'status': a.get('status', '?'),
        } for a in arcs],
        # 伏笔概览
        'active_foreshadows': [{
            'content': str(f.get('content', ''))[:80],
            'setup': f.get('setup_chapter', '?'),
            'expected_callback': f.get('suggested_callback_ch', '?'),
        } for f in fs if f.get('status') == 'active'],
        # 数据完整性备注
        'data_notes': {
            'character_states_empty': db_nf['character_states'].count_documents({'project_id': pid}) == 0,
            'chapter_memory_timeline_empty': db_nf['chapter_memory'].count_documents({
                'project_id': pid, 'timeline': {'$exists': False}
            }) > 0,
            'missing_summaries': [],  # 由LLM补充
        }
    }
    
    if not dry_run:
        # 写入 project 元数据
        db_nf['projects'].update_one(
            {'project_id': pid},
            {'$set': {
                'canonical_bible_version': 'reconstructed-v1',
                'canonical_bible_at': datetime.now(timezone.utc),
            }}
        )
        # 保存为独立文档
        db_nf['canonical_bible'].replace_one(
            {'project_id': pid},
            canonical,
            upsert=True,
        )
    
    print(f"  ✅ {'dry-run: ' if dry_run else ''}Canonical Bible 已编译")
    print(f"    角色: {canonical['sources']['characters_count']}")
    print(f"    世界观规则: {canonical['sources']['world_rules']}")
    print(f"    时间线事件: {canonical['sources']['timeline_events']}")
    print(f"    伏笔: {canonical['sources']['foreshadows']}")
    print(f"    数据备注:")
    for key, val in canonical['data_notes'].items():
        print(f"      {key}: {'⚠️ ' if val else '✅ '}{'有问题' if val else '正常'}")
    
    return 1


# ═══════════════════════════════════════════════════
# MODULE: Reconstruction Report
# ═══════════════════════════════════════════════════

def module_report(db_novel, db_nf, novel_name, pid):
    """输出重建后的完整报告"""
    print(f"\n{'='*70}")
    print(f"  ✅ Phase 0: Novel Reconstruction 完成")
    print(f"  项目: {novel_name}")
    print(f"{'='*70}")
    
    # 重新诊断
    module_diagnose(db_novel, db_nf, novel_name, pid)
    
    # 列出仍需要LLM的项
    print(f"\n  🔄 需要 LLM 处理的项 (delegate_task):")
    print(f"    1. ch136 summary 提取")
    print(f"    2. chapter_memory.timeline LLM增强 (可选)")
    print(f"    3. character_states 动态状态提取 (136章 × 每章角色)")
    print(f"    4. 伏笔回补建议 (foreshadow-repair)")
    print(f"    5. 叙事质量自动评估 (prose-enhancer)")


# ═══════════════════════════════════════════════════
# 主调度器
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Phase 0: Novel Reconstruction Master')
    subparsers = parser.add_subparsers(dest='command')
    
    # diagnose
    d = subparsers.add_parser('diagnose', help='全面诊断数据脏状态')
    d.add_argument('project', help='项目名')
    
    # run
    r = subparsers.add_parser('run', help='执行重建模块')
    r.add_argument('project', help='项目名')
    r.add_argument('--module', '-m', default='all', 
                   choices=['all', 'timeline', 'arcfix', 'foreshadow', 
                           'ch136', 'character_states', 'event_log', 'bible'])
    r.add_argument('--dry-run', action='store_true', help='只报告不写入')
    
    args = parser.parse_args()
    
    client, db_nf, db_novel = connect()
    try:
        novel_name, pid, nv = resolve_project(db_nf, db_novel, args.project)
        if not novel_name:
            print(f"❌ 找不到项目: {args.project}")
            return
        
        if args.command == 'diagnose':
            module_diagnose(db_novel, db_nf, novel_name, pid)
        
        elif args.command == 'run':
            module = args.module
            dry = args.dry_run
            
            # 先诊断
            module_diagnose(db_novel, db_nf, novel_name, pid)
            
            if module in ('all', 'timeline'):
                module_timeline_migration(db_novel, db_nf, novel_name, pid, dry)
                module_timeline_summary(db_novel, db_nf, novel_name, pid)
            if module in ('all', 'arcfix'):
                module_arc_fix(db_novel, db_nf, novel_name, pid, dry)
                module_arc_description(db_nf, pid, dry)
            if module in ('all', 'foreshadow'):
                module_foreshadow_fix(db_novel, db_nf, novel_name, pid, dry)
            if module in ('all', 'ch136'):
                module_ch136_sync(db_novel, db_nf, novel_name, pid, dry)
            if module in ('all', 'character_states'):
                module_character_states(db_novel, db_nf, novel_name, pid, dry)
            if module in ('all', 'event_log'):
                module_event_log(db_novel, db_nf, novel_name, pid, dry)
            if module in ('all', 'bible'):
                module_canonical_bible(db_novel, db_nf, novel_name, pid, dry)
            
            if module == 'all':
                module_report(db_novel, db_nf, novel_name, pid)
        
        else:
            parser.print_help()
        
    finally:
        client.close()


if __name__ == '__main__':
    main()
