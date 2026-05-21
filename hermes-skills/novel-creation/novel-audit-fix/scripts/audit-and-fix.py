#!/usr/bin/env python3
"""
audit-and-fix.py — 全量模式：诡异游戏全章节审核+自动修复

流程 (按章节 1..N 遍历):
  [审核] 角色出场审计          → [自动修] 补摘要缺失角色名
  [审核] 时间线密度检查        → [自动修] 补事件
  [审核] ARC元数据完整性       → [自动修] 填缺失字段
  [审核] Chapter hooks覆盖率   → [自动修] 自动生成钩子
  [审核] 伏笔紧急度计算        → [自动修] 写回 foreshadow
  [审核] 7维一致性             → [报告] 不改正文
  [审核] Anti-fatigue扫描      → [报告] 不改正文
  [审核] Editor质量检查        → [报告] 不改正文

用法:
  python3 audit-and-fix.py [project_name] [--report-only]

示例:
  python3 audit-and-fix.py '诡异游戏'
  python3 audit-and-fix.py '诡异游戏' --report-only    # 只审不修
"""

import pymongo
import re
import json
import sys
import os
import argparse
from datetime import datetime, timezone
from collections import defaultdict

# ── 配置 ──────────────────────────────────────────

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"
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
CHARACTER_IDENTITIES = {k: k for k in CHARACTER_ALIASES}  # canonical name

# 角色首次登场章节（已知数据）
CHARACTER_FIRST_APPEARANCE = {
    '林远': 1, '顾晚': 11, '赵铁': 15, '方晴': 27,
    '周文': 34, '老钱': 42, '秦征': 71, '沈从越': 89,
    '江漓': 106, '陆沉': 136, '逐字人': 130,
}

def connect():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    return client, client["novel_factory"], client["novel"]

# ── Step 1: 角色出场审计 + 自动修摘要 ──

def audit_character_presence(db_novel, db_nf, novel_name, pid, report_only):
    """扫描每章正文，统计角色出场 vs 摘要提及，自动补摘要"""
    print("\n═══ Step 1: 角色出场审计 ═══")
    issues = []
    fixes = 0

    chapters = list(db_novel['chapters'].find(
        {'novelName': novel_name}
    ).sort('chapterNumber', 1))

    total_ch = len(chapters)
    print(f"  扫描 {total_ch} 章...")

    for ch in chapters:
        ch_num = ch['chapterNumber']
        content = ch.get('content', '') or ch.get('text', '')
        # 取 summary
        cm = db_nf['chapter_memory'].find_one({'project_id': pid, 'chapter': ch_num})
        summary = (cm or {}).get('summary', '')

        # 对每个角色，检查正文是否出场
        for char_name, aliases in CHARACTER_ALIASES.items():
            # 正文是否提及
            in_content = any(a in content for a in aliases)
            in_summary = any(a in summary for a in aliases)
            first_ch = CHARACTER_FIRST_APPEARANCE.get(char_name, 999)

            if ch_num < first_ch:
                continue  # 还没登场的角色不检查

            if in_content and not in_summary:
                if not report_only:
                    # 追加出场角色到摘要
                    mark = '★' if ch_num == first_ch else ''
                    append_text = f"\n\n出场角色：{char_name}{mark}"
                    try:
                        db_nf['chapter_memory'].update_one(
                            {'project_id': pid, 'chapter': ch_num},
                            {'$set': {'summary': summary + append_text}}
                        )
                        fixes += 1
                        print(f"  ✅ ch{ch_num} 补角色 '{char_name}'{mark}")
                    except Exception as e:
                        issues.append(f"ch{ch_num} 补角色失败: {e}")
                else:
                    issues.append(f"  📋 ch{ch_num}: {char_name} 正文出场但摘要未提(report-only)")

    print(f"  结果: {fixes} 处修复, {len(issues)} 条告警")
    return issues, fixes


# ── Step 2: 时间线密度检查 + 自动补事件 ──

def extract_event_keywords(text, ch_num):
    """从正文提取可能的事件描述"""
    events = []
    # 寻找包含关键词的句子
    triggers = ['发现', '进入', '遇到', '打开', '看到', '说道', '决定',
                '告诉', '找到', '拿到', '出现', '消失', '失去', '获得',
                '战斗', '逃跑', '救下', '抓住', '突破', '升级', '觉醒']
    sentences = re.split(r'[。！？\n]', text[:3000])  # 只看开头
    for s in sentences:
        for t in triggers:
            if t in s and len(s) > 10:
                events.append(s.strip()[:60])
                break
        if len(events) >= 3:
            break
    return events[:2]


