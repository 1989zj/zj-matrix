---
name: novel-refinement-branch
description: V3 Refinement Pipeline — Patch-based chapter refinement branch for Hermes Novel Factory. Covers consistency fixes, lore sync, foreshadow backfill, dialogue voice refinement, and prose enhancement. Includes hard-learned anti-patterns from 7 rounds of iterative refinement with LLM-generated patches.
version: 2.0.0
tags: [novel, refinement, patch, diff, lore, continuity, foreshadow, consistency, prose-enhance, dialogue-voice, anti-patterns]
---

# Refinement Branch — 小说精修分支

> **核心理念**: 精修不是重写, 是修补与增强。
> 精修系统不拥有"世界真相"——世界真相始终来自 Creation Core。
> 精修只提 Patch, 不直接改设定。

## ⚠️ 前置条件: 必须先跑 Phase 0 (Novel Reconstruction)

**精修前数据必须是干净的。** 如果脏数据直接进精修:

| 问题 | 后果 |
|------|------|
| 角色没身份数据 | 精修 Agent 使用旧/错误的 Bible → 越修越乱 |
| 章节没 timeline | 无法判断事件先后 → 时间线错乱 |
| 角色状态空 | state machine 无法工作 → 续写崩 |
| 伏笔未登记 | 精修时忽略伏笔 → 漏修 |
| ARC 数据残 | 精修范围判断错误 → 修错章节 |

**正确顺序:**
```
Phase 0: Novel Reconstruction (novel-reconstruction skill) ← 必须先做
Phase 1: Consistency Repair (本 skill)
Phase 2: Narrative Enhancement (本 skill)
Phase 3: Lore Synchronization (本 skill)
```

先运行 `python3 novel-reconstruct.py run '小说名' --module all` 确保数据完整后再进入本 skill。见 `content-creation/novel-reconstruction`。

## 架构位置

```
Novel System
├── Creation Pipeline (创作主线)
│   └── hermes-novel-factory (skill)
│       ├── world-bible
│       ├── character-db / character-states
│       ├── timeline / event-log
│       ├── chapter-planner / arc-manager
│       ├── state-manager / snapshot-store
│       └── memory-manager / anti-fatigue
│
└── Refinement Pipeline (精修支线) ← NOW
    └── novel-refinement-branch (skill)
        ├── refine-chapter.py      # 主调度器 (Router)
        ├── state-diff.py          # Diff 记录器
        ├── lore-corrector.py      # 设定同步检测
        ├── continuity-patch.py    # 一致性修复 (即将)
        ├── foreshadow-repair.py   # 伏笔回补 (即将)
        └── prose-enhancer.py      # 微润色 (即将)
```

## 精修三原则

1. **读取已有小说状态** — 从 MongoDB novel_factory 读取最新 Bible/角色/时间线/伏笔
2. **对指定章节做局部修正** — 生成 Patch 而非重写
3. **回写系统状态** — 通过 diff 记录变更, 不污染原始数据

## 精修分类

### 第一类: Consistency Refinement (一致性修复) — "修 Bug"

优先级最高, 因为影响根基。

| 子类 | 检测内容 | 严重度 |
|------|---------|--------|
| 角色称呼错误 | 主角被误称为相反性别/身份 | critical |
| 已死角色复活 | 已死亡角色在后续章节出场 | critical |
| 时间线矛盾 | 同一章出现"三天后"又"第二天" | warning |
| 战力崩坏 | 角色使用未设定能力/过早使用高阶能力 | warning |
| 地点冲突 | 同一地点描述不一致 | warning |

### 第二类: Narrative Enhancement (叙事增强) — "提升可读性"

不改变剧情走向。

| 子类 | 检测内容 |
|------|---------|
| AI味词过多 | "仿佛/似乎/好像"高频出现 |
| 废话词组 | "说实话/说白了/不得不说" |
| 对话比例过高 | 叙述占比 <40% |
| 章末悬念弱 | 结尾缺乏钩子 |
| 章节过短/长 | <1500 字或 >5000 字 |
| 重复句式 | 相同句式连续出现 |

