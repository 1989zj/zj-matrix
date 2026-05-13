#!/usr/bin/env python3
"""
批量减少两本小说破折号 + 通过认证上传MongoDB
1. 末世: 5,802→1,741 (70%)
2. 诡异游戏: 24,712→7,296 (70%)
"""
import re, sys, os
import requests

sys.path.insert(0, '/root/NovelStudio/web')
from dotenv import load_dotenv
load_dotenv('/root/NovelStudio/web/.env')

API_BASE = 'http://192.168.2.47:5003'

# ── 认证 ──
s = requests.Session()
lr = s.post(f'{API_BASE}/login/', data={'phone': 'admin', 'code': '456321zj'},
            headers={'User-Agent': 'HermesAgent/1.0'}, allow_redirects=True)
assert lr.status_code == 200, f"Login failed: {lr.status_code}"
print(f"✅ 认证成功: {list(s.cookies.keys())}")

def upload_chapter(novel, cn, content, title):
    r = s.post(f'{API_BASE}/api/upload-chapter', json={
        'novelName': novel, 'chapterNumber': cn,
        'content': content, 'title': title
    }, headers={'User-Agent': 'HermesAgent/1.0'})
    return r.status_code == 200 and r.json().get('success')

# ── 末世小说 ──
def reduce_novel1(text):
    if not text: return text, 0
    orig = text
    for p in '，、。？！：；':
        text = text.replace(f'{p}——', p)
    text = text.replace('"——"', '""').replace('"——"', '""')
    text = text.replace('"——“', '""').replace('"——“', '""')
    text = text.replace('"——', '"').replace('"——', '"')
    text = text.replace('”——', '”').replace('"——', '"')
    
    prev = None
    while prev is None or text.count('——') != prev:
        prev = text.count('——')
        text = re.sub(r'——(.{5,100}?)——', lambda m: f'，{m.group(1)}，', text)
        if text.count('——') < 2: break
    
    text = re.sub(r'(不是[^，。——！？]{2,30})——', r'\1，', text)
    text = re.sub(r'——(是[^，。——！？]{2,30})', r'，\1', text)
    for w in ['就是', '像是', '如同']:
        text = re.sub(f'({w}[^，。——！？]{{2,25}})——', r'\1，', text)
    text = text.replace('""', '')
    return text, orig.count('——') - text.count('——')

# ── 诡异游戏 ──
def reduce_novel2(text):
    if not text: return text, 0
    orig = text
    text = text.replace('「——', '「◆PRFX')
    text = text.replace('——」', 'SUFX◆」')
    for p in '，、。？！：；':
        text = text.replace(f'{p}——', p)
    text = text.replace('"——"', '""').replace('"——"', '""')
    text = text.replace('"——“', '""').replace('"——“', '""')
    text = text.replace('"——', '"').replace('"——', '"')
    text = text.replace('”——', '”').replace('"——', '"')
    
    prev = None
    while prev is None or text.count('——') != prev:
        prev = text.count('——')
        text = re.sub(r'——(.{5,100}?)——', lambda m: f'，{m.group(1)}，', text)
        if text.count('——') < 2: break
    
    text = re.sub(r'(不是[^，。——！？]{2,30})——', r'\1，', text)
    text = re.sub(r'——(是[^，。——！？]{2,30})', r'，\1', text)
    for w in ['就是', '像是', '如同']:
        text = re.sub(f'({w}[^，。——！？]{{2,25}})——', r'\1，', text)
    text = text.replace('""', '')
    text = text.replace('「◆PRFX', '「——')
    text = text.replace('SUFX◆」', '——」')
    return text, orig.count('——') - text.count('——')


# ══ 执行 ══
from app.db import db

NOVELS = [
    ('我的第一部小说', reduce_novel1),
    ('诡异游戏：我的规则别人看不见', reduce_novel2),
]

for novel_name, reduce_fn in NOVELS:
    chapters = list(db['chapters'].find({'novelName': novel_name}).sort('chapterNumber', 1))
    print(f"\n{'='*55}\n📖 {novel_name} ({len(chapters)} 章)")
    
    total_before = total_after = total_removed = 0
    updated = 0
    
    for ch in chapters:
        cn = ch['chapterNumber']
        content = ch.get('content', '') or ''
        before = content.count('——')
        total_before += before
        if before == 0: continue
        
        new_content, removed = reduce_fn(content)
        after = new_content.count('——')
        total_after += after
        total_removed += removed
        
        if upload_chapter(novel_name, cn, new_content, ch.get('title', '')):
            updated += 1
            pct = ((before - after) / before) * 100
            bar = '█' * min(int(pct/5), 18) + '░' * max(18-min(int(pct/5), 18), 0)
            print(f"  Ch{cn:3d}: {before:3d}→{after:3d} (-{removed:3d}, {pct:3.0f}%) {bar}")
        else:
            print(f"  Ch{cn:3d}: ❌ 上传失败")
    
    avg_pct = ((total_before - total_after) / total_before) * 100 if total_before else 0
    print(f"\n  ✅ 总计: {total_before}→{total_after} (-{total_removed}, {avg_pct:.0f}%) | 更新 {updated}/{len(chapters)} 章")