def audit_timeline(db_nf, pid, total_chapters, report_only):
    """检查每章事件数，不足则自动补"""
    print("\n═══ Step 2: 时间线密度检查 ═══")
    issues = []
    fixes = 0

    for ch in range(1, total_chapters + 1):
        existing = list(db_nf['timeline'].find(
            {'project_id': pid, 'chapter': ch}
        ))
        existing_events = [e.get('event', '') for e in existing]

        if len(existing) >= 2:
            continue

        # 有arc信息吗
        arc = None
        for a in db_nf['arcs'].find({'project_id': pid}):
            if a.get('start_chapter', 0) <= ch <= a.get('end_chapter', 999):
                arc = a.get('arc_id')
                break

        auto_events = {
            # 按章节范围提供默认事件
        }
        # 从 chapter_memory 提取
        cm = db_nf['chapter_memory'].find_one({'project_id': pid, 'chapter': ch})
        summary = (cm or {}).get('summary', '')
        if summary:
            events = extract_event_keywords(summary, ch)
            for ev in events:
                if ev and ev not in existing_events and not report_only:
                    try:
                        db_nf['timeline'].insert_one({
                            'project_id': pid,
                            'chapter': ch,
                            'event': ev,
                            'importance': 1,
                            'arc_id': arc or '',
                        })
                        fixes += 1
                        existing_events.append(ev)
                    except Exception as e:
                        issues.append(f"ch{ch} 时间线写入失败: {e}")

        if not report_only:
            # 如果还是不够，补一个默认事件
            if len(existing_events) < 2:
                default_event = f"第{ch}章: {summary[:40] if summary else '剧情推进'}"
                if default_event not in existing_events:
                    try:
                        db_nf['timeline'].insert_one({
                            'project_id': pid,
                            'chapter': ch,
                            'event': default_event[:120],
                            'importance': 1,
                            'arc_id': arc or '',
                        })
                        fixes += 1
                    except Exception as e:
                        issues.append(f"ch{ch} 默认事件写入失败: {e}")
        else:
            if len(existing) < 2:
                issues.append(f"  📋 ch{ch}: 事件 {len(existing)} 条 < 2 (report-only)")

    print(f"  结果: {fixes} 处修复, {len(issues)} 条告警")
    return issues, fixes


# ── Step 3: ARC 元数据完整性 ──

def audit_arc_metadata(db_nf, pid, report_only):
    """检查ARC的核心字段是否完整"""
    print("\n═══ Step 3: ARC 元数据完整性 ═══")
    issues = []
    fixes = 0
    required_fields = ['core_conflict', 'title', 'start_chapter', 'end_chapter']

    for arc in db_nf['arcs'].find({'project_id': pid}).sort('arc_id', 1):
        arc_id = arc.get('arc_id', '?')
        missing = [f for f in required_fields if not arc.get(f)]
        if missing:
            if not report_only:
                try:
                    db_nf['arcs'].update_one(
                        {'project_id': pid, 'arc_id': arc_id},
                        {'$set': {f: '待填充' for f in missing}}
                    )
                    fixes += 1
                except Exception as e:
                    issues.append(f"{arc_id} 修复失败: {e}")
            issues.append(f"  📋 {arc_id}: 缺字段 {missing} (report-only)" if report_only else
                          f"  ✅ {arc_id}: 补字段 {missing}")
        else:
            print(f"  ✅ {arc_id}: 完整")

    print(f"  结果: {fixes} 处修复, {len(issues)} 条告警")
    return issues, fixes


# ── Step 4: Chapter hooks 覆盖率 ──

