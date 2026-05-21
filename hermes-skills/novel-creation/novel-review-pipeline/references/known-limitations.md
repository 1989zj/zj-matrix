# Review Pipeline — 已知局限与修复方向

> 文档更新: 2026-05-19 (v2.0.0 LLM 升级后归档)

## ✅ 已解决 (v2.0.0)

### ~~1. chapters_content 未被使用~~ ✅ 已修复

**状态**: 已修复 (2026-05-19)

`do_review()` 现在调用 `load_chapter_content()` 加载 `novel.chapters.content` 全文，并传入所有 5 个 LLM 评审维度函数。若全文加载失败则自动回退到 `_legacy_*` 关键词评分。

### ~~2. 关键词统计 vs 语义理解~~ ✅ 已修复

**状态**: 已修复 (2026-05-19)

Hook/Pacing/Retention/Emotion/Character Charm 五个维度已全部升级为 DeepSeek LLM 语义评审。AI Smell/Readability/Market 仍保留规则引擎（不需要语义理解）。

## 🔴 未解决

### 1. 章节记忆同步断裂

#### 断裂链
```
Phase 3 Refinement
  → update novel.chapters.content     ← 正文已修
  → chapter_memory.summary 不变      ← 摘要仍旧
  → 缓存变量未刷新
Phase 4 Review
  → load_chapter_metadata(chapter_memory)  ← 读旧摘要
  → meta 维度（非 LLM 维度）用旧数据
```

注意：v2.0.0 后 LLM 评审维度直接读 `chapters.content` 正文，不再依赖 `chapter_memory.summary`，但 `market` 和 `readability` 两个维度仍依赖 `chapters_meta`。

#### 修复方向
精修完成后显式调用摘要更新:
```python
def sync_chapter_memory_after_refine(pid, ch_num, new_content, new_hook=None):
    summary = generate_summary(new_content[:200])
    nf['chapter_memory'].update_one(
        {'project_id': pid, 'chapter': ch_num},
        {'$set': {
            'summary': summary,
            'hook': new_hook or extract_hook(new_content[-200:]),
            'last_refined': datetime.now(timezone.utc)
        }}
    )
```

### 2. Market 维度评分过低

#### 问题
Market 维度使用关键词规则，对非起点类小说（悬疑/心理恐怖）评分极低（诡异游戏得 0.0/10）。但 LLM 不适合评估平台适配性，因为需要具体的平台规则知识。

#### 可能的修复方向
- 扩展起点/番茄/女频的关键词库
- 引入 LLM 辅助分析小说类型，然后匹配平台规则

### 3. MongoDB 小说名匹配

#### 问题
MongoDB 中 `novel.chapters.novelName` 存储全名（如 `诡异游戏：我的规则别人看不见`），但用户通常输入简称（`诡异游戏`）。

#### 当前修复
`load_chapter_content()` 已添加正则回退匹配。但 `get_project_id()` 中的 `$regex: novel_name[:6]` 对 4 字小说名处理正确。

### 4. DeepSeek API token 消耗

大批量评审（136 章）的 token 消耗较大。每章每个 LLM 维度调用一次 API，5 个维度 × N 章 = 5N 次调用。

#### 建议
批量评审时可用 `--dimension` 指定关键维度，或只评审关键章节（如前三章 `--chapters 1-3`）。

## 评审用例（基于诡异游戏实测 v2.0.0）

| 模式 | 评分 | 判决 |
|------|------|------|
| v1.0 关键词版 | 2.6/10 | REJECT |
| v2.0 LLM 版 | 7.6/10 | PASS |
| hook LLM | 7.67 | ✅ |
| pacing LLM | 8.33 | ✅ |
| retention LLM | 8.70 | ✅ |
| emotion LLM | 7.00 | ✅ |
| character_charm LLM | 6.33 | ✅ |
