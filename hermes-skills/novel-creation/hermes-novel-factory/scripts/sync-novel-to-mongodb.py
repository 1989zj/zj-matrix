#!/usr/bin/env python3
"""
novel-factory 产出 → MongoDB novel 库 同步脚本

用法:
  python3 sync-novel-to-mongodb.py --proj-dir <slug>

  <slug> = /root/novel-factory/ 下的项目目录名，如 ni-sheng-zhi-yu

功能:
  - 读取 /root/novel-factory/<slug>/draft/chapter-*.md 文件
  - 读取 /root/novel-factory/<slug>/ops/summary.md 提取梗概
  - 读取 /root/novel-factory/<slug>/outline.md 提取角色和章节标题
  - 写入 novel.novels + novel.chapters 集合
  - 格式与已有小说完全一致
"""
import pymongo, os, re, sys, json
from datetime import datetime

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/novel?authSource=admin"
BASE_DIRS = ["/root/novel-factory", "/root/zj-matrix/novel-factory"]

# --- 解析参数 ---
proj_dir = None
for i, arg in enumerate(sys.argv[1:]):
    if arg == '--proj-dir' and i + 1 < len(sys.argv) - 1:
        proj_dir = sys.argv[i + 2]
        break

if not proj_dir:
    print("用法: python3 sync-novel-to-mongodb.py --proj-dir <slug>")
    print("\n可用项目：")
    seen = set()
    for base in BASE_DIRS:
        if not os.path.isdir(base):
            continue
        for d in sorted(os.listdir(base)):
            if d.startswith('.'):
                continue
            dp = os.path.join(base, d)
            if not os.path.isdir(dp) or d in seen:
                continue
            seen.add(d)
            found = []
            for sub in ['draft', 'chapters']:
                sd = os.path.join(dp, sub)
                if os.path.isdir(sd):
                    found.extend(f for f in os.listdir(sd) if f.endswith('.md'))
            print(f"  {d} ({len(found)} 章)")
    sys.exit(1)

# 尝试所有 base dir
proj_path = None
for base in BASE_DIRS:
    candidate = os.path.join(base, proj_dir)
    if os.path.isdir(candidate):
        proj_path = candidate
        break

if not proj_path:
    print(f"错误: 项目目录 {proj_dir} 不在以下路径中:")
    for base in BASE_DIRS:
        print(f"  {base}")
    sys.exit(1)

# 支持 draft/ 和 chapters/ 两种目录结构
draft_dir = os.path.join(proj_path, 'draft')
chapters_dir = os.path.join(proj_path, 'chapters')
if os.path.isdir(draft_dir):
    src_dir = draft_dir
elif os.path.isdir(chapters_dir):
    src_dir = chapters_dir
else:
    print(f"错误: 未找到草稿目录 (draft/ 或 chapters/)")
    sys.exit(1)

# --- 读取章节文件（支持两种命名格式） ---
ch_files = sorted(
    [f for f in os.listdir(src_dir) if re.match(r'(?:chapter-|ch)\d+', f)],
    key=lambda x: int(re.search(r'\d+', x).group())
)

if not ch_files:
    print("错误: 未找到任何章节文件")
    sys.exit(1)

chapters = {}
for fn in ch_files:
    ch_num = int(re.search(r'\d+', fn).group())
    with open(os.path.join(src_dir, fn), 'r', encoding='utf-8') as f:
        chapters[ch_num] = f.read()

print(f"读取 {len(chapters)} 个章节文件")

# --- 提取小说名 ---
novel_name = ""

# 方法1: 从 ops/synopsis.md 或 ops/summary.md 提取《》中的书名
summary_paths = [
    os.path.join(proj_path, 'ops', 'synopsis.md'),
    os.path.join(proj_path, 'ops', 'summary.md'),
]
# 也检查 blurb.md 和 cover-copy.md 有无书名
blurb_path = os.path.join(proj_path, 'ops', 'blurb.md')
cover_path = os.path.join(proj_path, 'ops', 'cover-copy.md')

for sp in summary_paths + [blurb_path, cover_path]:
    if os.path.exists(sp):
        with open(sp, 'r', encoding='utf-8') as f:
            st = f.read()
        m = re.search(r'《(.+?)》', st)
        if m:
            novel_name = m.group(1).strip()
            break

# 方法2: 从 outline.md 提取《》中的书名
if not novel_name:
    outline_path = os.path.join(proj_path, 'outline.md')
    if os.path.exists(outline_path):
        with open(outline_path, 'r', encoding='utf-8') as f:
            ot = f.read()
        m = re.search(r'《(.+?)》', ot)
        if m:
            novel_name = m.group(1).strip()

