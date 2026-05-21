# NovelOS — Hermes Agent 小说创作技能包

> 完整的小说创作工程化系统，覆盖从创建、续写、重建、精修、评审到发布的六阶段全流程。

## 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                    NovelOS 全流程流水线                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Phase 1: 创建 (Creation)                                        │
│  └─ hermes-novel-factory     ← 多 Agent 小说创作引擎              │
│                                                                  │
│  Phase 0: 数据重建 (Reconstruction)                              │
│  └─ novel-reconstruction     ← 一次性元数据恢复（修脏数据）       │
│                                                                  │
│  Phase 2: 精修 (Refinement)                                      │
│  ├─ novel-refinement-branch  ← Patch 级精修流水线                │
│  ├─ dialogue-voice-refinement-runbook  ← 对话声音重塑 SOP        │
│  └─ novel-full-pipeline-sop  ← 全流程指引                        │
│                                                                  │
│  Phase 3: 评审 (Review)                                          │
│  └─ novel-review-pipeline    ← 八维独立评审系统（不改文只判分）   │
│                                                                  │
│  Phase 4: 审计修复 (Audit & Fix)                                 │
│  ├─ novel-audit-fix          ← 全量8步审计+自动修复              │
│  └─ novel-factory-repair-workflow  ← 诊断→修复→新ARC启动        │
│                                                                  │
│  基础设施:                                                       │
│  ├─ novel-cli-web-integration ← CLI统一入口 + Web控制台          │
│  └─ web-novel-chapter        ← 单章写作（男频/女频模板）         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 技能清单（10 个）

| # | 技能名 | 定位 | SKILL.md 大小 | 核心文件 |
|---|--------|------|---------------|----------|
| 1 | **hermes-novel-factory** | 多 Agent 小说撰写引擎 | ~55KB | 7 scripts, templates, references |
| 2 | **novel-reconstruction** | Phase 0 — 小说状态重建 | ~20KB | novel-reconstruct.py, schema mappings |
| 3 | **novel-refinement-branch** | V3 Patch 级精修流水线 | ~40KB | 6 scripts, 3 references |
| 4 | **novel-review-pipeline** | 八维独立质检系统 | ~15KB | novel-judge.py (LLM + 规则) |
| 5 | **novel-audit-fix** | 全量8步审计+自动修复 | ~8KB | audit-and-fix.py |
| 6 | **novel-factory-repair-workflow** | 修复+新ARC启动一站式方案 | ~28KB | 内置MongoDB路径、角色出场审计 |
| 7 | **novel-cli-web-integration** | CLI统一入口+Web控制台 | ~18KB | novel入口脚本、Flask API |
| 8 | **web-novel-chapter** | 单章写作（10种模板） | ~30KB | count-chinese-chars.py, 10 references |
| 9 | **dialogue-voice-refinement-runbook** | 对话声音差异化精修 | ~12KB | retry-refine.py |
| 10 | **novel-full-pipeline-sop** | 全流程操作手册 | ~18KB | 从创建到发布的完整指引 |

## 核心工作流

### 标准六阶段流程

```
创建 → 重建(脏数据时) → 精修 → 评审 → 反馈循环 → 发布
```

详细操作见每个子技能的 SKILL.md。

### 快速命令汇总

```bash
# 创建小说
novel-factory new '小说名' --genre 玄幻

# 续写（3-5章/轮）
novel-factory continue '小说名'

# 数据重建（脏数据修复）
python3 novel-reconstruct.py run '小说名' --module all

# 全量评审
python3 novel-judge.py review '小说名' --chapters 1-136

# 对话声音重塑（最高ROI精修）
python3 dialogue-voice-refiner.py '小说名' --chapters 1-5

# 全量审计修复
python3 audit-and-fix.py '小说名'

# Web UI
novel studio  # 或访问 NovelStudio (端口5003)
```

## 数据库架构

| 用途 | MongoDB URI | 库名 |
|------|-------------|------|
| 最终成品 | mongodb://user:pass@host:27017 | `novel` (novels + chapters) |
| 创作中间态 | mongodb://user:pass@host:27017 | `novel_factory` (结构化元数据) |

**字段映射核心坑**（反复踩过的）：
- `novel.chapters` 用 `novelName`（字符串）关联，不是 ObjectId
- `novel_factory.arcs` 用 `title`（非 `name`），无 `chapters` 数组
- `novel_factory.foreshadow`：`description`→`content`，`callback_chapter`→`suggested_callback_ch`
- `event_log.timestamp` 必须是 `datetime` 对象，不能是字符串
- `world_bible` 所有设定字段为数组类型
- `foreshadow_queue.urgency` 是 `enum(low/medium/high/critical)`，不能含 emoji

## 关键设计原则

1. **裁判与修理工分离** — Review 不改文，Refinement 不判分
2. **局部 Patch 优先** — 禁止全文重写，只做精确的 find-and-replace
3. **MongoDB 唯一真相源** — 所有数据落盘，本地文件仅作为缓存
4. **Append-only 事件日志** — 不删不改历史
5. **黄金三章特殊规则** — 前三章评审标准 3 倍，hook < 4 直接打回
6. **3 轮不通过 = 人工介入** — 防止无限循环消耗 token

## 文件结构

```
hermes-skills/novel-creation/
├── README.md                        ← 本文件
├── hermes-novel-factory/            ← 创作引擎
│   ├── SKILL.md
│   ├── scripts/
│   ├── references/
│   ├── templates/
│   ├── storage/
│   └── mongodb/
├── novel-reconstruction/            ← Phase 0: 数据重建
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
├── novel-refinement-branch/         ← Patch 精修
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
├── novel-review-pipeline/           ← 八维评审
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
├── novel-audit-fix/                 ← 审计修复
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
├── novel-factory-repair-workflow/   ← 修复工作流
│   └── SKILL.md
├── novel-cli-web-integration/       ← CLI+Web集成
│   └── SKILL.md
├── web-novel-chapter/               ← 单章模板
│   ├── SKILL.md
│   ├── scripts/
│   └── references/
├── dialogue-voice-refinement-runbook/  ← 对话精修
│   ├── SKILL.md
│   └── scripts/
└── novel-full-pipeline-sop/         ← 全流程手册
    └── SKILL.md
```

## 安装方式

### Hermes Agent 用户（推荐）

每个技能在 Hermes 中自动注册为 skill，通过 `skill_view('技能名')` 加载。

```bash
# 将技能目录链接或复制到 ~/.hermes/skills/content-creation/
# Hermes 会自动发现
```

### 独立部署

每个技能的 `scripts/` 目录下的 Python 脚本可直接运行（需安装 `pymongo`、`requests` 等依赖）。

## 实战数据

- **诡异游戏**：136 章，34 万字，经 7 轮精修迭代
- **对话声音重塑 ROI**：+0.63 Character Charm（6.67→7.33），5 条手术级修改
- **分数天花板**：约 7.6/10，突破需结构性重写
- **API 重试策略**：DeepSeek 间歇性空返回，sleep 20s 后重试通过率 100%
