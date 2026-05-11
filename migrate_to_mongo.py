#!/usr/bin/env python3
"""迁移小说数据从文件系统到MongoDB"""
import os
import re
import json
from pathlib import Path
from pymongo import MongoClient, ASCENDING

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/"
DB_NAME = "novel"
BASE_DIR = Path("/root/NovelStudio/novels")
WEB_DIR = Path("/root/NovelStudio/web")


def chinese_to_int(s):
    digits = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
              '六': 6, '七': 7, '八': 8, '九': 9}
    if '十' in s:
        parts = s.split('十')
        tens = digits.get(parts[0], 1) if parts[0] else 1
        ones = digits.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    return digits.get(s, 0)


def get_chapter_number(filename):
    """从文件名提取章节号"""
    stem = filename.replace('.md', '')
    m = re.search(r'第([一二三四五六七八九十百千万\d]+)章', stem)
    if m:
        raw = m.group(1)
        try:
            return int(raw) if raw.isdigit() else chinese_to_int(raw)
        except (ValueError, KeyError):
            pass
    return 0


def import_novels(client):
    """导入小说元数据"""
    db = client[DB_NAME]
    novels_col = db['novels']
    chapters_col = db['chapters']
    reports_col = db['reports']

    # 直接从app模块导入NOVEL_META
    import sys
    sys.path.insert(0, str(WEB_DIR))
    import app
    NOVEL_META_RAW = app.NOVEL_META

    print(f"找到 {len(NOVEL_META_RAW)} 部小说元数据")
    
    for name, meta in NOVEL_META_RAW.items():
        # 检查novel_dir是否存在
        novel_dir = BASE_DIR / name
        print(f"\n=== {meta['title']} ({name}) ===")
        
        # 1. 写入novels集合
        novel_doc = {
            "name": name,
            "title": meta['title'],
            "author": meta.get('author', ''),
            "slug": meta['slug'],
            "genre": meta.get('genre', ''),
            "target": meta.get('target', ''),
            "synopsis": meta.get('synopsis', ''),
            "stats": {
                "words": meta.get('stats', {}).get('words', 0),
                "chapters": meta.get('stats', {}).get('chapters', 0),
                "status": meta.get('stats', {}).get('status', '')
            },
            "characters": meta.get('characters', []),
            "world": meta.get('world', {}),
            "updatedAt": None  # will set after importing chapters
        }
        
        novels_col.update_one(
            {"name": name},
            {"$set": novel_doc},
            upsert=True
        )
        print(f"  小说元数据已写入novels集合")

        # 2. 写入chapters集合
        chapters_dir = novel_dir / "章节"
        if not chapters_dir.exists():
            print(f"  章节目录不存在: {chapters_dir}")
            continue

        chapter_files = sorted(chapters_dir.glob("*.md"), 
                              key=lambda f: get_chapter_number(f.name))
        
        # 先清空旧章节
        chapters_col.delete_many({"novelName": name})
        
        chapter_docs = []
        for f in chapter_files:
            num = get_chapter_number(f.name)
            text = f.read_text(encoding='utf-8')
            lines = text.split('\n')
            
            # 提取标题
            title = ""
            for line in lines:
                if line.startswith('# '):
                    title = line.replace('# ', '').strip()
                    break
            if not title:
                title = f.stem
            
            # 字数统计
            clean = re.sub(r'#.*?\n', '', text)
            clean = re.sub(r'\*\*.*?\*\*', '', clean)
            clean = re.sub(r'【.*?】', '', clean)
            word_count = len(re.sub(r'\s', '', clean))
            
            chapter_docs.append({
                "novelName": name,
                "chapterNumber": num,
                "title": title,
                "filename": f.name,
                "content": text,
                "wordCount": word_count
            })
        
        if chapter_docs:
            chapters_col.insert_many(chapter_docs)
            total_words = sum(c['wordCount'] for c in chapter_docs)
            # 更新stats
            novels_col.update_one(
                {"name": name},
                {"$set": {
                    "stats.words": total_words,
                    "stats.chapters": len(chapter_docs),
                    "updatedAt": __import__('datetime').datetime.now().isoformat()
                }}
            )
            print(f"  导入 {len(chapter_docs)} 章，总字数 {total_words:,}")

        # 3. 写入reports集合（分析报告）
        reports_col.delete_many({"novelName": name})
        report_files = list(novel_dir.glob("*.md"))
        report_count = 0
        for rf in report_files:
            # 跳过章节目录中的文件
            if rf.parent.name == "章节":
                continue
            report_text = rf.read_text(encoding='utf-8')
            report_type = "report"
            # 根据文件名推断类型
            fname = rf.stem
            if "一致性" in fname or fname == "一致性检查报告":
                report_type = "consistency"
            elif "逻辑" in fname:
                report_type = "logic"
            elif "爽点" in fname:
                report_type = "highlight"
            elif "总编" in fname or "商业" in fname:
                report_type = "review"
            elif "标题" in fname:
                report_type = "titles"
            elif "阶段总结" in fname or "全书" in fname:
                report_type = "summary"
            
            reports_col.insert_one({
                "novelName": name,
                "type": report_type,
                "filename": rf.name,
                "content": report_text,
                "createdAt": __import__('datetime').datetime.now().isoformat()
            })
            report_count += 1
            print(f"  报告已导入: {rf.name}")
        print(f"  导入 {report_count} 份分析报告")

    # 创建索引
    chapters_col.create_index([("novelName", ASCENDING), ("chapterNumber", ASCENDING)], unique=True)
    reports_col.create_index([("novelName", ASCENDING), ("type", ASCENDING)])
    novels_col.create_index("name", unique=True)
    novels_col.create_index("slug", unique=True)
    print("\n✅ 索引创建完成")


def main():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=15000)
    # 测试连接
    client.server_info()
    print(f"MongoDB 连接成功: {client.server_info()['version']}")
    
    import_novels(client)
    
    # 汇总统计
    db = client[DB_NAME]
    print(f"\n{'='*50}")
    print(f"  小说: {db['novels'].count_documents({})}")
    print(f"  章节: {db['chapters'].count_documents({})}")
    print(f"  报告: {db['reports'].count_documents({})}")
    print(f"{'='*50}")
    print("迁移完成 ✅")


if __name__ == "__main__":
    main()