# 方法3: 从 proj_dir 反向生成（ni-sheng-zhi-yu → 你生治愈 → 不行，用固定规则映射）
if not novel_name:
    # 常见 slug 映射
    slug_map = {
        'ni-sheng-zhi-yu': '深夜小馆的温暖守则',
    }
    novel_name = slug_map.get(proj_dir, '')

# 方法4: fallback 到第一章的第一行（去掉 #）
if not novel_name:
    first_ch = chapters[min(chapters.keys())]
    first_line = first_ch.split('\n')[0]
    novel_name = re.sub(r'^#+\s*第?\d*章?[\s:：]*', '', first_line).strip()
    novel_name = novel_name or proj_dir

# --- 读取概要 ---
synopsis = ""
desc = ""
for sp in summary_paths:
    if os.path.exists(sp):
        with open(sp, 'r', encoding='utf-8') as f:
            st = f.read()
        lines = [l.strip() for l in st.split('\n') if l.strip()]
        if lines:
            # 去掉标题行（以 # 开头或以 《》开头）
            body = [l for l in lines if not l.startswith('#') and not l.startswith('《')]
            if body:
                synopsis = body[0][:2000]
                break

# 如果没有 synopsis，fallback: 从 blurb.md 取全部内容
if not synopsis and os.path.exists(blurb_path):
    with open(blurb_path, 'r', encoding='utf-8') as f:
        synopsis = f.read().strip()[:2000]

# blurb 内容也作为 description
if os.path.exists(blurb_path):
    with open(blurb_path, 'r', encoding='utf-8') as f:
        desc = f.read().strip()[:500]
print(f"提取概要: {len(synopsis)} 字, description: {len(desc)} 字")

# --- 读取大纲获取章节标题 ---
outline_path = os.path.join(proj_path, 'outline.md')
chapter_titles = {}
if os.path.exists(outline_path):
    with open(outline_path, 'r', encoding='utf-8') as f:
        ot = f.read()
    # 找章节标题表 | 01 | 深夜十点 | ...
    tbl_pattern = re.findall(r'\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|', ot)
    for num_str, title in tbl_pattern:
        num = int(num_str)
        title = title.strip()
        if 1 <= num <= 999:
            chapter_titles[num] = title
    print(f"提取 {len(chapter_titles)} 个章节标题")

# --- 提取角色 ---
characters = []
if os.path.exists(outline_path):
    with open(outline_path, 'r', encoding='utf-8') as f:
        ot = f.read()
    # 找角色表格
    char_pattern = re.findall(
        r'\|\s*\*\*(.+?)\*\*（主角）?\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|',
        ot
    )
    if not char_pattern:
        # 更宽松的匹配
        char_pattern = re.findall(
            r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|',
            ot
        )
    for name, role, desc, arc in char_pattern[:10]:
        characters.append({
            'name': name.strip(),
            'title': role.strip(),
            'desc': desc.strip()[:200],
            'traits': []
        })

if not characters:
    # fallback: 从 outline 的人物关系图提取
    char_names = re.findall(r'\|\s*\|?\s*(林暖|苏晚|陈远山|沈悦|顾深|林远|陆瑶|方晴|赵铁|顾晚|陈叔|老钱)', outline_path if 'outline_path' in dir() else '')
    for n in set(char_names):
        characters.append({'name': n, 'title': '', 'desc': '', 'traits': []})

print(f"提取 {len(characters)} 个角色")

# --- 写入 MongoDB ---
try:
    db = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)['novel']
    db.command('ping')
except Exception as e:
    print(f"错误: MongoDB 连接失败 — {e}")
    sys.exit(1)

# 确定小说名
if not novel_name or len(novel_name) > 30:
    novel_name = proj_dir.replace('-', '的').replace('_', '的')

# 生成 slug（拼音化，与其他小说格式一致）
# 常用汉字→拼音映射（持续扩充）
PINYIN_MAP = {
    '凌':'ling','晨':'chen','站':'zhan','台':'tai','的':'de','访':'fang','客':'ke',
    '我':'wo','的':'de','第':'di','一':'yi','部':'bu','小':'xiao','说':'shuo',
    '末':'mo','世':'shi','污':'wu','染':'ran','等':'deng','级':'ji','比':'bi','高':'gao',
    '诡':'gui','异':'yi','游':'you','戏':'xi','规':'gui','则':'ze','别':'bie','人':'ren','看':'kan','不':'bu','见':'jian',
    '离':'li','婚':'hun','后':'hou','在':'zai','花':'hua','店':'dian','找':'zhao','到':'dao','了':'le','自':'zi','己':'ji',
    '钱':'qian','就':'jiu','返':'fan','利':'li','开':'kai','局':'ju','买':'mai','水':'shui','三':'san','亿':'yi',
    '深':'shen','夜':'ye','馆':'guan','温':'wen','暖':'nuan','守':'shou',
    '零':'ling','点':'dian','午':'wu','入':'ru','口':'kou',
    '记':'ji','忆':'yi','删':'shan','除':'chu','公':'gong','司':'si',
    '暗':'an','面':'mian','真':'zhen','相':'xiang','伤':'shang','痛':'tong',
    '接':'jie','纳':'na','完':'wan','整':'zheng',
    '母':'mu','亲':'qin','告':'gao','别':'bie','带':'dai','着':'zhe','去':'qu','爱':'ai',
    '林':'lin','暖':'nuan','晓':'xiao','川':'chuan','远':'yuan','陆':'lu','陈':'chen',
    '苏':'su','晚':'wan','秦':'qin','若':'ruo','云':'yun','阿':'a','老':'lao',
    '蒋':'jiang','言':'yan','青':'qing',
}
slug_parts = []
for ch in novel_name:
    if ch in PINYIN_MAP:
        slug_parts.append(PINYIN_MAP[ch])
    elif re.match(r'[a-zA-Z0-9]', ch):
        slug_parts.append(ch.lower())
    elif ch in '·':
        slug_parts.append('-')