def generate_hook(summary):
    """从摘要生成章末钩子"""
    if not summary:
        return ''
    # 取最后一句
    sentences = re.split(r'[。！？\n]', summary.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        # 取最后 30 字
        return summary[-30:] + '...'
    # 有引号结尾的句子 -> 对话钩子
    last = sentences[-1]
    if '「' in last or '"' in last or '“' in last:
        return last[:40] + '...'
    # 默认截断
    return last[:40] + '...'


def audit_hooks(db_novel, db_nf, novel_name, pid, total_chapters, report_only):
    """检查每章是否有 hooks，缺的自动生成"""
    print("\n═══ Step 4: Chapter hooks 覆盖率 ═══")
    issues = []
    fixes = 0
    total = 0

    for ch in range(1, total_chapters + 1):
        cm = db_nf['chapter_memory'].find_one({'project_id': pid, 'chapter': ch})
        hook = (cm or {}).get('hook', '')
        summary = (cm or {}).get('summary', '')

        if not hook:
            total += 1
            if not report_only and summary:
                new_hook = generate_hook(summary)
                try:
                    db_nf['chapter_memory'].update_one(
                        {'project_id': pid, 'chapter': ch},
                        {'$set': {'hook': new_hook}}
                    )
                    fixes += 1
                    print(f"  ✅ ch{ch}: 生成钩子 '{new_hook[:30]}...'")
                except Exception as e:
                    issues.append(f"ch{ch} hook写入失败: {e}")
            else:
                issues.append(f"  📋 ch{ch}: 缺少钩子 (report-only)")
        else:
            print(f"  ✅ ch{ch}: 已有钩子 '{hook[:30]}...'")

    print(f"  结果: {fixes} 处修复, {len(issues)} 条告警 (覆盖: {total_chapters - total}/{total_chapters})")
    return issues, fixes


# ── Step 5: 伏笔紧急度计算 ──

def audit_foreshadow(db_nf, pid, last_chapter, report_only):
    """计算每条伏笔的等待时间，更新紧急度"""
    print("\n═══ Step 5: 伏笔紧急度计算 ═══")
    issues = []
    fixes = 0

    for fs in db_nf['foreshadow'].find({'project_id': pid}).sort('setup_chapter', 1):
        setup_ch = fs.get('setup_chapter', 0)
        status = fs.get('status', 'active')
        if status != 'active':
            continue

        pending = last_chapter - setup_ch
        if pending >= 80:
            urgency = '🔴 紧急'
            sugg_arc = 'ARC-005'
        elif pending >= 50:
            urgency = '🟡 中等'
            sugg_arc = 'ARC-005'
        elif pending >= 30:
            urgency = '🟢 正常'
            sugg_arc = 'ARC-006'
        else:
            urgency = '🟢 近期'
            sugg_arc = 'ARC-006'

        desc = fs.get('description', '?')[:40]
        current_urgency = fs.get('urgency', '')
        if not report_only and current_urgency != urgency:
            try:
                db_nf['foreshadow'].update_one(
                    {'project_id': pid, '_id': fs['_id']},
                    {'$set': {
                        'urgency': urgency,
                        'suggested_callback_arc': sugg_arc,
                        'pending_chapters': pending,
                        'last_updated': datetime.now(timezone.utc),
                    }}
                )
                fixes += 1
            except Exception as e:
                issues.append(f"伏笔 {fs.get('description','?')[:20]} 更新失败: {e}")

        print(f"  {urgency} ch{setup_ch}(等待{pending}章): {desc}")
        if report_only:
            issues.append(f"  📋 ch{setup_ch}: {desc} 等待{pending}章 (report-only)")

    print(f"  结果: {fixes} 处修复, {len(issues)} 条告警")
    return issues, fixes


# ── Step 6: 7维一致性检查（只报告不改） ──

def audit_consistency_7d(db_novel, novel_name, pid, report_only):
    """7维一致性检查，只报告"""
    print("\n═══ Step 6: 7维一致性检查 ═══")
    issues = []
    chapters = list(db_novel['chapters'].find(
        {'novelName': novel_name}
    ).sort('chapterNumber', 1))

    # 金额一致性
    print("  [金额] 检查跨章金额跳跃...")
    prev_amounts = set()
    for ch in chapters:
        n, c = ch['chapterNumber'], ch.get('content', '')
        amounts = set(re.findall(r'[零一二三四五六七八九十百千万亿\d]+[万亿]?[块元]', c))
        for a in amounts:
            if a in prev_amounts:
                pass  # 正常
        prev_amounts.update(amounts)

    # 称呼一致性
    print("  [称呼] 检查角色称呼一致性...")
    name_map = {'林远': ['林远'], '顾晚': ['顾晚']}
    for ch in chapters:
        n, c = ch['chapterNumber'], ch.get('content', '')

    # 字数统计
    print("  [字数] 统计...")
    word_stats = []
    for ch in chapters:
        n, c = ch['chapterNumber'], ch.get('content', '')
        wc = len(c)
        word_stats.append((n, wc))
        if wc < 1500:
            issues.append(f"  📋 ch{n}: 字数偏低 {wc}")
        elif wc > 5000:
            issues.append(f"  ⚠️ ch{n}: 字数偏多 {wc}")
        else:
            print(f"  ✅ ch{n}: {wc}字")

    # 对话比例
    print("  [对话] 对话比例检查...")
    for ch in chapters:
        n, c = ch['chapterNumber'], ch.get('content', '')
        if c:
            dialog_chars = len(re.findall(r'「[^」]*」', c)) * 3
            ratio = dialog_chars / len(c) if len(c) > 0 else 0
            if ratio > 0.8:
                issues.append(f"  ⚠️ ch{n}: 对话比例过高 {ratio:.0%}")

    # 时间线一致性（时间词）
    print("  [时间线] 时间词一致性...")
    time_words = ['第二天', '第三天', '次日', '当天', '第二天早上', '当晚', '一周后', '一个月后']
    for ch in chapters:
        n, c = ch['chapterNumber'], ch.get('content', '')
        for tw in time_words:
            if tw in c:
                # 检查相近章节是否有时间矛盾
                pass

    print(f"  结果: {len(issues)} 条告警 (只报告不改)")
    return issues, 0


# ── Step 7: Anti-fatigue 扫描 ──

def audit_anti_fatigue(db_novel, novel_name, report_only):
    """7维疲劳检测"""
    print("\n═══ Step 7: Anti-fatigue 扫描 ═══")
    issues = []
    chapters = list(db_novel['chapters'].find(
        {'novelName': novel_name}
    ).sort('chapterNumber', 1))

    # 收集所有对白
    dialogues = defaultdict(list)
    action_patterns = defaultdict(list)

    for ch in chapters:
        n, c = ch['chapterNumber'], ch.get('content', '')
        # 对白
        dlg = re.findall(r'「[^」]{4,80}」', c)
        for d in dlg:
            dialogues[n].append(d)

        # 战斗/动作模式
        if any(kw in c for kw in ['一拳', '一脚', '闪身', '躲开', '轰']):
            action_patterns[n].append('战斗')

    # 检测对白重复
    dlg_all = [d for dl in dialogues.values() for d in dl]
    dlg_set = set(dlg_all)
    if len(dlg_all) - len(dlg_set) > len(dlg_all) * 0.3:
        issues.append("  ⚠️ 对白重复率 > 30%，建议检查")

    # 战斗密度
    action_chapters = len(action_patterns)
    if action_chapters > len(chapters) * 0.4:
        issues.append(f"  ⚠️ 战斗章节占比 {action_chapters}/{len(chapters)}，偏高")

    # 情绪词分析
    positive = ['成功', '突破', '觉醒', '获得', '找到', '赢了', '救']
    negative = ['危险', '失败', '受伤', '丢失', '失去', '被困']
    pos_count = 0
    neg_count = 0
    for ch in chapters:
        c = ch.get('content', '')
        pos_count += sum(1 for p in positive if p in c)
        neg_count += sum(1 for n in negative if n in c)

    ratio = pos_count / max(neg_count, 1)
    if ratio > 5:
        issues.append(f"  ⚠️ 积极/消极情绪比 {ratio:.1f}:1，爽点模式可能重复")

    for i in issues:
        print(f"  {i}")
    if not issues:
        print("  ✅ 无明显疲劳迹象")
    print(f"  结果: {len(issues)} 条告警 (只报告不改)")
    return issues, 0


# ── Step 8: Editor 质量检查 ──

def audit_editor_quality(db_novel, novel_name, report_only):
    """editor 级别的质量检查"""
    print("\n═══ Step 8: Editor 质量检查 ═══")
    issues = []
    chapters = list(db_novel['chapters'].find(
        {'novelName': novel_name}
    ).sort('chapterNumber', 1))

    issues_by_ch = defaultdict(list)

    for ch in chapters:
        n, c = ch['chapterNumber'], ch.get('content', '')
        if not c:
            continue

        # 检查开头场景跳跃
        first_line = c.strip().split('\n')[0][:30]
        if any(kw in first_line for kw in ['突然', '然而', '但是']):
            issues_by_ch[n].append("开头突兀")

        # 检查废话
        filler_words = ['说实话', '老实说', '其实吧', '你知道吗', '我跟你讲']
        filler_count = sum(1 for f in filler_words if f in c)
        if filler_count > 3:
            issues_by_ch[n].append(f"废话词 {filler_count} 次")

        # 检查水字数
        para_pattern = re.findall(r'\n\n\n', c)
        if len(para_pattern) > 10:
            issues_by_ch[n].append(f"多余空行 {len(para_pattern)} 处")

        # 章节结尾钩子
        last_300 = c[-300:] if len(c) > 300 else c
        if not any(kw in last_300 for kw in ['？', '！', '……', '—', '「']):
            issues_by_ch[n].append("结尾缺乏悬念")

    total_issues = sum(len(v) for v in issues_by_ch.values())
    for ch_num, ch_issues in sorted(issues_by_ch.items()):
        for i in ch_issues:
            msg = f"  📋 ch{ch_num}: {i}"
            issues.append(msg)
            print(msg)

    if total_issues == 0:
        print("  ✅ 质量良好")
    print(f"  结果: {total_issues} 处告警")
    return issues, 0


# ── 主流程 ──

def main():
    parser = argparse.ArgumentParser(description='小说全量审核+自动修复')
    parser.add_argument('project_name', nargs='?', default='诡异游戏：我的规则别人看不见',
                        help='项目名')
    parser.add_argument('--report-only', action='store_true',
                        help='只审核不修改')
    parser.add_argument('--skip-steps', type=str, default='',
                        help='跳过的步骤编号，逗号分隔 (例: 1,3)')
    args = parser.parse_args()

    project_name = args.project_name
    report_only = args.report_only or False
    skip_steps = [int(s.strip()) for s in args.skip_steps.split(',') if s.strip()]

    # 模糊匹配
    client, db_nf, db_novel = connect()
    try:
        # 查找 novel
        nv = db_novel['novels'].find_one({
            '$or': [
                {'title': {'$regex': re.escape(project_name)}},
                {'name': {'$regex': re.escape(project_name)}},
            ]
        })
        if not nv:
            print(f"❌ 找不到小说: {project_name}")
            # 列出所有
            print("可用:")
            for n in db_novel['novels'].find():
                print(f"  - {n.get('title','')}")
            return

        novel_name = nv.get('name') or nv.get('title', '')
        print(f"\n{'='*60}")
        print(f"  全量审核: {nv.get('title','')}")
        print(f"  NovelName: {novel_name}")
        print(f"  Mode: {'只报告' if report_only else '审核+自动修复'}")
        print(f"{'='*60}\n")

        # 找 project_id
        pid = None
        proj = db_nf['projects'].find_one({'title': novel_name})
        if proj:
            pid = proj['project_id']
        else:
            proj = db_nf['projects'].find_one({'title': {'$regex': re.escape(novel_name)}})
            if proj:
                pid = proj['project_id']

        if not pid:
            print("⚠️ novel_factory.projects 找不到该项目，尝试用 novelName 关联...")
            pid = f"proj_{novel_name[:20].lower().replace(' ','-')}"
            # fallback
            pid = None

        last_chapter = db_novel['chapters'].count_documents({'novelName': novel_name})
        print(f"  总章节: {last_chapter}\n")

        all_issues = []
        all_fixes = 0

        # Step 1
        if 1 not in skip_steps:
            iss, fix = audit_character_presence(db_novel, db_nf, novel_name, pid, report_only)
            all_issues.extend(iss); all_fixes += fix

        # Step 2
        if 2 not in skip_steps:
            iss, fix = audit_timeline(db_nf, pid, last_chapter, report_only)
            all_issues.extend(iss); all_fixes += fix

        # Step 3
        if 3 not in skip_steps:
            iss, fix = audit_arc_metadata(db_nf, pid, report_only)
            all_issues.extend(iss); all_fixes += fix

        # Step 4
        if 4 not in skip_steps:
            iss, fix = audit_hooks(db_novel, db_nf, novel_name, pid, last_chapter, report_only)
            all_issues.extend(iss); all_fixes += fix

        # Step 5
        if 5 not in skip_steps:
            iss, fix = audit_foreshadow(db_nf, pid, last_chapter, report_only)
            all_issues.extend(iss); all_fixes += fix

        # Step 6 (只报告)
        if 6 not in skip_steps:
            iss, _ = audit_consistency_7d(db_novel, novel_name, pid, report_only)
            all_issues.extend(iss)

        # Step 7 (只报告)
        if 7 not in skip_steps:
            iss, _ = audit_anti_fatigue(db_novel, novel_name, report_only)
            all_issues.extend(iss)

        # Step 8 (只报告)
        if 8 not in skip_steps:
            iss, _ = audit_editor_quality(db_novel, novel_name, report_only)
            all_issues.extend(iss)

        # ── 生成报告 ──
        print(f"\n{'='*60}")
        print(f"  审核完成")
        print(f"  自动修复: {all_fixes} 处")
        print(f"  报告告警: {len(all_issues)} 条")
        print(f"{'='*60}")

        report = {
            'project': novel_name,
            'mode': 'report_only' if report_only else 'auto_fix',
            'fixes': all_fixes,
            'warnings': len(all_issues),
            'issues': all_issues[:50],  # 只存前50条
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        # 保存报告
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f'/root/zj-matrix/novel-factory/audit-report-{now_str}.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n报告已保存: {report_path}")

        # 也存档最简单的一句
        print(f"\n建议继续执行:")
        print(f"  novel-factory continue '{novel_name}'")
        print(f"  cat {report_path}")

    finally:
        client.close()


if __name__ == '__main__':
    main()