### 第三类: Lore Synchronization (设定同步) — "后期反哺前文"

最容易忽略但最考验系统设计。

| 场景 | 说明 |
|------|------|
| 新增设定 | 后期新增修炼等级/势力/能力 → 前文需补充提及 |
| 规则变更 | Bible 中明确"金丹后无法飞行" → 前文筑基飞天的段落需修正 |
| 隐藏设定 | "系统存在隐藏等级" → 前文需轻微埋伏笔 |
| 伏笔回补 | 第80章"黑戒指是魔器" → 前50章需补轻微异常描写 |

### 第四类: Dialogue Voice Refinement (对话声音重塑) — 最高ROI策略

> **核心发现**: 经过 7 轮、30+ 次 patch 的实测对比，**对话声音重塑是所有精修策略中净收益最高的**。只改 `「」` 内的对话文字，不动叙述，5 条手术级修改即可提升 Character Charm 0.66 分（6.67→7.33），且不产生次生损伤。

**原理：** 角色的根本问题通常是**对话同质化**——所有角色说话听起来一样。小说明明有 6-8 个角色，但他们的对话声音几乎无法区分。

**策略步骤：**
1. **提取含说话人的对话** — 用正则覆盖两种中文对话模式：
   - 模式 A: `角色说：「对话内容。」`
   - 模式 B: `「对话内容。」角色说`
2. **为每个角色定义声音特征**（见下方角色声音模板）
3. **LLM 重写对话** — 保留剧情信息，只改说话方式
4. **单次 ≤5 条** — 每轮不超过 5 句对话修改，过多(>5)会触发次生效应

**角色声音模板（实用中文小说）:**

| 角色类型 | 说话特征 | 示例 |
|---------|---------|------|
| 主角（冷静分析型） | 短句、逻辑词、数字类比、不骂人 | "概率上，90%会触发陷阱。" |
| 莽撞型（工兵/武者） | 单字开头（啧/操/滚）、脏话语气词、动词多 | "啧。这门他妈的有问题。" |
| 胆小型（路人/年轻人） | 重复、自打断、音调高 | "啊？我、我刚才……不是，别别别——" |
| 神秘型（导师/长者） | 完整句子、停顿、用词正式 | "规则变了。或者说，它们本来就是这样。" |
| 专业型（医生/学者） | 怀疑式表达（更像是/看起来）、用词精确 | "这不是病，更像是某种应激反应。" |
| 轻声型（学生/文静） | 轻、不确定、句尾上扬 | "呃……你是说……可能吗？" |

## 数据模型

### refinement_patches (补丁集合)

```json
{
  "project_id": "proj_xxx",
  "patch_id": "uuid",
  "chapter": 52,
  "patch_type": "lore" | "continuity" | "foreshadow" | "prose" | "pacing" | "dialogue_voice",
  "sub_type": "title_mismatch" | "ai_smell" | "character_voice" | "...",
  "status": "draft" | "proposed" | "applied" | "rejected" | "merged",
  "severity": "info" | "warning" | "critical",
  "reason": "角色称呼错误: 林远被误称为林小姐",
  "location": 1234,
  "context_before": "XXXX",
  "context_after": "XXXX",
  "original_text": "林小姐",
  "proposed_text": "林少",
  "diff": "--- original\n+++ patched\n@@ -1 +1 @@\n-林小姐\n+林少",
  "impact": "low" | "medium" | "high",
  "bible_version": "v3",
  "created_by": "refinement-router",
  "created_at": "ISO datetime",
  "applied_at": null
}
```

### refinement_log (精修日志)

```json
{
  "project_id": "proj_xxx",
  "chapter": 52,
  "current_hash": "sha256 of current content",
  "patch_ids": ["uuid1", "uuid2"],
  "last_refined_at": "ISO datetime",
  "refinement_count": 2
}
```

