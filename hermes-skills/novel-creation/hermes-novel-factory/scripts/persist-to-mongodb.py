#!/usr/bin/env python3
"""
MongoDB 持久化脚本 — novel-factory 产出写入数据库

用法:
  # V1/手动模式：扫描 /root/chapterN_edited.txt
  python3 persist-to-mongodb.py [--dir /root/] [--novel-name "小说名"]

  # novel-factory CLI 模式：读取 novel-factory 目录结构
  python3 persist-to-mongodb.py --novel-factory <slug>

功能:
  1. 扫描并读取章节文件（支持两种路径格式）
  2. 写入 novel.chapters / novel.novels（novelName 字段关联）
  3. 写入 novel_factory.arcs / novel_factory.characters
  4. 不提交 GitHub
"""
import pymongo, os, re, sys
from datetime import datetime

# --- 配置 ---
MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/novel?authSource=admin"
FACTORY_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/novel_factory?authSource=admin"
NOVEL_FACTORY_BASE = "/root/novel-factory"

# --- 参数解析 ---
NOVEL_FACTORY_SLUG = None
OUTPUT_DIR = "/root/"
NOVEL_NAME_OVERRIDE = None

i = 1
while i < len(sys.argv):
    if sys.argv[i] == '--dir' and i + 1 < len(sys.argv):
        OUTPUT_DIR = sys.argv[i + 1]; i += 2
    elif sys.argv[i] == '--novel-name' and i + 1 < len(sys.argv):
        NOVEL_NAME_OVERRIDE = sys.argv[i + 1]; i += 2
    elif sys.argv[i] == '--novel-factory' and i + 1 < len(sys.argv):
        NOVEL_FACTORY_SLUG = sys.argv[i + 1]; i += 2
    else:
        i += 1

# --- MongoDB 连接 ---
try:
    novel_db = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)["novel"]
    factory_db = pymongo.MongoClient(FACTORY_URI, serverSelectionTimeoutMS=5000)["novel_factory"]
except Exception as e:
    print(f"错误: MongoDB 连接失败 — {e}")
    sys.exit(1)

