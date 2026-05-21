# MongoDB Sync Fallback

当 `sync-novel-to-mongodb.py` 因目录结构不匹配或文件名格式异常而失败时，用此 Python 片段做直连 upsert。

## 用法

```bash
python3 references/mongodb-sync-fallback.md
```

调整脚本顶部的四个变量：`NOVEL_NAME`、`CHAPTER_NUM`、`CHAPTER_FILE`。

```python
#!/usr/bin/env python3
"""Fallback: direct MongoDB upsert for a single chapter.
Adjust the 4 variables below to match your case, then run."""

import pymongo, re

# ===== 调整这 4 个变量 =====
NOVEL_NAME = '诡异游戏：我的规则别人看不见'
CHAPTER_NUM = 136
CHAPTER_FILE = '/root/zj-matrix/novel-factory/chapters/ch136_旧城区图书馆.md'
# =========================

uri = 'mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/novel?authSource=admin'
db = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)['novel']

content = open(CHAPTER_FILE, 'r', encoding='utf-8').read()
first_line = content.split('\n')[0]
ch_title = re.sub(r'^#+\s*第\d+章[:：]?\s*', '', first_line).strip()
full_title = f'第{CHAPTER_NUM}章 {ch_title}'
filename = f'ch{CHAPTER_NUM:03d}_{ch_title}.md'

# upsert chapter
result = db.chapters.update_one(
    {'novelName': NOVEL_NAME, 'chapterNumber': CHAPTER_NUM},
    {'$set': {
        'novelName': NOVEL_NAME,
        'chapterNumber': CHAPTER_NUM,
        'title': full_title,
        'filename': filename,
        'content': content,
        'chapterEndNotes': '',
        'version': 'v1',
        'wordCount': len(content)
    }},
    upsert=True
)
print(f'章节: {"新建" if result.upserted_id else "更新"} (ch{CHAPTER_NUM})')

# update novels stats
total_chs = db.chapters.count_documents({'novelName': NOVEL_NAME})
total_words = sum(
    c.get('wordCount', 0) or len(c.get('content',''))
    for c in db.chapters.find({'novelName': NOVEL_NAME})
)
db.novels.update_one(
    {'name': NOVEL_NAME},
    {'$set': {
        'stats.words': total_words,
        'stats.chapters': total_chs,
        'updatedAt': __import__('datetime').datetime.utcnow()
    }}
)
print(f'novels 更新: {total_chs} 章, {total_words} 字')
print('✅ 同步完成')
```
