#!/usr/bin/env python3
"""
lore-corrector.py — 设定同步检测器

根据最新世界观圣经, 扫描旧章节中的设定冲突。

用法:
  python3 lore-corrector.py scan '诡异游戏' --chapters 1-100
  python3 lore-corrector.py bible-diff '诡异游戏'  # 查看 Bible 版本变更
"""

import pymongo
import json
import sys
import re
import hashlib
import argparse
from datetime import datetime, timezone
from collections import defaultdict

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"


def connect():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    return client, client["novel_factory"], client["novel"]


def load_bible_history(db_nf, pid):
    """加载圣经及其版本历史"""
    bible = db_nf['world_bible'].find_one({'project_id': pid})
    if bible:
        return {
            'rules': bible.get('rules', bible.get('world_rules', [])),
            'power_system': bible.get('power_system', bible.get('power', {})),
            'geography': bible.get('geography', {}),
            'version': bible.get('version', 'v1'),
            'last_updated': bible.get('updated_at', bible.get('created_at', None)),
            'historical_versions': bible.get('version_history', []),
        }
    ws = db_nf['world_state'].find_one({'project_id': pid})
    if ws:
        return {
            'rules': ws.get('active_rules', []),
            'power_system': ws.get('power_system', {}),
            'version': 'from_world_state',
        }
    return {}


def extract_power_rules(bible):
    """从圣经提取战力/等级规则"""
    rules = {}
    ps = bible.get('power_system', {})
    
    tiers = ps.get('tiers', [])
    for t in tiers:
        name = t.get('name', '')
        if name:
            restrictions = []
            desc = t.get('description', '')
            if '不能' in desc or '无法' in desc or '禁止' in desc:
                # 提取限制条件
                restrictions = re.findall(r'[^。]*?(?:不能|无法|禁止)[^。]*。', desc)
            rules[name] = {
                'description': desc,
                'restrictions': restrictions,
                'prerequisites': t.get('prerequisites', t.get('requirements', [])),
            }
    
    return rules


def extract_lore_rules(bible):
    """提取世界观规则 (用于检测冲突)"""
    raw_rules = bible.get('rules', [])
    processed = []
    
    for rule in raw_rules:
        if isinstance(rule, str):
            processed.append({'name': rule, 'description': rule, 'type': 'unknown'})
        elif isinstance(rule, dict):
            processed.append({
                'name': rule.get('name', rule.get('rule', '')),
                'description': rule.get('description', rule.get('text', '')),
                'type': rule.get('type', 'unknown'),
                'severity': rule.get('severity', 'medium'),
            })
    
    return processed


def find_violations(content, rules, power_rules):
    """在正文中检测对规则的违反"""    
    violations = []
    
    # 战力等级限制检测
    for tier_name, tier_info in power_rules.items():
        if not tier_info['restrictions']:
            continue
        for restriction in tier_info['restrictions']:
            # 如果正文中提到这个等级且有明令禁止的行为
            if tier_name in content:
                for restr in restriction:
                    # 简单关键词检测
                    if restr in content:
                        violations.append({
                            'rule': f"{tier_name}: {restriction}",
                            'severity': 'warning',
                            'type': 'power_restriction',
                        })
    
    return violations