## 执行流程

```
[精修阶段]

1. 读取章节                    refine-chapter.py analyze
2. 加载最新 Bible              (自动)
3. 对比当前章节状态             (自动)
4. 生成 Patch 提案             → refinement_patches (status=draft)
5. 一致性检查                  lore-corrector.py scan
6. (手工确认后) 应用 Patch     refine-chapter.py apply
5. 提取 Diff                  state-diff.py diff
6. 更新状态                   → refinement_log
7. ⚠️ 同步 chapter_memory 摘要  → 见下方说明
8. 最终审查                    refine-chapter.py status

### 关键：精修后同步 chapter_memory 摘要

精修改进了正文后，`novel_factory.chapter_memory` 的摘要不会自动更新。下游评审系统（novel-review-pipeline）依赖 `chapter_memory.summary` 和 `chapter_memory.hook` 做评分，不更新则评审看不到精修成果。

**精修应用 Patch 后必须执行**：

```python
import pymongo
from datetime import datetime, timezone
c = pymongo.MongoClient('...')
nf = c['novel_factory']
novel = c['novel']

# 对每个精修过的章节
for ch_num in patched_chapters:
    ch = novel['chapters'].find_one({'novelName': name, 'chapterNumber': ch_num})
    content = ch['content']
    
    # 新摘要（取前150字）
    new_summary = content[:150] + '...'
    
    # 章末钩子 — 两种策略选一种：
    # 策略A（快速）: content[-200:] 截取最后一句
    # 策略B（推荐）: 调 LLM 生成 30-80 字悬念钩子（效果显著更好）
    
    nf['chapter_memory'].update_one(
        {'project_id': pid, 'chapter': ch_num},
        {'$set': {
            'summary': new_summary,
            'hook': new_hook,    # 见 scripts/sync-after-refinement.py --llm-hooks
            'last_refined': datetime.now(timezone.utc)
        }}
    )
```

如忽略此步骤，后续评审基于旧摘要给出旧分数，反馈循环不收敛。

**还有两个必做事项：**

1. **修正 wordCount 字段** — Python 脚本直接修改 `novel.chapters.content` 后，`wordCount` 字段不会自动更新，导致统计失准。实测 ch1 从 1691→2354（差 663 字）。
2. **合并元数据更新** — 精修通过后设置 `chapter_memory.status = 'merged'` + 写入 `refinement_log`，标记本轮精修正式合入主线。

**推荐使用配套脚本 `scripts/sync-after-refinement.py` 自动执行以上所有步骤：**

```bash
# 常规同步（只更新 summary/hook/wordCount）
python3 scripts/sync-after-refinement.py '诡异游戏' --chapters 1-3

# 合并+同步（更新+标记 merged+写 log）
python3 scripts/sync-after-refinement.py '诡异游戏' --chapters 1-3 --merge

# 使用 LLM 生成钩子（推荐）— 比启发式截取效果显著更优
python3 scripts/sync-after-refinement.py '诡异游戏' --chapters 1-3 --merge --llm-hooks

# 预览模式
python3 scripts/sync-after-refinement.py '诡异游戏' --chapters 1-3 --merge --dry-run

# 如果某章 LLM 钩子返回空（概率性，约10%），单独重试该章：
python3 sync-after-refinement.py '诡异游戏' --chapters 3 --llm-hooks
```

脚本会自动推导 project_id、检测 wordCount 漂移、生成 summary/hook。

**LLM 钩子 vs 启发式钩子实测对比：**

| 方法 | ch1 | ch2 | ch3 | 平均 |
|------|-----|-----|-----|------|
| 启发式截取 | 44字 | 9字（过短） | 8字（过短） | 20字 |
| LLM 生成 | 44字 | 54字 | 46字 | 48字 |

LLM 钩子的提示词策略：给结尾600字、指定30-80字、明确「不剧透后续」和「无限流·规则怪谈风格」。如果返回空，通常是 LLM 没在尾600字中识别到悬念元素——重试时加一句「提示：尾段中'蛋糕还在冰箱里'这个细节可以成为钩子基点」可解决。
```

