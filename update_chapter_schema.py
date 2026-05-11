#!/usr/bin/env python3
"""分离章尾说明 + 增加版本字段"""
import re
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/"
DB_NAME = "novel"

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=15000)
db = client[DB_NAME]
chapters_col = db['chapters']

now = datetime.now(timezone.utc).isoformat()
updated = 0
no_change = 0

for num in range(1, 61):
    doc = chapters_col.find_one({"novelName": "我的第一部小说", "chapterNumber": num})
    if not doc:
        print(f"  第{num}章: 未找到")
        continue
    
    content = doc['content']
    lines = content.rstrip().split('\n')
    
    # 查找最后一个 ---
    sep_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == '---':
            sep_idx = i
            break
    
    chapter_end_notes = ""
    main_content = content
    
    if sep_idx is not None:
        after_sep = '\n'.join(lines[sep_idx + 1:]).strip()
        # 判断是否真的是元信息（非故事正文）
        is_meta = any(after_sep.startswith(m) for m in [
            '**本章', '**全卷', '**第', '**字数**', '**生成'
        ])
        if is_meta:
            chapter_end_notes = after_sep
            main_content = '\n'.join(lines[:sep_idx]).strip()
    
    # 版本记录
    versions = [{
        "version": "v1",
        "content": main_content,
        "chapterEndNotes": chapter_end_notes,
        "updatedAt": now,
        "notes": "初始版本（从文件系统导入）"
    }]
    
    # 已有版本字段则不重复更新
    if 'versions' in doc and doc.get('chapterEndNotes') == chapter_end_notes:
        no_change += 1
        continue
    
    chapters_col.update_one(
        {"novelName": "我的第一部小说", "chapterNumber": num},
        {"$set": {
            "content": main_content,
            "chapterEndNotes": chapter_end_notes,
            "version": "v1",
            "versions": versions,
            "updatedAt": now
        }}
    )
    updated += 1
    status = "有章尾说明" if chapter_end_notes else "无章尾说明"
    print(f"  第{num:2d}章: {status} (正文{len(main_content)}字, 尾注{len(chapter_end_notes)}字)")

print(f"\n更新 {updated} 章, 无需变更 {no_change} 章")
print("完成 ✅")