def cmd_scan(args):
    """扫描设定冲突"""
    client, db_nf, db_novel = connect()
    try:
        novel_name = args.project
        nv = db_novel['novels'].find_one({
            '$or': [{'title': {'$regex': args.project}},
                    {'name': {'$regex': args.project}}]
        })
        if not nv:
            print(f"❌ 找不到项目: {args.project}")
            return
        
        novel_name = nv.get('name') or nv.get('title', '')
        pid = None
        proj = db_nf['projects'].find_one({'title': {'$regex': re.escape(novel_name)}})
        if proj:
            pid = proj['project_id']
        
        if not pid:
            print(f"❌ 找不到 project_id")
            return
        
        bible = load_bible_history(db_nf, pid)
        print(f"\n=== 设定同步扫描: {novel_name} ===")
        print(f"Bible 版本: {bible.get('version', 'N/A')}")
        print(f"最后更新: {bible.get('last_updated', 'N/A')}")
        
        rules = extract_lore_rules(bible)
        power_rules = extract_power_rules(bible)
        
        print(f"世界观规则: {len(rules)} 条")
        print(f"战力体系: {len(power_rules)} 个等级\n")
        
        # 解析章节范围
        if args.chapters:
            if '-' in args.chapters:
                parts = args.chapters.split('-')
                ch_range = list(range(int(parts[0]), int(parts[1]) + 1))
            else:
                ch_range = [int(x.strip()) for x in args.chapters.split(',')]
        else:
            ch_range = list(range(1, 137))
        
        print(f"扫描章节: ch{ch_range[0]}-ch{ch_range[-1]} ({len(ch_range)} 章)")
        
        total_issues = 0
        chapter_issues = defaultdict(list)
        
        for ch_num in ch_range:
            ch = db_novel['chapters'].find_one(
                {'novelName': novel_name, 'chapterNumber': ch_num}
            )
            if not ch:
                continue
            content = ch.get('content', '') or ch.get('text', '')
            if not content:
                continue
            
            violations = find_violations(content, rules, power_rules)
            if violations:
                chapter_issues[ch_num] = violations
                total_issues += len(violations)
        
        if total_issues == 0:
            print(f"\n✅ 未发现设定冲突 (基于现有规则)")
        else:
            print(f"\n⚠️  发现 {total_issues} 处可能的设定冲突:")
            for ch_num, issues in sorted(chapter_issues.items()):
                print(f"\n  ch{ch_num}:")
                for issue in issues:
                    print(f"    [{issue['severity']}] {issue['rule']}")
        
        # 列出所有活跃规则供参考
        if rules:
            print(f"\n--- 当前活跃规则 ---")
            for rule in rules[:20]:
                print(f"  • {rule['name']}: {rule['description'][:80]}")
        
    finally:
        client.close()


def cmd_bible_diff(args):
    """查看圣经版本变更历史"""
    client, db_nf, _ = connect()
    try:
        novel_name = args.project
        proj = db_nf['projects'].find_one({'title': {'$regex': re.escape(novel_name)}})
        if not proj:
            print(f"❌ 找不到项目")
            return
        
        pid = proj['project_id']
        bible = db_nf['world_bible'].find_one({'project_id': pid})
        if not bible:
            # 从 world_state 读取
            ws = db_nf['world_state'].find_one({'project_id': pid})
            if ws:
                print(f"=== 无完整 Bible (使用 world_state) ===")
                print(f"活跃规则: {json.dumps(ws.get('active_rules', [])[:10], ensure_ascii=False, indent=2)}")
            else:
                print(f"❌ 无法获知世界观数据")
            return
        
        print(f"\n=== Bible 版本信息 ===")
        print(f"版本: {bible.get('version', bible.get('_id', 'N/A'))}")
        print(f"最后修改: {bible.get('updated_at', bible.get('created_at', 'N/A'))}")
        
        # 规则列表
        rules = bible.get('rules', bible.get('world_rules', []))
        print(f"\n--- 世界观规则 ({len(rules)} 条) ---")
        for i, rule in enumerate(rules[:30]):
            name = rule.get('name', rule.get('rule', f'规则#{i+1}'))
            desc = rule.get('description', rule.get('text', ''))
            print(f"  {i+1}. {name}: {desc[:100]}")
        
        # 历史版本
        history = bible.get('version_history', [])
        if history:
            print(f"\n--- 版本历史 ({len(history)} 次变更) ---")
            for h in history:
                print(f"  {h.get('version', '?')} @ {h.get('timestamp', '?')}: {h.get('changes', '')[:60]}")
        
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description='Lore Corrector — 设定同步检测器')
    subparsers = parser.add_subparsers(dest='command')
    
    s = subparsers.add_parser('scan', help='扫描设定冲突')
    s.add_argument('project')
    s.add_argument('--chapters', '-c', help='章节范围: 1-50')
    
    b = subparsers.add_parser('bible-diff', help='查看Bible版本')
    b.add_argument('project')
    
    args = parser.parse_args()
    
    if args.command == 'scan':
        cmd_scan(args)
    elif args.command == 'bible-diff':
        cmd_bible_diff(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