## 命令参考

```bash
# 切换到精修工作目录
cd ~/.hermes/skills/content-creation/novel-refinement-branch/scripts/

# 分析章节 (只检查不修改)
python3 refine-chapter.py analyze '诡异游戏' --chapters 1-50
python3 refine-chapter.py analyze '诡异游戏' --chapters 1-136 --full
python3 refine-chapter.py analyze '诡异游戏' --chapters 50-60 --types continuity
python3 refine-chapter.py analyze '诡异游戏' --chapters 1-10 --dry-run  # 只输出不写入

# 查看 Patch 状态
python3 refine-chapter.py status '诡异游戏'

# 设定同步检测
python3 lore-corrector.py scan '诡异游戏' --chapters 1-100
python3 lore-corrector.py bible-diff '诡异游戏'

# 生成 Diff
python3 state-diff.py diff '诡异游戏' --chapter 52 --original ch52_orig.txt --patched ch52_fixed.txt
python3 state-diff.py verify '诡异游戏' --chapter 52
```

## ⚠️ 反模式与硬核教训（v2.0 新增）

### 反模式 11: MongoDB URI 含占位符密码导致脚本无提示失败

**症状**: `scripts/dialogue-voice-refiner.py` 和 `scripts/sync-after-refinement.py` 中硬编码了 `MONGO_URI = 'mongodb://mongo_8F6dTZ:***@192.168.2.30:27017/?authSource=admin'`。`***` 是占位符而非真实密码，脚本运行时不报错但返回空结果（`Found 0 chapters`），因为 MongoDB 连接实际失败。

**对策**:
- 首次部署时 grep 检查所有脚本的 MongoDB URI：`grep -rn '\*\*\*' ~/.hermes/skills/content-creation/novel-refinement-branch/scripts/`
- 替换为真实密码后再运行
- 建议脚本从环境变量 `MONGO_PASSWORD` 读取密码，而非硬编码

### 反模式 12: 批量化运行时 API 超时/空返回

**症状**: 对 11 章运行 `dialogue-voice-refiner.py`，主进程超时（300s 不够），某些章节（如 ch12、ch14、ch15、ch19）反复返回空响应或 API 错误，但隔几分钟重试后又能成功。

**原因**: DeepSeek API 有隐性速率限制或请求队列，短时间密集请求（11 章 × 1-3 次 API 调用/章）会导致部分请求静默丢弃。

**对策**:
- 不要一次跑超过 5 章，推荐 3 章一批
- 批次间 sleep 5-10 秒
- 对返回空的章节，等 10 秒后单独重试
- 使用独立的 retry 脚本（见 `scripts/retry-failed-chapters.py`）
- 恒等退避：失败后 sleep 10→20→40s，最多 3 次

### 反模式 13: apply 阶段静默失败（LLM 说改了但实际没改）

**症状**: `dialogue-voice-refiner.py` 输出 "Applied 11 patches across ch10, ch11, ch13" 但实际 grep 验证发现部分修改不存在。例如「记下了」应改为「记住了」但原文未变。

**原因**: 脚本的 apply 逻辑在锚点匹配时因编码/空格/标点差异匹配失败，但只记录不报错。apply 阶段的 API 错误也被静默吞掉。

**对策**:
- 每次 apply 后必须 grep 验证修改是否生效
- 用脚本验证：`python3 -c "import pymongo;c=pymongo.MongoClient('...');ch=c['novel']['chapters'].find_one(...);print('记下了' in ch['content'])"`
- 如果 patch 未应用，用独立脚本逐个 patch 重试
- 关键操作用 `content.replace('「原文」', '「新文」', 1)` 做精确替换，不依赖 LLM 的 apply 逻辑

以下教训来自 7 轮、30+ 次 LLM 生成 patch 在《诡异游戏》前三章上的真实迭代。每条都有代价。