slug = '-'.join([p for p in slug_parts if p]) if slug_parts else proj_dir
slug = re.sub(r'-+', '-', slug).strip('-')

# 检查是否已存在
existing = db.novels.find_one({'name': novel_name})
if existing:
    print(f"小说 \"{novel_name}\" 已存在，将更新章节")
    novel_id = existing['_id']
    # 保留已有元数据
    existing_characters = existing.get('characters', [])
    if existing_characters:
        characters = existing_characters if len(existing_characters) >= len(characters) else characters
    existing_tags = existing.get('tags', [])
    existing_genre = existing.get('genre', '')
    existing_tags = existing.get('tags', [])
else:
    novel_id = None
    existing_genre = ''
    existing_tags = []

# 确定体裁/标签
# 如果新颖（无已有），使用通用默认值
genre = existing.get('genre', '') if existing else ''
if not genre:
    genre = '虚构'
tags = existing.get('tags', []) if existing else []
if not tags:
    tags = ['小说', '情感']

# 总字数
total_words = sum(len(c) for c in chapters.values())

# 插入/更新 novels
if novel_id:
    db.novels.update_one(
        {'_id': novel_id},
        {'$set': {
            'stats.words': total_words,
            'stats.chapters': len(chapters),
            'stats.status': '已完结',
            'synopsis': synopsis or existing.get('synopsis', ''),
            'description': desc or existing.get('description', ''),
            'updatedAt': datetime.utcnow()
        }}
    )
    print(f"更新 novels: {novel_name}")
else:
    novel_doc = {
        'name': novel_name,
        'title': novel_name,
        'author': '',
        'genre': genre,
        'slug': slug,
        'synopsis': synopsis or '暂无简介',
        'description': desc or '',
        'tags': tags,
        'target': '番茄小说',
        'characters': characters,
        'world': {},
        'stats': {
            'words': total_words,
            'chapters': len(chapters),
            'status': '已完结'
        },
        'updatedAt': datetime.utcnow()
    }
    result = db.novels.insert_one(novel_doc)
    novel_id = result.inserted_id
    print(f"新建 novels: {novel_name} (id={novel_id})")

# 写入章节
inserted = 0
updated = 0
for ch_num in sorted(chapters.keys()):
    content = chapters[ch_num]
    ch_title = chapter_titles.get(ch_num, '')
    if not ch_title:
        # 从文件第一行提取
        first_line = content.split('\n')[0]
        ch_title = re.sub(r'^#+\s*第\d+章[:：]?\s*', '', first_line).strip()
        ch_title = ch_title or f'第{ch_num}章'
    full_title = f'第{ch_num}章 {ch_title}' if not ch_title.startswith(f'第{ch_num}章') else ch_title
    filename = f'ch{ch_num:03d}_{ch_title}.md'

    result = db.chapters.update_one(
        {'novelName': novel_name, 'chapterNumber': ch_num},
        {'$set': {
            'novelName': novel_name,
            'chapterNumber': ch_num,
            'title': full_title,
            'filename': filename,
            'content': content,
            'chapterEndNotes': '',
            'version': 'v1',
            'wordCount': len(content)
        }},
        upsert=True
    )
    if result.upserted_id:
        inserted += 1
    else:
        updated += 1

print(f"章节: {inserted} 新建, {updated} 更新")

# 验证
final_novel = db.novels.find_one({'name': novel_name})
final_chs = db.chapters.count_documents({'novelName': novel_name})
print(f"\n✅ MongoDB 同步完成: \"{novel_name}\"")
print(f"   novels: {final_chs} 章, {final_novel['stats']['words']} 字")
print(f"   characters: {len(final_novel.get('characters', []))} 个")
