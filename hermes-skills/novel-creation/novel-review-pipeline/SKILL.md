---
name: novel-review-pipeline
description: Novel Judge System — 独立于创作系统的 AI 小说质检流水线。只负责判决，不参与创作。覆盖 Hook/Retention/Pacing/Emotion/Readability/AI Smell/Market/Character Charm 八维评审。
version: 2.0.0
tags: [novel, review, qa, judge, hook, retention, pacing, ai-smell, market, quality, rewrite-patch]
---

# Novel Review Pipeline — AI 小说质检系统

> **核心理念**: 评审不参与创作，只负责判决。
> 创作 Agent 自己评判自己 → 严重自嗨。
> Novel Judge 必须有独立人格、独立 Prompt、独立评分体系。

## 架构位置

```
NovelOS
├── creation/          (hermes-novel-factory)       ← 创作主线
├── reconstruction/    (novel-reconstruction)        ← Phase 0: 数据重建
├── refinement/        (novel-refinement-branch)    ← Phase 1-3: 精修
├── review/            (novel-review-pipeline)      ← NOW: 独立评审
│
└── feedback-loop/                                    ← 评审 → Patch → 精修 → 再评审
```

## 评审原则

1. **独立人格** — 评审 Agent 与创作 Agent 使用不同的 Prompt/模型
2. **不修改正文** — 只输出评分/裁决/Patch 建议，不直接改文
3. **局部修复** — 不全文重写，只生成局部修复方案
4. **通过/打回** — 裁决系统决定「通过 / 条件通过 / 打回重写」
5. **反馈回路** — 评审 → Rewrite Patch → 精修 → 再评审 → 直到通过

## v2.0 升级：LLM 语义评审

v2.0.0 (2026-05-19) 将 5 个核心维度从关键词统计升级为 DeepSeek LLM 语义评审：

### 变更一览

| 维度 | 旧实现 | 新实现 | 备注 |
|------|--------|--------|------|
| Hook | 关键词计数（摘要） | LLM 语义评审（正文） | 评估悬念、紧张感、神秘感、情感拉扯、爽点 |
| Pacing | 事件词密度（摘要） | LLM 语义评审（正文） | 评估冲突密度、信息释放节奏、章节张弛感 |
| Retention | 关键词+模式（摘要） | LLM 语义评审（正文） | 评估章末钩子、下一章驱动力 |
| Emotion | 情绪词匹配（摘要） | LLM 语义评审（正文） | 评估情绪密度、情感共鸣 |
| Character Charm | 关键词+Bible对比（摘要） | LLM 语义评审（正文） | 评估角色辨识度、行为一致性、成长弧线 |
| AI Smell | 正则表达式（全文） | 不变（正则） | 规则检测AI味，无需LLM |
| Market | 关键词+算法（摘要） | 不变（规则） | 平台适配依赖规则，无需LLM |
| Readability | 句式分析（全文） | 不变（规则） | 可读性分析无需LLM |

### 降级策略

若 `chapters_content` 为空（数据库加载失败），自动回退到 `_legacy_*` 关键词统计函数，不会中断评审。

### LLM 引擎

- **模型**: deepseek-v4-flash（通过 Hermes config.yaml 读取 API key）
- **Prompt**: 针对每个维度定制，要求严格评分（6=及格，7=良好，8=优秀，9=顶级）
- **重试**: 3 次自动重试（JSON 解析失败或网络错误）
- **系统 Prompt**: 角色设定为「专业的中国网络小说编辑」

## 八维评审

| 维度 | 评分 | 实现方式 | 依赖 | 权重 |
|------|------|----------|------|------|
| Hook | 0-10 | LLM 语义（正文） | chapters_content | 25% |
| Retention | 0-10 | LLM 语义（正文） | chapters_content | 20% |
| Pacing | 0-10 | LLM 语义（正文） | chapters_content | 15% |
| Emotion | 0-10 | LLM 语义（正文） | chapters_content | 10% |
| AI Smell | 0-10 | 正则表达式（全文） | chapter_content | 10% |
| Character Charm | 0-10 | LLM 语义（正文） | chapters_content | 10% |
| Market | 0-10 | 关键词+算法（摘要） | chapters_meta | 5% |
| Readability | 0-10 | 句式分析（全文） | chapter_content | 5% |

## 命令

```bash
cd ~/.hermes/skills/content-creation/novel-review-pipeline/scripts/
python3 novel-judge.py review '诡异游戏'
python3 novel-judge.py review '诡异游戏' --chapters 1-136
python3 novel-judge.py review '诡异游戏' --chapters 1-3 --golden
python3 novel-judge.py review '诡异游戏' --dimension hook,ai_smell
python3 novel-judge.py review '诡异游戏' --verdict-only
python3 novel-judge.py patch '诡异游戏' --chapter 2 --issue hook
python3 novel-judge.py history '诡异游戏'
```

## 反馈回路

评审发现 hook_score < 5 → 生成 Rewrite Patch → novel-refinement-branch 执行精修 → 再评审 → 通过则合入主线，否则继续生成新 Patch。

## 黄金三章特别规则

前三章不是普通章节，是「小说广告页」。评审标准: 3倍评审次数, hook_score < 4 直接打回, 章末必须强钩子, 前500字必须有冲突/爽点。前3章不通过不续写。

## 脚本

- `scripts/novel-judge.py` — 主评审脚本（LLM 语义评审 + 关键词降级 + 规则引擎）
- `references/known-limitations.md` — 已知局限详情（已解决的关键词统计问题归档）

## 已知问题

- `market` 维度仍使用关键词规则，对部分小说可能评分过低。
- MongoDB 章节名必须包含小说全名，建议用 `$regex` 前缀匹配。
- DeepSeek API 的 token 消耗随章节数线性增长，大批量评审注意超时。