### 反模式 1: LLM 批量自动 patch 不可靠

**症状**: 每次让 LLM 生成 ≥5 条 batch patch 并自动应用，必然有 ≥1 条产生次生损伤:
- 插入位置错误（太靠近章首/章尾）
- 锚点文本匹配失败
- 改写内容与原语境冲突
- 多个 patch 之间相互影响

**实测数据**: 7 轮中，每轮 LLM patch 后分数在 6.9-7.6 之间震荡，净效果为零。最佳分数 7.6 与原始分数完全相同。

**对策**:
- 单轮 patch 数量 ≤5（不超过大脑能追踪的变更量）
- 每次 patch 后立即跑评审验证
- 不用"replace batch"模式，用"apply one, verify, then next"模式
- LLM 返回的 patch 内容必须逐条检查，不接受批量信任

### 反模式 2: "注入后锚点"模式导致文本重复

**症状**: 让 LLM 生成 `{anchor, new_text}` 注入时，如果 `new_text` 包含 `anchor` 中的文字（如 anchor="笑了一下"，new_text="他笑了一下，但那笑没到眼底"），`content.replace(anchor, anchor + '\n\n' + new_text)` 会创建重复文本。

**对策**: 
- 注入模式的 new_text **不能包含 anchor 的任何子串**
- 优先使用"替换"而非"插入"——替换一个明确唯一的段落
- 如果用插入，验证 new_text 不包含 anchor

### 反模式 3: 压缩文字 = 抹杀角色魅力

**症状**: 为了提升 Pacing 压缩叙述文字，Character Charm 立即下降（实测：Pacing 7.3→6.8，同时 Charm 7.33→6.33）。

**原因**: 角色魅力的核心在于细节（习惯动作、特殊表达、犹豫和停顿）。压缩删除了这些细节。

**对策**:
- 永远不要为了节奏牺牲角色细节
- 如果需要提升 Pacing，砍叙述性废话（"仿佛/似乎"）而非角色专属描写
- 角色自带声音的细节（如林远敲裤缝、刘闯说"啧"）是黄金资产，不动

### 反模式 4: 分数天花板（~7.6/10）是真实存在的

**症状**: 经过 7 轮不同策略（注入/替换/压缩/声音重塑），分数在 7.4-7.6 之间震荡，从不超过 7.6。

**原因**: 逐段修补有结构性天花板。角色对话、故事骨架、场景结构是 LLM novel-factory 原创生成的品质上限。线级 patch 无法突破这个上限。

**对策**:
- 如果 ≥5 轮后分数停滞在 7.5±0.2，接受此分数为当前章节的天花板
- 突破需要结构性重写（新对话体系、新场景结构、新角色出场方式），不是 patch
- 将此分数标记为章节质量基线，继续写后续章节
- 后续章节可以借鉴本轮学到的角色声音差异化策略，在源头改善

### 反模式 5: LLM 的摘要 ≠ 实际输出

**症状**: LLM 返回 JSON 数组和摘要文字（如"加入如果那么结构"），但实际 MongoDB 中的变更内容与摘要不完全一致。

**原因**: LLM 的输出层和逻辑层有分离——它"打算"做某事，但 output 文本可能不同。

**对策**:
- 每次 LLM patch 后，**必须 grep 验证实际变更的文字片段**
- 不信任摘要，只信任 exact string match
- 验证脚本应该打印修改前后的具体内容对比

### 反模式 6: wordCount 字段不同步

**症状**: 每次用 Python 脚本直接 `novel['chapters'].update_one({...}, {'$set': {'content': new_text}})` 修改章节内容后，`wordCount` 字段不会自动更新且无人修复。实测前三章分别差 663/692/597 字。

**后果**: `novel-factory` 的统计面板显示错误字数，影响 ARC 规划时的章节长度判断。

