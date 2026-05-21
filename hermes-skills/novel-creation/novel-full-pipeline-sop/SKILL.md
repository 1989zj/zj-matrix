---
name: novel-full-pipeline-sop
description: NovelOS 全流程 SOP — 从创建、数据重建、精修、评审到反馈循环的完整工作流。覆盖 hermes-novel-factory / novel-reconstruction / novel-refinement-branch / novel-review-pipeline 四阶段联动。
version: 1.0.0
tags: [novel, pipeline, sop, workflow, creation, review, refinement, reconstruction]
---

# NovelOS 全流程 SOP

> 从零创建 → 数据重建 → 内容精修 → 独立评审 → 反馈循环 → 发布就绪

## 前置条件

- MongoDB `novel` + `novel_factory` 库可访问
- 四个 skill 就位：`hermes-novel-factory`、`novel-reconstruction`、`novel-refinement-branch`、`novel-review-pipeline`

## 阶段 1：创建小说（Creation）

**skill: hermes-novel-factory**

### 1.1 新项目启动

```bash
# 创建新小说骨架（Research/Outline/Character + 开头3万字）
novel-factory new '小说名' --genre 玄幻

# 产出写入:
#   MongoDB novel_factory: projects, chapters, characters, arcs, ...
#   MongoDB novel: novels (name, title, genre, synopsis), chapters (content)
```

### 1.2 续写章节

```bash
# 每轮写 3-5 章，约 4.5分钟/轮
novel-factory continue '小说名'
```

### 1.3 创作规范

- `new` 只做项目骨架（Research/Outline/Character/Draft 开头几章）
- `continue` 做后续章节续写，每轮不超 5 章
- 超时处理 600s：如果 `new` 超时，检查是否生成了部分数据，用 `continue` 接上
- 所有产出**必须**同时写 MongoDB novel_factory（结构化数据） + novel（novels/chapters 集合）

---

## 阶段 2：数据重建（Reconstruction）

**skill: novel-reconstruction**

当 MongoDB 存在脏数据（字段不匹配、元数据缺失、关联断裂）时执行。一次性操作，不修改正文。

### 2.1 诊断（dry-run）

```bash
cd ~/.hermes/skills/content-creation/novel-reconstruction/scripts/
python3 novel-reconstruct.py run '小说名' --module all --dry-run
```

查看健康评分，确认缺失模块。

### 2.2 执行重建

```bash
# 全量重建
python3 novel-reconstruct.py run '小说名' --module all
```

### 2.3 重建模块列表

| 模块 | 修复内容 | 说明 |
|------|---------|------|
| chapter_memory | 每章摘要、Hook、Timeline | 从 chapters 内容自动提取 |
| timeline | 章节-事件关联 | 每章至少一个时间线事件 |
| foreshadow | 伏笔字段映射 | description→content, callback_chapter→suggested_callback_ch |
| foreshadow_queue | 伏笔队列重建 | urgency enum (low/medium/high/critical) 不含 emoji |
| event_log | 事件日志 | timestamp 必须是 datetime 对象 |
| arcs | ARC 元数据 | 使用 title（非 name）、无 chapters 数组 |
| canonical_bible | 世界观圣经 | 所有设定字段为数组类型 |
| character_states | 角色状态机 | 需 LLM 提取（可选模块） |

### 2.4 已知踩坑（字段映射）

```
novel_factory 字段       → 脚本中应使用的字段
description (foreshadow)  → content
callback_chapter          → suggested_callback_ch  
category (foreshadow)     → type
arcs[].name               → arcs[].title
event_log.timestamp type  → datetime 对象（非字符串）
mongo URI auth            → 需加 ?authSource=admin
```

### 2.5 重建后检查

- chapter_memory: 章节数 = 总章数
- timeline: 每章有关联
- foreshadow: 活跃伏笔 > 0
- foreshadow_queue: 队列完整
- event_log: 条目数 ~ 章节数
- arcs: 每个有 title
- canonical_bible: 已编译

---

## 阶段 3：内容精修（Refinement）

**skill: novel-refinement-branch**

内容级别的修复。只做局部 Patch，不全文重写。保存 original/patched/diff 三联。

### 3.1 精修范围

- Phase 1 — **一致性修复**：角色名统一、设定冲突消除、时间线对齐
- Phase 2 — **语言润色**：AI味消除（重复句式、空洞描写、机械情绪）、句式优化、节奏调整
- Phase 3 — **伏笔回收**：foreshadow_queue 冲销、ARC 收束

### 3.2 执行

```bash
# 加载 skill 后按提示执行
# 每个精修任务输出:
#   1. original 原文
#   2. patched 修改后
#   3. diff 差异追踪
# 回写前需确认
```

### 3.3 精修规范

- **不脑补**：不新增情节/角色/设定
- **局部修复**：指定章节、段落、精确到句
- **确认回写**：diff 审核通过后落盘到 MongoDB
- **OOM 处理**：MongoDB 连接完释放，内存吃紧时用 fuser -k 5003/tcp

### 3.4 精修后：同步 chapter_memory 摘要