# ==============================================================
# novel-factory CLI 模式
# ==============================================================
if NOVEL_FACTORY_SLUG:
    project_dir = os.path.join(NOVEL_FACTORY_BASE, NOVEL_FACTORY_SLUG)
    draft_dir = os.path.join(project_dir, "draft")
    ops_dir = os.path.join(project_dir, "ops")
    outline_path = os.path.join(project_dir, "outline.md")
    summary_path = os.path.join(ops_dir, "summary.md")

    if not os.path.isdir(draft_dir):
        print(f"错误: 未找到 novel-factory 项目 {NOVEL_FACTORY_SLUG} (expected {draft_dir})")
        sys.exit(1)

    print(f"novel-factory 模式: slug={NOVEL_FACTORY_SLUG}")

    # 1. 读取章节文件
    ch_files = sorted(
        [f for f in os.listdir(draft_dir) if re.match(r'chapter-\d+\.md$', f)],
        key=lambda x: int(re.search(r'\d+', x).group())
    )
    if not ch_files:
        print(f"错误: draft 目录为空 ({draft_dir})"); sys.exit(1)
    print(f"  找到 {len(ch_files)} 个章节文件")

    # 2. 解析数据
    #   从 summary.md 提取小说名、梗概、章节标题
    novel_name = None
    synopsis = ""
    chapter_titles = {}
    if os.path.exists(summary_path):
        with open(summary_path, encoding='utf-8') as f:
            sm = f.read()
        # 小说名：第一行 # 《xxx》
        m = re.search(r'# 《(.+?)》', sm)
        if m: novel_name = m.group(1)
        # 300字梗概
        m = re.search(r'## 300字梗概\s*\n\s*\n(.*?)(?:\n\s*\n---|\n\s*##)', sm, re.DOTALL)
        if m: synopsis = m.group(1).strip()
        # 章节标题表
        m = re.search(r'## 15章标题列表.*?\n(\|.*?\|.*?\|.*?\|.*?\n?)+', sm, re.DOTALL)
        if m:
            for line in m.group(0).split('\n'):
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 2 and parts[0].isdigit():
                    chapter_titles[int(parts[0])] = parts[1]

    #   从 outline.md 提取角色和类型
    genre = "女频·治愈"
    tags = ["女频", "治愈"]
    characters = []
    if os.path.exists(outline_path):
        with open(outline_path, encoding='utf-8') as f:
            ol = f.read()
        # 提取人物关系表
        m = re.search(r'## 人物关系说明\s*\n.*?(\|.*?\|.*?\|.*?\|.*?\|.*?\n?)+', ol, re.DOTALL)
        if m:
            for line in m.group(0).split('\n'):
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 5 and parts[0] not in ('人物', '------'):
                    ch = parts[0].strip().rstrip('（主角）').strip()
                    characters.append(ch)

    if not novel_name:
        # fallback: 从 outline 第一行取
        if os.path.exists(outline_path):
            with open(outline_path, encoding='utf-8') as f:
                first = f.readline().strip()
            m = re.search(r'《(.+?)》', first)
            if m: novel_name = m.group(1)
    if not novel_name:
        novel_name = NOVEL_FACTORY_SLUG.replace('-', '的')
    if NOVEL_NAME_OVERRIDE:
        novel_name = NOVEL_NAME_OVERRIDE

    # slug 也作为 fallback 类型/标签
    slug_parts = NOVEL_FACTORY_SLUG.split('-')
    if not genre or genre == "女频·治愈":
        pass  # keep default

    print(f"  小说名: {novel_name}")
    print(f"  角色: {characters}")

    # 3. 写 novels 集合
    existing = novel_db.novels.find_one({"title": novel_name})
    if existing:
        novel_id = existing['_id']
        print(f"  → novels 集合已存在: {novel_name}")
    else:
        char_docs = [{"name": c, "title": "", "desc": "", "traits": []} for c in characters] if characters else []
        novel_db.novels.insert_one({
            "name": novel_name, "title": novel_name,
            "author": "", "genre": genre,
            "slug": NOVEL_FACTORY_SLUG,
            "synopsis": synopsis[:2000],
            "tags": tags, "target": "番茄小说",
            "characters": char_docs,
            "world": {},
            "stats": {"words": 0, "chapters": len(ch_files), "status": "已完结"},
            "updatedAt": datetime.now()
        })
        print(f"  → novels 集合新建: {novel_name}")

    # 4. 逐章写入 chapters
    total_words = 0
    for fname in ch_files:
        ch_num = int(re.search(r'\d+', fname).group())
        with open(os.path.join(draft_dir, fname), encoding='utf-8') as f:
            content = f.read().strip()
        title_from_file = content.split('\n')[0].strip().lstrip('# ')
        title = f"第{ch_num}章 {chapter_titles.get(ch_num, title_from_file)}"
        word_count = len(content)

        novel_db.chapters.update_one(
            {"novelName": novel_name, "chapterNumber": ch_num},
            {"$set": {
                "novelName": novel_name, "chapterNumber": ch_num,
                "title": title, "content": content,
                "wordCount": word_count, "version": "v1",
                "filename": f"ch{ch_num:03d}_{title_from_file}.md"
            }},
            upsert=True
        )
        total_words += word_count

    # 5. 更新字数统计
    novel_db.novels.update_one(
        {"title": novel_name},
        {"$set": {
            "stats.words": total_words,
            "stats.chapters": len(ch_files),
            "updatedAt": datetime.now()
        }}
    )

    print(f"\n✅ novel-factory 同步完成: {len(ch_files)} 章, {total_words} 字 → {novel_name}")
    sys.exit(0)

# ==============================================================
# V1 / 手动模式（原有逻辑保持不变）
# ==============================================================
# 1. 扫描章节文件
ch_files = sorted(
    [f for f in os.listdir(OUTPUT_DIR) if re.match(r'chapter\d+_edited\.txt$', f)],
    key=lambda x: int(re.search(r'\d+', x).group())
)
if not ch_files:
    ch_files = sorted(
        [f for f in os.listdir(OUTPUT_DIR) if re.match(r'chapter\d+\.txt$', f)],
        key=lambda x: int(re.search(r'\d+', x).group())
    )
if not ch_files:
    print("未在 {} 找到章节文件，跳过".format(OUTPUT_DIR))
    sys.exit(0)

print(f"找到 {len(ch_files)} 个章节文件")