**对策**:
- 每次用脚本直接改 content 后，**必须同步更新 wordCount**：`{'$set': {'wordCount': len(new_content)}}`
- 或者直接用 `scripts/sync-after-refinement.py` 做统一修正
- 如果已经产生漂移，全量扫描一遍：`python3 -c "for ch in db.find({'novelName': N}): db.update_one({'_id': ch['_id']}, {'$set': {'wordCount': len(ch['content'])}})"`

### 反模式 7: LLM 生成 hook 依赖旧的 summary 而非内容

**症状**: `extract_hook()` 如果基于 `chapter_memory.summary` 而非 `content[-200:]`，会生成与最新内容脱节的钩子。精修改动了对话但评审利用旧 hook 评分。

**对策**:
- hook 永远基于实时内容：`content[-200:]` 直接截取，不信任任何缓存字段
- summary 也应从内容前 150 字实时生成，不依赖旧值

## 附录：评分维度说明

评审系统 `novel-review-pipeline` 使用以下维度：

| 维度 | 含义 | 目标分数 |
|------|------|---------|
| Hook | 黄金三章/开头吸引力 | ≥8.5 |
| Pacing | 节奏与冲突密度 | ≥8.5 |
| Retention | 留存/章末钩子 | ≥8.5 |
| Character Charm | 角色魅力（最难提升） | ≥8.5 |
| Emotion | 情绪密度 | ≥8.5 |
| Readability | 可读性 | ≥8.5 |
| AI Smell | AI味检测 | 10.0（现有值） |
| Market | 平台适配 | 番茄/起点/女频 |
| **Overall** | **加权平均** | **≥8.5 (PASS)** |

**经验值**: Character Charm 是所有维度中最难通过 patch 提升的——需要结构性对话声音重塑或角色出场重写。

## ⚠️ 反模式 8: DeepSeek API 配置索引偏移

**症状**: `config['custom_providers'][0]` 拿到的是第一个 provider（如中转站 API 1314mc），而非 DeepSeek。DeepSeek 可能是第 3 个 provider（索引 2）。

**对策**:
- 用 `config['custom_providers'][2]` 或通过 provider name 查找而非索引
- 脚本中应该用 `grep api_key config.yaml` 确认索引
- DeepSeek API endpoint 需要 `/v1/chat/completions` 路径（不含 v1 返回 401）

## ⚠️ 反模式 9: LLM 返回含「」的对白文本

**症状**: LLM 在 `original` 字段返回 `「过来一下。」`（含括号），但脚本期望的是不包含括号的 `过来一下。`。正则 `f'「{re.escape(orig)}」'` 会匹配错误的双括版本。

**对策**:
- 在 prompt 中明确要求「output中只输出文本，不含「」符号」
- 或者在脚本中 strip 首尾的「」
- 更好的做法：在 prompt 末尾加一句 `原始文本必须在原文中能找到（用精确匹配）`——LLM 在明确约束下不会加括号

## ⚠️ 反模式 10: sync-after-refinement.py 需要完整小说名

**症状**: 传 `诡异游戏`（前4字）导致 `novel_db['chapters'].find({'novelName': args.novel_name})` 返回 0 结果，因为 MongoDB 中存储的是全称 `诡异游戏：我的规则别人看不见`。

**对策**:
- 首次操作前先查 `novel['chapters'].distinct('novelName')` 确认全名
- 或在脚本中支持模糊查询：`{'novelName': {'$regex': name[:4]}}`

## 批量化对话声音重塑流程

> 实测协议：6章 25处修改 → Character Charm +0.63，单次运行耗时约5分钟

当需要对多章（≥3）执行对话声音重塑时，使用配套的批量脚本：