精修改进了 `novel.chapters.content` 字段后，`novel_factory.chapter_memory` 的摘要并未同步更新。下游评审系统（Phase 4）依赖 `chapter_memory.summary` 做评估，导致评审无法识别精修成果。

**必须在精修后执行**：

```python
import pymongo
from datetime import datetime, timezone

c = pymongo.MongoClient('...')
nf = c['novel_factory']
for ch_num in patched_chapters:
    # 从更新后的正文提取新摘要
    ch_content = novel['chapters'].find_one({...})['content']
    new_summary = generate_summary(ch_content)
    new_hook = extract_hook(ch_content[-200:])
    
    nf['chapter_memory'].update_one(
        {'project_id': pid, 'chapter': ch_num},
        {'$set': {
            'summary': new_summary,
            'hook': new_hook,
            'last_refined': datetime.now(timezone.utc)
        }}
    )
```

如使用 LLM 生成摘要，直接将更新写入 chapter_memory 后再跑评审。

---

## 阶段 4：独立评审（Review）

**skill: novel-review-pipeline**

评审 Agent 独立于创作 Agent，只判不改。

### 4.1 执行评审

```bash
cd ~/.hermes/skills/content-creation/novel-review-pipeline/scripts/

# 黄金三章高规格
python3 novel-judge.py review '小说名' --chapters 1-3 --golden

# 全量评审
python3 novel-judge.py review '小说名' --chapters 1-136

# 只看裁决
python3 novel-judge.py review '小说名' --verdict-only

# 只看特定维度
python3 novel-judge.py review '小说名' --dimension hook,ai_smell,market
```

### 4.2 八维评审体系

| 维度 | 权重 | 评分方式 | 黄金三章标准 |
|------|------|---------|------------|
| Hook | 25% | 关键词+密度 | < 4 直接打回 |
| Retention | 20% | 模式匹配 | 章末必须强钩子 |
| Pacing | 15% | 事件/冲突密度 | 前500字必须有冲突/爽点 |
| Emotion | 10% | 情绪词匹配 | 常规标准 |
| AI Smell | 10% | 正则规则（纯机械） | 3倍检查 |
| Character Charm | 10% | 五维检测 | 常规标准 |
| Market | 5% | 平台关键词匹配 | 参考 |
| Readability | 5% | 句式分析 | 参考 |

### 4.3 裁决标准

| 加权得分 | 裁决 | 说明 |
|---------|------|------|
| >= 8 | PASS | 可直接发布 |
| 6-8 (黄金三章) / 5-7 (普通) | CONDITIONAL_PASS | 修完优化项再发 |
| < 6 (黄金三章) / < 5 (普通) | REJECT | 打回精修 |

---

## 阶段 5：反馈循环（Feedback Loop）

> 核心：评审发现问题 → 生成 Patch → 精修执行 → 再评审 → 直到通过

### 5.1 完整循环

```
① Review → 发现 hook_score=1.8 ❌
② 生成 Rewrite Patches（局部修复建议）
   → "ch1: 前500字增加冲突/悬念钩子"
   → "ch2: 章末补充疑问句制造追读动力"
③ Refinement 执行 Patch
   → 读取对应章节正文
   → 精确到段落/句子修改
   → 保存 original/patched/diff
   → 确认后回写 MongoDB
④ 再次 Review 该章节
⑤ verdict=PASS? → 合入主线
   verdict=REJECT? → 回到②（最多3轮）
   3轮不通过 → 标记"需人工介入"
```

### 5.2 停止条件

- ✅ **PASS**：章节标记 `status: reviewed`，进入发布就绪队列
- 🔶 **CONDITIONAL_PASS**：标记 `status: conditional` + 待优化清单，可先发布
- ❌ **3轮 REJECT**：标记 `status: needs_human`，暂停自动化，等待人工干预

---

## 阶段 6：发布（Release）

当所有章节达到 PASS 状态时：

```
① 最终全量评审确认
② 从 MongoDB 导出完整正文
③ 按平台格式输出（番茄/起点/女频适配）
④ 发布于目标平台/本地存储
```

---

## 快速参考：一条命令跑多久？

| 操作 | 预估耗时 | 说明 |
|------|---------|------|
| novel-factory new | ~10分钟 | 3万字骨架 |
| novel-factory continue (3-5章) | ~4.5分钟 | 续写 |
| Phase 0 重建（136章） | ~2分钟 | 机械化 |
| 全量评审（136章） | ~30秒 | 机械化规则 |
| 单章精修（LLM） | ~1分钟 | 含 diff 审核 |
| 反馈循环（1章） | ~3分钟 | 评审+精修+再审 |

## 关键原则（必须遵守）

1. **裁判与修理工分离** — Review 不改文，Refinement 不判分
2. **禁止全文重写** — 局部 Patch 优先
3. **MongoDB 唯一真相源** — 所有数据落盘在 MongoDB
4. **Append-only event log** — 不删不改历史记录
5. **前3章不是普通章节，是广告页** — 超高规格评审
6. **3 轮不通过 = 停，等人** — 防止无限循环消耗 token
