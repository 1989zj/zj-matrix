# Legacy Novel Review — Reference

Complete workflow for extracting a novel from MongoDB and running the 5-angle review pipeline. Derived from the 80-chapter / 276K-word audit of 《末世：我的污染等级比怪物高》.

## 1. Extract from MongoDB

```python
import pymongo, os, json

# Connect (correct host is 192.168.2.30, not 2.47)
client = pymongo.MongoClient("mongodb://mongo_8F6dTZ:<password>@192.168.2.30:27017/")
db = client['novel']

# Find the novel — check both names and title
novel = db['novels'].find_one({"$or": [
    {"name": "我的第一部小说"},
    {"title": "末世：我的污染等级比怪物高"}
]})

novel_name = novel['name']  # internal key for chapters lookup
print(f"Internal name: {novel_name}")
print(f"Published title: {novel.get('title')}")
print(f"Stats: {novel.get('stats')}")

# Extract all chapters with content, sorted by chapterNumber
chapters = list(db['chapters'].find(
    {"novelName": novel_name, "content": {"$ne": ""}},
    sort=[("chapterNumber", 1)]
))

outdir = "/root/.hermes/projects/<project-review>"
os.makedirs(outdir, exist_ok=True)

for c in chapters:
    fn = f"ch{c['chapterNumber']:03d}_{c.get('title','').replace(' ','')}.md"
    fpath = os.path.join(outdir, fn)
    content = c.get('content', '')
    header = f"# 第{c['chapterNumber']}章 {c.get('title','')}\n\n"
    with open(fpath, 'w') as f:
        f.write(header + content)
    print(f"  {c['chapterNumber']:03d}: {c.get('title')} ({c.get('wordCount',0)}字)")

# Also export novel meta
def serialize(obj):
    if isinstance(obj, (list, dict)):
        return {k: serialize(v) for k, v in obj.items()} if isinstance(obj, dict) else [serialize(i) for i in obj]
    return str(obj) if not isinstance(obj, (str, int, float, bool, type(None))) else obj

with open(os.path.join(outdir, "_novel_meta.json"), 'w') as f:
    json.dump(serialize(novel), f, ensure_ascii=False, indent=2)

print(f"\nDone. {len(chapters)} chapters → {outdir}")
```

## 2. Concatenate

```python
import os, glob

indir = "/root/.hermes/projects/<project-review>"
files = sorted(glob.glob(os.path.join(indir, "ch*.md")),
              key=lambda x: int(x.split('/')[-1].split('_')[0].replace('ch','')))

meta = open(os.path.join(indir, "_novel_meta.json")).read()
parts = [f"# 小说元数据\n\n{meta}\n\n---\n\n"]
for fpath in files:
    parts.append(open(fpath).read())
    parts.append("\n\n---\n\n")

outpath = os.path.join(indir, "_full_novel.md")
with open(outpath, 'w') as f:
    f.write("".join(parts))

print(f"Full novel: {len(''.join(parts))} chars, {len(files)} chapters")
```

## 3. Delegate 5 Reviews (2 batches)

### Batch 1 (3 tasks):

Each task uses the same base context:
```
小说全文在 {indir}/_full_novel.md
小说元数据在 {indir}/_novel_meta.json
```

**Task 1 — Structure Review** (`review_structure.md`):
- Story arcs (3-act / 5-act), pacing issues, punch-point density per phase
- Foreshadowing matrix (laid vs recovered vs orphaned)
- Opening chapter analysis (first 500 words)
- Power system clarity and usage
- Output: 5000+ words, markdown

**Task 2 — Character Review** (`review_characters.md`):
- MC arc (complete/varied?), core supporting cast depth
- Antagonist motivation and menace
- Female character toolification check
- Relationship chemistry, OOC detection
- Output: 3000+ words, with per-character rating table

**Task 3 — Writing Review** (`review_writing.md`):
- Opening hook power, POV discipline (no head-hopping)
- Dialogue quality (functional vs natural, subtext)
- Description/action balance, prose technique
- Chapter hook strength per phase, repetitive language patterns
- Output: 3000+ words, with quotes

### Batch 2 (2 tasks):

**Task 4 — Compliance Review** (`review_compliance.md`):
- 404 redlines (politics, history, religion, territory)
- Graphic violence / gore level
- Sexual content
- Value orientation (positive energy)
- Platform scoring (90-100 safe, 70-89 low risk, <70 modify)
- Output: 2000-3000 words with specific flagged passages

**Task 5 — Market Review** (`review_market.md`):
- Genre competition analysis (primary + subgenre + intersection)
- Title/synopsis evaluation with optimization suggestions
- Comparable works benchmarking
- Monetization path: paid (Qidian) vs free (Tomato) vs audio vs comic
- Word count viability analysis
- Revenue estimation (monthly, total)
- Output: 3000-4000 words

## 4. Synthesize _MASTER_REVIEW.md

Read all 5 reports, extract: composite score, top 3-5 strengths, prioritized issues (🔴🟡🟢), commercial verdict, P0/P1/P2 action items.

## 5. Upload to GitHub

Use GitHub Content API (not git CLI — observed timeout >120s).

```python
import base64, json

token = "<from git credential>"
repo = "1989zj/zj-matrix"
branch = "master"  # NOTE: Repo branch is 'master', not 'main'
path_prefix = f"novel/<review-dir>/"

for filename in ["_MASTER_REVIEW.md", "review_structure.md", ...]:
    content = open(os.path.join(indir, filename)).read()
    
    # Check existing file for SHA
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/contents/{path_prefix}{filename}",
        headers={"Authorization": f"token {token}"}
    )
    sha = resp.json().get('sha') if resp.ok else None
    
    payload = {
        "message": f"评审报告: {filename}",
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch
    }
    if sha:
        payload["sha"] = sha
    
    resp = requests.put(
        f"https://api.github.com/repos/{repo}/contents/{path_prefix}{filename}",
        json=payload,
        headers={"Authorization": f"token {token}"}
    )
```

## Common Findings from 80-Chapter Audit (reusable as baselines)

| Finding | Frequency | Severity |
|---------|-----------|----------|
| 前后体量失衡（early >70%, climax <12%） | Common in multi-arc novels | 🔴 High |
| 女性配角工具化（能力线未回收） | Common | 🟡 Medium |
| 中期疲劳段（信息密度高但情感张力低） | Common | 🟡 Medium |
| 对话缺乏潜台词（一问一答功能型） | Common in action-focused genres | 🟢 Low |
| 伏笔未回收（3+条） | Common in first drafts | 🟡 Medium |
| 27.6万字商业天花板 | Structural | 🔴 High |