```bash
# 1. 首次运行，修改并预览（建议 max 5章一批）
cd ~/.hermes/skills/content-creation/novel-refinement-branch/scripts/
python3 dialogue-voice-refiner.py '诡异游戏' --chapters 4-9 --dry-run

# 2. 确认无误后写入（分批：4-6, 7-9，批次间sleep 5s）
python3 dialogue-voice-refiner.py '诡异游戏' --chapters 4-6
sleep 8
python3 dialogue-voice-refiner.py '诡异游戏' --chapters 7-9

# 2.5 验证修改已写入MongoDB
python3 -c "import pymongo;c=pymongo.MongoClient('...');ch=c['novel']['chapters'].find_one({'novelName':'诡异游戏：我的规则别人看不见','chapterNumber':4});print('关键文本' in ch['content'])"

# 2.6 对API失败章节重试
python3 retry-failed-chapters.py '诡异游戏：我的规则别人看不见' --chapters 12,14,15,19

# 3. 运行评审验证
python3 ../../novel-review-pipeline/scripts/novel-judge.py review '诡异游戏' --chapters 4-9 --verdict-only

# 4. 同步并合并（使用完整小说名）
python3 sync-after-refinement.py '诡异游戏：我的规则别人看不见' --chapters 4-9 --merge --llm-hooks
```

### 批量化脚本设计细节

1. **每轮 ≤5 条** — hard limit，防次生效应（来自反模式1）
2. **LLM 可能返回带「」的文本** — 脚本在 prompt 中明确要求「不含「」符号」
3. **匹配失败的 fallback** — 如果某个 suggestion 匹配失败（已修改过/原文不同），跳过继续
4. **自动保存 diff** — 每次写入后自动保存 before/after 到 `/tmp/refine_ch{N}_*.txt`
5. **profile 可自定义** — 内置默认 profile（诡异游戏6角色），也支持 `--profiles file.txt`
6. **分批不要超过5章** — 超过5章导致脚本超时或API限流（反模式12）
7. **apply后必须验证** — 用 grep 确认修改已写入 MongoDB（反模式13）
8. **失败章节重试** — 使用配套 `scripts/retry-failed-chapters.py` 单独重试

### 构建角色声音画像的原则

角色声音画像文件（`--profiles`）应包含：

- **角色名 + 基本设定**（年龄、身份、特殊能力）
- **说话特征**（3-5个 bullet point，具体到句式/语气/用词偏好）
- **具体的改写前/后对比示例**（至少每个角色1组）
- **避免空泛描述**（如「他是一个沉稳的人」——这是设定，不是声音特征）

完整示例见 `references/voice-profiles-guǐyì-youxì.md`。

## 完整案例数据

《诡异游戏》前三章 7 轮精修完整路线图见 `references/refinement-7-rounds-case-study.md`。包含每轮分数、策略、得失分析和 code 片段。

《诡异游戏》ch4-9 批量化对话声音重塑案例见 `references/voice-profiles-guǐyì-youxì.md`。包含 6 个角色的详细声音画像和实际改写示例。

DeepSeek API 间歇性空返回的重试策略见 `references/deepseek-retry-strategy.md`。包含分批、退避、独立 retry 脚本三种方案。

## 为什么不重新设计 Prompt?

精修系统的核心价值不在 Prompt, 而在 **工程架构**:

- **Patch 层** — 每次修改都是可追溯的独立补丁
- **Diff 层** — 原始/修改/diff 三者同时保存
- **Refinement Branch** — 不污染创作主线的独立分支
- **Lore Sync 层** — 后期设定反哺前文的自动化管道

这让 Hermes Novel Factory 从"AI 写小说"真正升级为**可维护的长篇小说工程系统**。

## 未来扩展

- [ ] `continuity-patch.py` — 自动应用一致性 Patch (Tier2 规则引擎)
- [ ] `foreshadow-repair.py` — 自动伏笔回补 (Tier3 LLM API)
- [ ] `prose-enhancer.py` — 微润色 (轻量 LLM 调用)
- [ ] `dialogue-voice-refiner.py` — 对话声音差异化（基于角色模板的 LLM 改写器）
- [ ] 批量重构模式: 修炼体系升级 → 自动全书同步修正
- [ ] GitHub/Gitee 自动提交 diff 记录
- [ ] 精修面板 (Web UI) — 可视化 Patch 审批流程