# 2. 提取小说名
novel_name = NOVEL_NAME_OVERRIDE
if not novel_name:
    nov = os.environ.get('NOVEL_FACTORY_PROJECT')
    if nov: novel_name = nov
if not novel_name:
    ops_path = os.path.join(OUTPUT_DIR, "ops_package.txt")
    if os.path.exists(ops_path):
        with open(ops_path, encoding='utf-8') as f:
            for line in f:
                m = re.match(r'作品名称[：:]\s*(.+)', line)
                if m: novel_name = m.group(1).strip(); break
if not novel_name:
    with open(os.path.join(OUTPUT_DIR, ch_files[0]), encoding='utf-8') as f:
        first_line = f.readline().strip()
    novel_name = re.sub(r'^第\d+章\s*', '', first_line).strip()
    if not novel_name or len(novel_name) > 30:
        novel_name = "未命名作品"

print(f"小说名称: {novel_name}")

# 3. 确保 novels 集合
existing = novel_db.novels.find_one({"title": novel_name})
if not existing:
    slug = re.sub(r'[^\u4e00-\u9fff\w]', '-', novel_name)
    novel_db.novels.insert_one({
        "title": novel_name, "name": novel_name, "slug": slug,
        "author": "", "status": "连载中",
        "stats": {"words": 0, "chapters": 0, "status": "连载中"},
        "updatedAt": datetime.now().strftime("%Y-%m-%d"),
        "tags": ["都市", "系统流", "爽文"]
    })
    print(f"  → novels 集合新建: {novel_name}")

# 4. 逐章写入
total_words = 0
for fname in ch_files:
    ch_num = int(re.search(r'\d+', fname).group())
    with open(os.path.join(OUTPUT_DIR, fname), encoding='utf-8') as f:
        content = f.read().strip()
    lines = content.split('\n')
    title = lines[0].strip()
    body = '\n'.join(lines[1:]).strip()
    word_count = len(re.sub(r'\s', '', body))
    novel_db.chapters.update_one(
        {"novelName": novel_name, "chapterNumber": ch_num},
        {"$set": {"novelName": novel_name, "chapterNumber": ch_num,
                   "title": title, "content": body,
                   "wordCount": word_count, "version": "v1"}},
        upsert=True
    )
    total_words += word_count

# 5. 更新字数
novel_db.novels.update_one(
    {"title": novel_name},
    {"$set": {"stats.words": total_words, "stats.chapters": len(ch_files),
               "updatedAt": datetime.now().strftime("%Y-%m-%d")}}
)

# 6. 同步大纲
outline_pattern = re.compile(r'.*完整大纲.*\.md$')
outline_files = [f for f in os.listdir(OUTPUT_DIR) if outline_pattern.match(f)]
if outline_files:
    with open(os.path.join(OUTPUT_DIR, outline_files[0]), encoding='utf-8') as f:
        outline_content = f.read()
    factory_db.arcs.update_one(
        {"project_id": novel_name, "arc_id": "ARC-001"},
        {"$set": {"outline": outline_content[:10000],
                   "source_file": outline_files[0],
                   "updated_at": datetime.now()}},
        upsert=True
    )
    print(f"  → arcs 集合更新: ARC-001 ({len(outline_content)}字大纲)")

# 7. 同步角色
char_pattern = re.compile(r'.*角色体系.*\.md$')
char_files = [f for f in os.listdir(OUTPUT_DIR) if char_pattern.match(f)]
if char_files:
    with open(os.path.join(OUTPUT_DIR, char_files[0]), encoding='utf-8') as f:
        char_content = f.read()
    for block in char_content.split('## '):
        if not block.strip(): continue
        lines = block.strip().split('\n')
        char_name = lines[0].strip().rstrip('（').rstrip('(').strip()
        if char_name:
            factory_db.characters.update_one(
                {"project_id": novel_name, "name": char_name},
                {"$set": {"project_id": novel_name, "name": char_name,
                           "description": '\n'.join(lines[1:]).strip()[:2000],
                           "updated_at": datetime.now()}},
                upsert=True
            )

print(f"\n✅ MongoDB 持久化完成: {len(ch_files)} 章, {total_words} 字")
print(f"   novel.chapters → {novel_db.chapters.count_documents({'novelName': novel_name})} 条")
print(f"   novel.novels   → 1 条")
