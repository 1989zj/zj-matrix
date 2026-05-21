#!/usr/bin/env python3
"""
state-diff.py — 状态差异记录器

功能:
  - 对比精修前后的章节内容
  - 生成 unified diff
  - 写入 refinement_log 和 refinement_patches
  
用法:
  python3 state-diff.py diff '诡异游戏' --chapter 52 --original file1.txt --patched file2.txt
  python3 state-diff.py verify '诡异游戏' --chapter 52
  python3 state-diff.py rollback '诡异游戏' --chapter 52 --patch PATCH_ID
"""

import pymongo
import json
import sys
import hashlib
import argparse
from datetime import datetime, timezone
from difflib import unified_diff

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"
PATCH_COLLECTION = "refinement_patches"
LOG_COLLECTION = "refinement_log"


def connect():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    return client, client["novel_factory"], client["novel"]


def content_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def generate_diff(original, patched):
    """生成可读的 unified diff"""
    orig_lines = original.splitlines(keepends=True)
    patch_lines = patched.splitlines(keepends=True)
    diff = unified_diff(orig_lines, patch_lines,
                        fromfile='original', tofile='patched', n=3)
    return ''.join(diff)


def cmd_diff(args):
    """生成并保存 diff"""
    client, db_nf, db_novel = connect()
    try:
        # 读取正文
        novel_name = args.project
        nv = db_novel['novels'].find_one({
            '$or': [{'title': {'$regex': args.project}},
                    {'name': {'$regex': args.project}}]
        })
        if not nv:
            print(f"❌ 找不到项目: {args.project}")
            return
        
        novel_name = nv.get('name') or nv.get('title', '')
        
        if args.original and args.patched:
            with open(args.original, 'r', encoding='utf-8') as f:
                original = f.read()
            with open(args.patched, 'r', encoding='utf-8') as f:
                patched = f.read()
        else:
            # 从数据库读取
            ch = db_novel['chapters'].find_one(
                {'novelName': novel_name, 'chapterNumber': args.chapter}
            )
            if not ch:
                print(f"❌ 找不到 ch{args.chapter}")
                return
            original = ch.get('content', '') or ch.get('text', '')
            patched = original  # 无修改时diff为空
        
        diff = generate_diff(original, patched)
        
        changes = sum(1 for line in diff.split('\n') if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff.split('\n') if line.startswith('-') and not line.startswith('---'))
        
        print(f"=== Diff: ch{args.chapter} ===")
        print(f"原长度: {len(original)} 字符")
        print(f"新长度: {len(patched)} 字符")
        print(f"改动: +{changes}/-{deletions} 行")
        print(f"\n{diff[:2000]}")
        
        # 写入 refinement_log
        patch_id = f"diff_ch{args.chapter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建 patch 记录
        if diff.strip():
            patch_doc = {
                'project_id': novel_name,
                'patch_id': patch_id,
                'chapter': args.chapter,
                'patch_type': 'manual_diff',
                'status': 'applied',
                'reason': f'手动 diff (ch{args.chapter})',
                'diff': diff,
                'original_hash': content_hash(original),
                'patched_hash': content_hash(patched),
                'impact': 'medium' if changes > 5 else 'low',
                'created_by': 'state-diff',
                'created_at': datetime.now(timezone.utc),
                'applied_at': datetime.now(timezone.utc),
            }
            db_nf[PATCH_COLLECTION].insert_one(patch_doc)
            print(f"\n✅ Patch 已保存: {patch_id}")
        
        # 更新精修日志
        db_nf[LOG_COLLECTION].update_one(
            {'project_id': novel_name, 'chapter': args.chapter},
            {
                '$set': {
                    'last_refined_at': datetime.now(timezone.utc),
                    'current_hash': content_hash(patched),
                },
                '$inc': {'refinement_count': 1},
                '$push': {'patch_ids': patch_id},
            },
            upsert=True,
        )
        
    finally:
        client.close()


def cmd_verify(args):
    """校验章节内容完整性"""
    client, _, db_novel = connect()
    try:
        nv = db_novel['novels'].find_one({
            '$or': [{'title': {'$regex': args.project}},
                    {'name': {'$regex': args.project}}]
        })
        if not nv:
            print(f"❌ 找不到项目: {args.project}")
            return
        
        novel_name = nv.get('name') or nv.get('title', '')
        ch = db_novel['chapters'].find_one(
            {'novelName': novel_name, 'chapterNumber': args.chapter}
        )
        if not ch:
            print(f"❌ 找不到 ch{args.chapter}")
            return
        
        content = ch.get('content', '') or ch.get('text', '')
        h = content_hash(content)
        
        print(f"=== ch{args.chapter} 校验 ===")
        print(f"字数: {len(content)}")
        print(f"SHA256: {h}")
        print(f"有钩子: {'是' if ch.get('hook', '호') != 'ه' else '未知'}")
        
        # 对比 refinement_log
        client2, db_nf, _ = connect()
        try:
            log = db_nf[LOG_COLLECTION].find_one(
                {'project_id': novel_name, 'chapter': args.chapter}
            )
            if log:
                print(f"上次精修: {log.get('last_refined_at')}")
                print(f"精修次数: {log.get('refinement_count', 0)}")
                print(f"记录hash: {log.get('current_hash', 'N/A')}")
                if log.get('current_hash') != h:
                    print(f"⚠️  HASH 不一致! 内容在记录之后被修改过")
            else:
                print("ℹ️  无精修记录")
        finally:
            client2.close()
        
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description='State Diff — 状态差异记录器')
    subparsers = parser.add_subparsers(dest='command')
    
    d = subparsers.add_parser('diff', help='生成diff并记录')
    d.add_argument('project')
    d.add_argument('--chapter', '-c', type=int, required=True)
    d.add_argument('--original', help='原始文件路径')
    d.add_argument('--patched', help='修改后文件路径')
    
    v = subparsers.add_parser('verify', help='校验章节完整性')
    v.add_argument('project')
    v.add_argument('--chapter', '-c', type=int, required=True)
    
    args = parser.parse_args()
    
    if args.command == 'diff':
        cmd_diff(args)
    elif args.command == 'verify':
        cmd_verify(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
