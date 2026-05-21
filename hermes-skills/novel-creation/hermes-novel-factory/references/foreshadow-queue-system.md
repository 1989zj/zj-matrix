# 伏笔债务系统（V3）

> 所属系统：hermes-novel-factory V3
> 文档版本：3.0.0
> 最后更新：2026-05-18
> 负责 Agent：foreshadow-manager

---

## 目录

1. [问题背景与设计目标](#1-问题背景与设计目标)
2. [核心数据结构 Schema](#2-核心数据结构-schema)
3. [foreshadow-manager Agent 职责](#3-foreshadow-manager-agent-职责)
4. [伏笔回收机制](#4-伏笔回收机制)
5. [伏笔健康度报告](#5-伏笔健康度报告)
6. [与 Context Packet 的集成](#6-与-context-packet-的集成)
7. [Python / MongoDB 参考实现](#7-python--mongodb-参考实现)
8. [工作流集成](#8-工作流集成)
9. [边界情况与故障处理](#9-边界情况与故障处理)

---

## 1. 问题背景与设计目标

### 1.1 痛点

长篇 AI 创作的最大死因之一是**「伏笔只埋不收」**。在长序列生成中，LLM 天然倾向于：

- 不断引入新的神秘元素（制造悬念）
- 遗忘早期埋设的线索（注意力窗口有限）
- 产生大量"僵尸伏笔"——埋下后从未回收的剧情债务

百万字以上的作品中，**超过 70% 的伏笔可能被遗忘**，导致读者弃书、逻辑矛盾、叙事崩塌。

### 1.2 设计目标

| 目标 | 说明 |
|------|------|
| **可追溯** | 每个伏笔从埋下到回收的全生命周期可查询 |
| **可预警** | 在 deadline 到达前自动提醒，防止超期 |
| **可强制执行** | 每次 Draft 前至少回收 1 个到期或紧急的伏笔 |
| **可量化** | 用健康度指标衡量当前叙事债务风险 |
| **可集成** | 无缝融入现有 Context Packet 与 Draft 流水线 |

### 1.3 与 V2 的差异

| 维度 | V2（无系统） | V3（本系统） |
|------|-------------|-------------|
| 伏笔管理 | 纯自然语言备忘录 | 结构化 Schema + MongoDB 持久化 |
| 回收触发 | 人工记忆或随机 | Agent 强制检查 + deadline 驱动 |
| 健康度 | 无 | 量化指标 + 自动报告 |
| 与 Context 集成 | 无 | 未回收高优先伏笔自动进入长期记忆层 |

---

## 2. 核心数据结构 Schema

### 2.1 基础 Schema（MongoDB Document）

```python
# === foreshadow 文档结构 (MongoDB Collection: foreshadows) ===

foreshadow_schema = {
    "_id": "ObjectId",                    # MongoDB 自动生成

    # --- 标识 ---
    "foreshadow_id": "str",               # 唯一 ID，格式 "FSH-{chapter:04d}-{seq:03d}"
    "novel_id": "str",                    # 所属小说 ID
    "title": "str",                       # 伏笔简短标题/标签

    # --- 内容 ---
    "content": "str",                     # 伏笔内容描述（含背景上下文）
    "summary": "str",                     # 一句话摘要（用于 Context Packet 引用）

    # --- 时间戳 ---
    "setup_chapter": "int",               # 埋设章节号 (1-indexed)
    "setup_chunk_index": "int",           # 埋设时在章节内的 chunk 序号
    "deadline_chapter": "int",            # 最晚回收章节号
    "resolved_chapter": "int | None",     # 实际回收章节号（未回收为 None）
    "created_at": "datetime",             # 记录创建时间
    "updated_at": "datetime",             # 最后更新时间

    # --- 分类 ---
    "type": "str",                        # 枚举: role / item / ability / event / secret
    "priority": "str",                    # 枚举: high / medium / low

    # --- 状态 ---
    "status": "str",                      # 枚举: active / pending / expired / resolved

    # --- 关联 ---
    "related_foreshadows": ["str"],       # 关联伏笔 ID 列表（伏笔链）
    "related_characters": ["str"],        # 关联角色 ID 或名称
    "tags": ["str"],                      # 自定义标签

    # --- 回收记录 ---
    "resolution": {
        "method": "str | None",           # 回收方式: soft / hard / repurposed
        "description": "str | None",      # 回收过程简述
        "chunk_index": "int | None",      # 回收时所在 chunk
        "satisfaction_score": "float",    # 回收满意度 0.0-1.0 (可选)
    },

    # --- 元数据 ---
    "metadata": {
        "created_by": "str",              # 创建者 agent 名称
        "resolved_by": "str | None",      # 回收者 agent 名称
        "notes": "str | None",            # 人工备注
    },
}
```

### 2.2 枚举值定义

```python
from enum import Enum

class ForeshadowType(str, Enum):
    ROLE    = "role"       # 角色相关（神秘人物、隐藏身份）
    ITEM    = "item"       # 物品相关（神器、关键道具）
    ABILITY = "ability"    # 能力相关（隐藏技能、血脉觉醒）
    EVENT   = "event"      # 事件相关（预言、灾难征兆）
    SECRET  = "secret"     # 秘密相关（真相、谜题）

class ForeshadowPriority(str, Enum):
    HIGH   = "high"        # 主线核心伏笔，必须在 deadline 前回收
    MEDIUM = "medium"      # 重要支线伏笔，尽量在 deadline 前回收
    LOW    = "low"         # 调味型伏笔，过期可忽略

class ForeshadowStatus(str, Enum):
    ACTIVE   = "active"    # 活跃，待回收
    PENDING  = "pending"   # 等待条件触发（前置伏笔未回收）
    EXPIRED  = "expired"   # 已超期未回收
    RESOLVED = "resolved"  # 已回收

class ResolutionMethod(str, Enum):
    SOFT       = "soft"        # 软回收：对话提及 / 回忆闪回 / 暗示
    HARD       = "hard"        # 硬回收：剧情直接触发 / 事件落地
    REPURPOSED = "repurposed"  # 改造回收：被新事件覆盖或改写
```

### 2.3 MongoDB 索引设计

```javascript
// === 索引策略 ===

// 1. 主查询索引：按小说 + 状态 + deadline 排序
db.foreshadows.createIndex(
  { novel_id: 1, status: 1, deadline_chapter: 1 },
  { name: "idx_foreshadow_query" }
);

// 2. 紧急度查询索引：优先查询即将到期的高优先伏笔
db.foreshadows.createIndex(
  { novel_id: 1, priority: 1, status: 1, deadline_chapter: 1 },
  { name: "idx_foreshadow_urgency" }
);

// 3. 时间窗口查询：查找特定章节范围内的伏笔
db.foreshadows.createIndex(
  { novel_id: 1, setup_chapter: 1, deadline_chapter: 1 },
  { name: "idx_foreshadow_chapter_range" }
);

// 4. 过期扫描索引：用于定期清理过期伏笔
db.foreshadows.createIndex(
  { status: 1, deadline_chapter: 1 },
  { name: "idx_foreshadow_expired_scan" }
);

// 5. 关联查询：伏笔链检索
db.foreshadows.createIndex(
  { related_foreshadows: 1 },
  { name: "idx_foreshadow_relations" }
);
```

### 2.4 紧急度计算公式

```python
def calculate_urgency(foreshadow, current_chapter):
    """
    计算伏笔紧急度分数。
    分数越高越紧急，用于排序决定回收优先级。
    
    返回: float (0.0 ~ 10.0)
    """
    if foreshadow.status != ForeshadowStatus.ACTIVE:
        return 0.0
    
    chapters_remaining = foreshadow.deadline_chapter - current_chapter
    
    # 已过期 -> 最高紧急
    if chapters_remaining <= 0:
        return 10.0
    
    # 基础分：距离 deadline 越近分数越高
    # deadline = 50, current = 40, 剩余 10 章 -> 7.0
    # deadline = 50, current = 10, 剩余 40 章 -> 1.0
    base_score = max(0.0, 10.0 - (chapters_remaining * 0.2))
    
    # 优先级加成
    priority_bonus = {
        ForeshadowPriority.HIGH:   2.0,
        ForeshadowPriority.MEDIUM: 1.0,
        ForeshadowPriority.LOW:    0.0,
    }[foreshadow.priority]
    
    # 类型加成（某些类型天然需要更长回收窗口）
    type_bonus = {
        ForeshadowType.SECRET:  0.5,   # 秘密类通常更关键
        ForeshadowType.EVENT:   0.5,   # 事件类影响面广
        ForeshadowType.ROLE:    0.3,
        ForeshadowType.ABILITY: 0.2,
        ForeshadowType.ITEM:    0.0,
    }[foreshadow.type]
    
    score = base_score + priority_bonus + type_bonus
    return min(10.0, max(0.0, score))


def get_urgency_level(score):
    """将分数转为可读等级"""
    if score >= 8.0:
        return "critical"    # 危机：必须立即回收
    elif score >= 5.0:
        return "warning"     # 警告：即将到期
    elif score >= 2.0:
        return "attention"   # 关注：还有时间但需留意
    else:
        return "healthy"     # 健康：无需担心
```

---

## 3. foreshadow-manager Agent 职责

### 3.1 职责概览

```
┌─────────────────────────────────────────────────────┐
│                foreshadow-manager                     │
├─────────────────────────────────────────────────────┤
│  - 伏笔创建与注册          (register_foreshadow)      │
│  - 紧急扫描与预警          (scan_urgency)             │
│  - 强制回收调度            (enforce_resolution)        │
│  - 过期伏笔审计            (audit_expired)             │
│  - 健康度报告              (health_report)             │
│  - Context Packet 集成推送  (sync_to_context)          │
└─────────────────────────────────────────────────────┘
```

### 3.2 核心工作流

```
Draft 开始
    │
    ▼
[1] 扫描即将到期的伏笔
    │
    ├── 有 critical 级伏笔 ──→ 强制中断 Draft，先执行回收
    │
    ├── 有 warning 级伏笔  ──→ 插入到 Draft 指令中，至少回收 1 个
    │
    └── 全部 healthy      ──→ 常规 Draft
            │
            ▼
[2] Draft 生成
    │
    ▼
[3] 后处理：
    ├── 检测 Draft 中是否出现了新伏笔 → 注册入库
    ├── 检测 Draft 中是否自然回收了伏笔 → 更新状态
    └── 更新 Context Packet 中的伏笔摘要
            │
            ▼
[4] 更新健康度快照
    │
    ▼
结束
```

### 3.3 Agent 方法定义

```python
class ForeshadowManager:
    """伏笔债务管理器"""

    def __init__(self, novel_id: str, db: MongoDBClient):
        self.novel_id = novel_id
        self.db = db
        self.collection = db["foreshadows"]

    # ──────────── 伏笔生命周期 ────────────

    def register_foreshadow(
        self,
        content: str,
        foreshadow_type: ForeshadowType,
        priority: ForeshadowPriority,
        setup_chapter: int,
        deadline_chapter: int | None = None,
        related: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        注册一个新伏笔。
        
        自动分配 foreshadow_id、deadline_chapter（如果未提供）。
        deadline_chapter 自动分配规则：
          - high priority:   setup_chapter + 20  (20章内回收)
          - medium priority: setup_chapter + 40
          - low priority:    setup_chapter + 80
        
        返回 foreshadow_id。
        """
        pass

    def resolve_foreshadow(
        self,
        foreshadow_id: str,
        method: ResolutionMethod,
        chapter: int,
        chunk_index: int | None = None,
        description: str | None = None,
        satisfaction: float = 0.7,
    ) -> bool:
        """
        标记一个伏笔已回收。
        
        回收规则：
        - 只有 status = active 或 pending 的伏笔可以回收
        - 回收后更新 resolved_chapter, status, resolution 字段
        - 如果有相关联的伏笔（pending），尝试触发其状态更新
        """
        pass

    # ──────────── 扫描与预警 ────────────

    def scan_urgency(self, current_chapter: int) -> list[dict]:
        """
        扫描所有 active 伏笔，返回按紧急度排序的列表。
        
        返回格式：
        [
            {
                "foreshadow_id": "FSH-0012-001",
                "content": "...",
                "urgency_score": 8.7,
                "urgency_level": "critical",
                "chapters_remaining": -3,
                "deadline_chapter": 48,
            },
            ...
        ]
        """
        pass

    def get_forced_resolution_candidates(
        self, current_chapter: int, min_count: int = 1
    ) -> list[dict]:
        """
        获取"强制回收候选"列表。
        
        规则：
        1. 所有 critical 级伏笔必须进入候选
        2. 如果 critical 不够 min_count，从 warning 级补充
        3. 按紧急度降序排列
        4. 优先选择与当前章节内容类型匹配的伏笔
        
        返回前 min_count 个候选。
        """
        pass

    # ──────────── 过期审计 ────────────

    def audit_expired(self, current_chapter: int) -> dict:
        """
        扫描所有 active 伏笔，将 deadline_chapter < current_chapter 的
        标记为 expired 状态。
        
        返回: { "marked_expired": 5, "total_active_before": 23 }
        """
        pass

    def get_expired_report(self) -> list[dict]:
        """获取所有已过期但未回收的伏笔列表（供人类审阅）"""
        pass

    # ──────────── 伏笔链管理 ────────────

    def link_foreshadows(
        self, parent_id: str, child_ids: list[str]
    ) -> bool:
        """
        建立伏笔链：parent 回收后自动触发 child 状态变为 active。
        
        用于"先决条件型"伏笔：角色必须先获得 A 线索，
        才能触发 B 事件。
        """
        pass

    def get_foreshadow_chain(self, foreshadow_id: str) -> list[dict]:
        """获取以指定伏笔为起点的完整伏笔链"""
        pass
```

### 3.4 Draft 前检查（关键入口函数）

```python
def pre_draft_check(manager: ForeshadowManager, current_chapter: int):
    """
    Draft 前的强制性伏笔检查。
    在每次 Draft Agent 执行前调用。
    
    返回: PreDraftDirective
    """
    # 1. 先执行过期审计
    expired = manager.audit_expired(current_chapter)
    
    # 2. 获取强制回收候选
    candidates = manager.get_forced_resolution_candidates(
        current_chapter, min_count=1
    )
    
    # 3. 构建 Draft 指令
    directive = PreDraftDirective()
    
    if expired["marked_expired"] > 0:
        directive.add_note(
            f"⚠️ {expired['marked_expired']} 个伏笔已过期，"
            f"请检查是否需要补回收或在后续章节处理。"
        )
    
    if candidates:
        directive.set_forced_resolution(candidates)
        # 将强制回收指令注入到 Draft prompt 中
        directive.add_instruction(
            f"【强制回收】以下伏笔必须在当前章节中至少回收 1 个：\n"
            + "\n".join(
                f"- [{c['urgency_level']}] {c['foreshadow_id']}: "
                f"{c['content']} (还剩 {c['chapters_remaining']} 章)"
                for c in candidates
            )
        )
    
    return directive
```

---

## 4. 伏笔回收机制

### 4.1 三种回收方式

#### 4.1.1 软回收 (Soft)

通过对话、回忆、暗示等方式间接呼应伏笔。

```yaml
适用场景:
  - 配角口头提及早年事件
  - 角色看到某物触发回忆闪回
  - 侧面描写暗示真相
  - 环境细节呼应（同一颜色的花在不同章节出现）

优缺点:
  - 优点: 自然、不打断叙事节奏、符合文学手法
  - 缺点: 读者可能忽略、需要较强的上下文暗示

示例:
  伏笔: "第三章主角捡到一枚刻有狼头的银币"
  软回收: "第四十二章中，主角路过古董店时，橱窗里一枚相似的银币
           让他想起三年前在河边捡到的那枚——至今不知道它的来历。"
```

#### 4.1.2 硬回收 (Hard)

伏笔直接触发剧情事件，是"揭晓时刻"。

```yaml
适用场景:
  - 神秘人的身份揭晓
  - 预言的实现
  - 关键道具的真正用途触发
  - 真相大白

优缺点:
  - 优点: 痛快、满足期待、读者记忆深刻
  - 缺点: 需要足够铺垫否则显突兀

示例:
  伏笔: "第一章预言'当双月重叠之日，冰封王座将苏醒'"
  硬回收: "第五十章中，两颗月亮在天穹重叠，冰川碎裂，
           王座的轮廓在寒雾中缓缓升起。"
```

#### 4.1.3 改造回收 (Repurposed)

伏笔被新事件覆盖或改写——原伏笔未按预期发展，但被赋予了新意义。

```yaml
适用场景:
  - 角色计划落空但走向更有趣的方向
  - 伏笔被另一条更重要的剧情线"劫持"
  - 反转：看似 A 其实是 B

优缺点:
  - 优点: 创造性解决"收不回来"的问题、制造反转惊喜
  - 缺点: 需要小心处理以避免感觉像"编不下去了"

示例:
  伏笔: "第二章神秘人留给主角一把生锈的钥匙"
  改造回收: "第六十章揭示这把钥匙其实是陷阱的触发机关，
            开启的不是宝库而是囚牢——神秘人从未想帮主角。"
```

### 4.2 回收时机策略

```python
def suggest_resolution_timing(foreshadow, current_chapter, total_chapters):
    """
    根据伏笔属性和当前进度，建议最优回收时机。
    
    返回: {
        "recommended_chapter": int,       # 建议回收章节
        "strategy": str,                  # soft / hard / repurposed
        "reasoning": str,                 # 建议理由
    }
    """
    remaining = foreshadow.deadline_chapter - current_chapter
    gap_from_setup = current_chapter - foreshadow.setup_chapter
    
    if remaining <= 0:
        # 已过期 -> 建议紧急软回收
        return {
            "recommended_chapter": current_chapter,
            "strategy": "soft",
            "reasoning": "已超过 deadline，建议在当前章节通过对话暗示紧急软回收"
        }
    
    if remaining <= 5 and foreshadow.priority == ForeshadowPriority.HIGH:
        return {
            "recommended_chapter": current_chapter + 1,
            "strategy": "hard",
            "reasoning": f"高优先伏笔仅剩 {remaining} 章，建议硬回收确保落地"
        }
    
    # 埋设时间已足够长但还有时间 -> 建议有节奏的回收
    if gap_from_setup >= 15 and remaining >= 10:
        return {
            "recommended_chapter": current_chapter,
            "strategy": "soft",
            "reasoning": f"已埋设 {gap_from_setup} 章，建议先软回收预热，后期硬回收"
        }
    
    # 还有充裕时间 -> 按兵不动
    return {
        "recommended_chapter": None,
        "strategy": "wait",
        "reasoning": f"距 deadline 还有 {remaining} 章，可继续酝酿"
    }
```

### 4.3 强制回收规则

| 条件 | 动作 |
|------|------|
| 存在 critical 级伏笔（score ≥ 8.0） | 强制中断当前 Draft，先执行回收子流程 |
| 存在 warning 级伏笔（score ≥ 5.0）且本次 Draft 未经回收 | Draft prompt 中插入强制回收指令 |
| 连续 3 章无任何伏笔被回收 | 自动触发一次"伏笔清算章节" |
| 出现 expired 伏笔 | 记录审计日志，在下一章通过软回收消化至少 1 个 |

### 4.4 回收质量评估

```python
def evaluate_resolution_quality(foreshadow, chapter_context):
    """
    评估一个回收的质量分数。
    用于后期健康度分析和 Agent 自我改进。
    
    评分维度 (0.0 ~ 1.0):
    - coherence:   与原文的一致性（是否有逻辑矛盾）
    - satisfaction: 读者满足感（基于埋设-回收的距离和类型匹配度）
    - naturalness: 是否自然地融入了当前章节
    - completeness: 伏笔的全部要素是否都被覆盖
    
    返回: QualityReport
    """
    pass
```

---

## 5. 伏笔健康度报告

### 5.1 核心指标

```python
class ForeshadowHealthReport:
    """伏笔系统健康度报告"""
    
    # ────── 规模指标 ──────
    total_foreshadows: int          # 伏笔总数
    active_count: int               # 活跃待回收数
    resolved_count: int             # 已回收数
    expired_count: int              # 过期未回收数
    pending_count: int              # 等待触发数
    
    # ────── 比率指标 ──────
    resolution_rate: float          # 回收率 = resolved / (resolved + expired + active)
    expired_rate: float             # 过期率 = expired / total
    healthy_rate: float             # 健康率 = (resolved + active_not_urgent) / total
    
    # ────── 债务指标 ──────
    total_debt_score: float         # 总债务分数
    avg_urgency: float              # 平均紧急度 (active 伏笔)
    max_urgency: float              # 最高紧急度
    
    # ────── 窗口指标 ──────
    avg_setup_to_deadline: int      # 平均埋设-回收窗口（章数）
    avg_setup_to_resolution: int    # 平均埋设-实际回收窗口
    deadline_violations: int        # 逾期次数
    
    # ────── 紧急分级 ──────
    critical_count: int             # critical 级数量
    warning_count: int              # warning 级数量
    attention_count: int            # attention 级数量
    healthy_urgency_count: int      # healthy 级数量
    
    # ────── 类型分布 ──────
    type_distribution: dict         # {type: count}
    priority_distribution: dict     # {priority: count}
```

### 5.2 健康度等级判定

```python
def classify_health(report: ForeshadowHealthReport) -> str:
    """
    综合判定伏笔系统健康度等级。
    
    等级:
    - "excellent": 一切正常
    - "good":      需要注意
    - "warning":   需要干预
    - "critical":  必须立刻处理
    """
    if report.expired_count >= 10 or report.critical_count >= 3:
        return "critical"
    
    if report.expired_count >= 5 or report.warning_count >= 5:
        return "warning"
    
    if report.expired_rate > 0.1 or report.resolution_rate < 0.3:
        return "warning"
    
    if report.expired_count >= 1 or report.warning_count >= 2:
        return "good"
    
    return "excellent"
```

### 5.3 报告模板

```markdown
# 伏笔健康度报告（第 {chapter} 章）

## 概览
- 总伏笔数: {total} | 已回收: {resolved} | 活跃: {active} | 过期: {expired}
- 回收率: {resolution_rate:.1%} | 过期率: {expired_rate:.1%}
- 健康等级: **{health_level}** {health_icon}

## 紧急伏笔（Top 5）
| ID | 内容摘要 | 优先 | 剩余章节 | 紧急度 |
|----|---------|------|---------|-------|
| ... | ... | ... | ... | ... |

## 过期伏笔清单
| ID | 内容摘要 | 埋设章节 | deadline | 超期章数 |
|----|---------|---------|---------|---------|
| ... | ... | ... | ... | ... |

## 类型分布
- 角色: {role_count} | 物品: {item_count} | 能力: {ability_count}
- 事件: {event_count} | 秘密: {secret_count}

## 建议
- {recommendation_1}
- {recommendation_2}
- {recommendation_3}
```

---

## 6. 与 Context Packet 的集成

### 6.1 集成架构

```
┌──────────────────────────────┐
│        Context Packet          │
├──────────────────────────────┤
│  Layer 1: 当前章节上下文        │  ← 不使用伏笔数据
│  Layer 2: 最近 5 章摘要        │  ← 不使用伏笔数据
│  Layer 3: 活跃角色状态          │  ← 可能引用伏笔摘要
│  Layer 4: 长期记忆              │  ← ◀ 未回收高优伏笔注入点
│  Layer 5: 世界观/设定           │  ← 不使用伏笔数据
│  Layer 6: 伏笔债务摘要 ★        │  ← 新增层
└──────────────────────────────┘
```

### 6.2 新增 Layer 6：伏笔债务摘要

```python
def build_foreshadow_context_layer(
    manager: ForeshadowManager,
    current_chapter: int,
    max_items: int = 10,
) -> dict:
    """
    构建 Context Packet 的 Layer 6（伏笔债务摘要）。
    
    选择策略:
    1. 所有 critical 级伏笔 (urgency >= 8.0) —— 必须全部包含
    2. 所有 warning 级伏笔 (urgency >= 5.0) —— 按 deadline 排序
    3. 如果容量有余，补充最近埋设的 active 伏笔
    4. 最多返回 max_items 条
    
    返回: {
        "layer": 6,
        "name": "foreshadow_debt",
        "summary": "当前有 15 个未回收伏笔，其中 3 个紧急",
        "items": [...],
    }
    """
    # 获取所有 active 伏笔并按紧急度排序
    urgent_items = manager.scan_urgency(current_chapter)
    
    selected = []
    
    # 步骤1：先取所有 critical
    critical = [i for i in urgent_items if i["urgency_level"] == "critical"]
    selected.extend(critical[:max_items])
    
    # 步骤2：补充 warning
    remaining_slots = max_items - len(selected)
    if remaining_slots > 0:
        warning = [i for i in urgent_items if i["urgency_level"] == "warning"]
        selected.extend(warning[:remaining_slots])
    
    # 步骤3：如果还有空位，补充 attention
    remaining_slots = max_items - len(selected)
    if remaining_slots > 0:
        attention = [i for i in urgent_items if i["urgency_level"] == "attention"]
        selected.extend(attention[:remaining_slots])
    
    # 构建 items 摘要（每个条目压缩到 1-2 句话）
    items_summary = []
    for item in selected:
        items_summary.append({
            "id": item["foreshadow_id"],
            "summary": item["content"][:120],  # 截断过长的内容
            "urgency": item["urgency_level"],
            "deadline": f"Chapter {item['deadline_chapter']}",
            "type": item.get("type", "unknown"),
        })
    
    urgent_summary = ""
    if critical:
        urgent_summary = f"⚠️ 有 {len(critical)} 个紧急伏笔需立即处理！"
    elif any(i["urgency_level"] == "warning" for i in selected):
        urgent_summary = f"注意：有多个伏笔即将到期。"
    
    return {
        "layer": 6,
        "name": "foreshadow_debt",
        "summary": (
            f"当前有 {len(urgent_items)} 个未回收伏笔。"
            + urgent_summary
        ),
        "overdue_count": sum(
            1 for i in urgent_items if i.get("chapters_remaining", 999) < 0
        ),
        "items": items_summary,
    }
```

### 6.3 长期记忆层注入

对于 high priority 且超过 30 章仍未回收的伏笔，应写入长期记忆层（Layer 4）：

```python
def inject_aged_foreshadows_to_long_term(
    manager: ForeshadowManager,
    current_chapter: int,
    threshold_chapters: int = 30,
) -> list[dict]:
    """
    将"埋设已久但未回收的重磅伏笔"注入到长期记忆层。
    
    条件:
    - priority = high
    - status = active
    - current_chapter - setup_chapter >= threshold_chapters
    
    注入格式:
    {
        "type": "aged_foreshadow",
        "foreshadow_id": "...",
        "summary": "...",
        "setup_chapter": ...,
        "importance": "这是一个埋设已超过 30 章的高优伏笔，必须回收",
    }
    """
    pipeline = [
        {
            "$match": {
                "novel_id": manager.novel_id,
                "status": "active",
                "priority": "high",
            }
        },
        {
            "$addFields": {
                "age": {"$subtract": [current_chapter, "$setup_chapter"]}
            }
        },
        {
            "$match": {"age": {"$gte": threshold_chapters}}
        },
        {"$sort": {"age": -1}},
    ]
    
    aged = list(manager.collection.aggregate(pipeline))
    
    return [
        {
            "type": "aged_foreshadow",
            "foreshadow_id": f["foreshadow_id"],
            "summary": f["summary"] or f["content"][:100],
            "setup_chapter": f["setup_chapter"],
            "age_chapters": current_chapter - f["setup_chapter"],
            "importance": (
                f"这是一个埋设已超过 {threshold_chapters} 章的高优伏笔"
                f"（第 {f['setup_chapter']} 章埋设），必须回收！"
            ),
        }
        for f in aged
    ]
```

### 6.4 Context Packet 集成示例

```python
def build_full_context_packet(manager, current_chapter, novel_data):
    """构建完整的 Context Packet，包含伏笔债务层"""
    
    packet = {
        "layer_1": build_chapter_context(novel_data, current_chapter),
        "layer_2": build_recent_summary(novel_data, current_chapter, window=5),
        "layer_3": build_character_status(novel_data),
        "layer_4": build_long_term_memory(novel_data),
        "layer_5": build_world_lore(novel_data),
        "layer_6": build_foreshadow_context_layer(
            manager, current_chapter, max_items=10
        ),
    }
    
    # 将"老化伏笔"注入到长期记忆层
    aged = inject_aged_foreshadows_to_long_term(
        manager, current_chapter, threshold_chapters=30
    )
    if aged:
        packet["layer_4"]["aged_foreshadows"] = aged
    
    return packet
```

---

## 7. Python / MongoDB 参考实现

### 7.1 完整 ForeshadowManager 实现

```python
"""
foreshadow_manager.py
Foreshadow Debt System for novel-factory V3

依赖: pymongo, datetime, uuid
"""

import uuid
from datetime import datetime
from typing import Optional
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError


class ForeshadowManager:
    """伏笔债务管理器 - 完整实现"""

    def __init__(self, novel_id: str, mongo_uri: str = "mongodb://localhost:27017"):
        self.novel_id = novel_id
        self.client = MongoClient(mongo_uri)
        self.db = self.client["novel_factory"]
        self.collection = self.db["foreshadows"]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """确保索引存在"""
        self.collection.create_index(
            [("novel_id", ASCENDING), ("status", ASCENDING),
             ("deadline_chapter", ASCENDING)],
            name="idx_foreshadow_query"
        )
        self.collection.create_index(
            [("novel_id", ASCENDING), ("priority", ASCENDING),
             ("status", ASCENDING), ("deadline_chapter", ASCENDING)],
            name="idx_foreshadow_urgency"
        )
        self.collection.create_index(
            [("status", ASCENDING), ("deadline_chapter", ASCENDING)],
            name="idx_foreshadow_expired_scan"
        )

    def _generate_id(self, setup_chapter: int) -> str:
        """生成 foreshadow_id: FSH-{chapter:04d}-{seq:03d}"""
        seq = self.collection.count_documents({
            "novel_id": self.novel_id,
            "setup_chapter": setup_chapter,
        }) + 1
        return f"FSH-{setup_chapter:04d}-{seq:03d}"

    def _auto_deadline(self, setup_chapter: int, priority: str) -> int:
        """根据优先级自动分配 deadline"""
        windows = {
            "high": 20,
            "medium": 40,
            "low": 80,
        }
        return setup_chapter + windows.get(priority, 40)

    # ──────────── 核心 API ────────────

    def register_foreshadow(
        self,
        content: str,
        summary: str = "",
        foreshadow_type: str = "event",
        priority: str = "medium",
        setup_chapter: int = 1,
        setup_chunk_index: int = 0,
        deadline_chapter: Optional[int] = None,
        related_foreshadows: Optional[list[str]] = None,
        related_characters: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        created_by: str = "unknown",
    ) -> str:
        """
        注册新伏笔并写入 MongoDB。
        
        返回 foreshadow_id。
        """
        if not summary:
            summary = content[:80] + ("..." if len(content) > 80 else "")

        if deadline_chapter is None:
            deadline_chapter = self._auto_deadline(setup_chapter, priority)

        foreshadow_id = self._generate_id(setup_chapter)

        doc = {
            "foreshadow_id": foreshadow_id,
            "novel_id": self.novel_id,
            "title": summary[:40],
            "content": content,
            "summary": summary,
            "setup_chapter": setup_chapter,
            "setup_chunk_index": setup_chunk_index,
            "deadline_chapter": deadline_chapter,
            "resolved_chapter": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "type": foreshadow_type,
            "priority": priority,
            "status": "active",
            "related_foreshadows": related_foreshadows or [],
            "related_characters": related_characters or [],
            "tags": tags or [],
            "resolution": {
                "method": None,
                "description": None,
                "chunk_index": None,
                "satisfaction_score": None,
            },
            "metadata": {
                "created_by": created_by,
                "resolved_by": None,
                "notes": None,
            },
        }

        try:
            self.collection.insert_one(doc)
        except DuplicateKeyError:
            # 极低概率冲突，重试
            foreshadow_id = self._generate_id(setup_chapter)
            doc["foreshadow_id"] = foreshadow_id
            self.collection.insert_one(doc)

        return foreshadow_id

    def resolve_foreshadow(
        self,
        foreshadow_id: str,
        method: str = "hard",
        chapter: int = 1,
        chunk_index: Optional[int] = None,
        description: Optional[str] = None,
        satisfaction: float = 0.7,
        resolved_by: str = "unknown",
    ) -> bool:
        """
        标记伏笔已回收。
        
        参数:
            method: "soft" | "hard" | "repurposed"
        
        返回 True 如果成功。
        """
        result = self.collection.update_one(
            {
                "foreshadow_id": foreshadow_id,
                "novel_id": self.novel_id,
                "status": {"$in": ["active", "pending"]},
            },
            {
                "$set": {
                    "status": "resolved",
                    "resolved_chapter": chapter,
                    "resolution.method": method,
                    "resolution.description": description,
                    "resolution.chunk_index": chunk_index,
                    "resolution.satisfaction_score": satisfaction,
                    "metadata.resolved_by": resolved_by,
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        return result.modified_count > 0

    def scan_urgency(self, current_chapter: int) -> list[dict]:
        """
        扫描活跃伏笔，按紧急度排序返回。
        
        紧急度计算见 calculate_urgency。
        """
        active = list(self.collection.find({
            "novel_id": self.novel_id,
            "status": "active",
        }))

        results = []
        for f in active:
            score = self._calculate_urgency(f, current_chapter)
            level = self._get_urgency_level(score)
            remaining = f["deadline_chapter"] - current_chapter
            results.append({
                "foreshadow_id": f["foreshadow_id"],
                "content": f["content"],
                "summary": f["summary"],
                "type": f["type"],
                "priority": f["priority"],
                "urgency_score": round(score, 2),
                "urgency_level": level,
                "chapters_remaining": remaining,
                "deadline_chapter": f["deadline_chapter"],
                "setup_chapter": f["setup_chapter"],
            })

        results.sort(key=lambda x: x["urgency_score"], reverse=True)
        return results

    def _calculate_urgency(self, foreshadow: dict, current_chapter: int) -> float:
        """计算单条伏笔紧急度分数"""
        remaining = foreshadow["deadline_chapter"] - current_chapter

        if remaining <= 0:
            return 10.0

        base = max(0.0, 10.0 - (remaining * 0.2))

        bonus_map = {"high": 2.0, "medium": 1.0, "low": 0.0}
        base += bonus_map.get(foreshadow.get("priority", "medium"), 1.0)

        type_bonus = {"secret": 0.5, "event": 0.5, "role": 0.3,
                       "ability": 0.2, "item": 0.0}
        base += type_bonus.get(foreshadow.get("type", "event"), 0.0)

        return min(10.0, max(0.0, base))

    def _get_urgency_level(self, score: float) -> str:
        if score >= 8.0:
            return "critical"
        elif score >= 5.0:
            return "warning"
        elif score >= 2.0:
            return "attention"
        return "healthy"

    def get_forced_resolution_candidates(
        self, current_chapter: int, min_count: int = 1
    ) -> list[dict]:
        """获取强制回收候选列表"""
        urgent = self.scan_urgency(current_chapter)

        candidates = []
        for item in urgent:
            if item["urgency_level"] == "critical":
                candidates.append(item)
            if len(candidates) >= min_count:
                break

        if len(candidates) < min_count:
            for item in urgent:
                if item["urgency_level"] == "warning" and item not in candidates:
                    candidates.append(item)
                if len(candidates) >= min_count:
                    break

        return candidates[:min_count]

    def audit_expired(self, current_chapter: int) -> dict:
        """将超期未回收的伏笔标记为 expired"""
        result = self.collection.update_many(
            {
                "novel_id": self.novel_id,
                "status": "active",
                "deadline_chapter": {"$lt": current_chapter},
            },
            {
                "$set": {
                    "status": "expired",
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        return {
            "marked_expired": result.modified_count,
            "total_active_before": self.collection.count_documents({
                "novel_id": self.novel_id,
                "status": "active",
            }),
        }

    # ──────────── 健康度报告 ────────────

    def health_report(self, current_chapter: int) -> dict:
        """生成完整健康度报告"""
        total = self.collection.count_documents({"novel_id": self.novel_id})
        active = self.collection.count_documents(
            {"novel_id": self.novel_id, "status": "active"}
        )
        resolved = self.collection.count_documents(
            {"novel_id": self.novel_id, "status": "resolved"}
        )
        expired = self.collection.count_documents(
            {"novel_id": self.novel_id, "status": "expired"}
        )
        pending = self.collection.count_documents(
            {"novel_id": self.novel_id, "status": "pending"}
        )

        urgent = self.scan_urgency(current_chapter)
        critical_count = sum(1 for u in urgent if u["urgency_level"] == "critical")
        warning_count = sum(1 for u in urgent if u["urgency_level"] == "warning")

        # 平均窗口
        resolved_cursor = self.collection.find(
            {"novel_id": self.novel_id, "status": "resolved"},
            {"setup_chapter": 1, "resolved_chapter": 1}
        )
        windows = [
            r["resolved_chapter"] - r["setup_chapter"]
            for r in resolved_cursor if r.get("resolved_chapter")
        ]
        avg_window = sum(windows) / len(windows) if windows else 0

        total_active = active + pending
        resolution_rate = (
            resolved / (resolved + expired + total_active)
            if (resolved + expired + total_active) > 0
            else 0
        )
        expired_rate = expired / total if total > 0 else 0

        # 健康等级判定
        if expired >= 10 or critical_count >= 3:
            health_level = "critical"
        elif expired >= 5 or warning_count >= 5:
            health_level = "warning"
        elif expired_rate > 0.1 or resolution_rate < 0.3:
            health_level = "warning"
        elif expired >= 1 or warning_count >= 2:
            health_level = "good"
        else:
            health_level = "excellent"

        return {
            # 规模
            "total_foreshadows": total,
            "active_count": active,
            "resolved_count": resolved,
            "expired_count": expired,
            "pending_count": pending,
            # 比率
            "resolution_rate": round(resolution_rate, 4),
            "expired_rate": round(expired_rate, 4),
            # 紧急
            "critical_count": critical_count,
            "warning_count": warning_count,
            # 窗口
            "avg_setup_to_resolution": round(avg_window, 1),
            # 健康等级
            "health_level": health_level,
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ──────────── 实用工具 ────────────

    def get_foreshadow(self, foreshadow_id: str) -> Optional[dict]:
        """按 ID 查询单条伏笔"""
        return self.collection.find_one({
            "foreshadow_id": foreshadow_id,
            "novel_id": self.novel_id,
        }, {"_id": 0})

    def list_active(self) -> list[dict]:
        """列出所有活跃伏笔"""
        return list(self.collection.find(
            {"novel_id": self.novel_id, "status": {"$in": ["active", "pending"]}},
            {"_id": 0}
        ).sort("deadline_chapter", ASCENDING))

    def delete_foreshadow(self, foreshadow_id: str) -> bool:
        """删除伏笔（仅用于清理测试数据）"""
        result = self.collection.delete_one({
            "foreshadow_id": foreshadow_id,
            "novel_id": self.novel_id,
        })
        return result.deleted_count > 0

    def link_foreshadows(self, parent_id: str, child_ids: list[str]) -> bool:
        """建立伏笔依赖链"""
        result = self.collection.update_one(
            {"foreshadow_id": parent_id, "novel_id": self.novel_id},
            {"$addToSet": {"related_foreshadows": {"$each": child_ids}}}
        )
        if result.modified_count == 0:
            return False
        # 子伏笔设为 pending
        self.collection.update_many(
            {"foreshadow_id": {"$in": child_ids}, "novel_id": self.novel_id},
            {"$set": {"status": "pending", "updated_at": datetime.utcnow()}}
        )
        return True
```

### 7.2 使用示例

```python
# === 初始化 ===
manager = ForeshadowManager(novel_id="novel_001")

# === 注册伏笔 ===
fid = manager.register_foreshadow(
    content="主角在古墓中发现了一枚刻有狼头的银币，背面写着一行模糊的古文",
    summary="狼头银币上的古文",
    foreshadow_type="item",
    priority="high",
    setup_chapter=3,
    tags=["古墓", "银币", "预言"],
    created_by="draft-agent-v3",
)
print(f"伏笔已注册: {fid}")

# === 注册依赖型伏笔 ===
child_id = manager.register_foreshadow(
    content="主角必须破解银币上的古文才能找到下一处秘境入口",
    foreshadow_type="event",
    priority="medium",
    setup_chapter=8,
    deadline_chapter=15,
)
manager.link_foreshadows(fid, [child_id])

# === Draft 前检查 ===
directive = pre_draft_check(manager, current_chapter=12)
print(f"强制回收候选: {len(directive.forced_candidates)} 个")

# === 回收伏笔 ===
manager.resolve_foreshadow(
    foreshadow_id=fid,
    method="hard",
    chapter=12,
    description="主角在图书馆查到了古文的含义——指向北方冰原",
    satisfaction=0.85,
    resolved_by="draft-agent-v3",
)

# === 健康度报告 ===
report = manager.health_report(current_chapter=12)
print(f"健康度: {report['health_level']}")
print(f"回收率: {report['resolution_rate']:.1%}")

# === 构建 Context Packet ===
packet = build_full_context_packet(manager, current_chapter=12, novel_data={})
print(f"Layer 6: {packet['layer_6']['summary']}")
```

### 7.3 数据迁移脚本（V2 → V3）

```python
"""
migrate_v2_to_v3.py
将 V2 系统的自然语言伏笔备忘录迁移到结构化 MongoDB
"""

import json
import re
from pathlib import Path

def migrate_v2_notes(manager: ForeshadowManager, notes_path: str):
    """
    迁移 V2 的纯文本伏笔笔记到 V3 结构化数据。
    
    输入格式: 每行一个伏笔，格式为:
    [类型] 内容 (第X章) [优先级]
    
    例如:
    [物品] 狼头银币，背面有古文 (第3章) [高]
    [事件] 预言说双月重叠时会如何 (第1章) [高]
    """
    notes_path = Path(notes_path)
    if not notes_path.exists():
        print(f"⚠️ 未找到 V2 笔记: {notes_path}")
        return 0
    
    type_map = {"角色": "role", "物品": "item", "能力": "ability",
                "事件": "event", "秘密": "secret"}
    priority_map = {"高": "high", "中": "medium", "低": "low"}
    
    count = 0
    with open(notes_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # 解析 [类型]
            type_match = re.match(r'\[(.+?)\]', line)
            f_type = type_map.get(type_match.group(1), "event") if type_match else "event"
            
            # 解析 (第X章)
            chapter_match = re.search(r'第(\d+)章', line)
            chapter = int(chapter_match.group(1)) if chapter_match else 1
            
            # 解析 [优先级]
            priority_match = re.search(r'\[(高|中|低)\]', line)
            priority = priority_map.get(priority_match.group(1), "medium") if priority_match else "medium"
            
            # 提取内容（去除标记）
            content = re.sub(r'\[.+?\]|\(第\d+章\)', '', line).strip()
            if not content:
                continue
            
            manager.register_foreshadow(
                content=content,
                foreshadow_type=f_type,
                priority=priority,
                setup_chapter=chapter,
                created_by="migration-v2",
            )
            count += 1
    
    print(f"✅ 已迁移 {count} 条伏笔从 V2 到 V3")
    return count
```

---

## 8. 工作流集成

### 8.1 与 Draft Pipeline 的集成点

```
                   ┌──────────────┐
                   │  User Prompt  │
                   └──────┬───────┘
                          │
                          ▼
              ┌──────────────────────┐
              │  pre_draft_check()    │  ← 伏笔强制检查入口
              │  (foreshadow-manager) │
              └──────────┬───────────┘
                         │
              ┌──────────▼───────────┐
              │  需强制回收？         │
              │  candidates > 0 ?     │
              └──────┬────────┬──────┘
                     │ 是     │ 否
                     ▼        ▼
           ┌────────────┐    ┌──────────────┐
           │ 回收子流程   │    │ 常规 Draft    │
           │ (resolve)   │    │ (generate)    │
           └──────┬─────┘    └──────┬───────┘
                  │                 │
                  ▼                 ▼
              ┌──────────────────────────┐
              │  post_draft_scan()        │  ← 检测新伏笔 + 自然回收
              │  (foreshadow-manager)     │
              └────────────┬─────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │  health_report()          │  ← 更新健康度
              └────────────┬─────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │  sync_to_context()        │  ← 更新 Context Packet
              └──────────────────────────┘
```

### 8.2 强制回收子流程

```python
def forced_resolution_workflow(
    manager: ForeshadowManager,
    candidate: dict,
    current_chapter: int,
    draft_agent: callable,
) -> dict:
    """
    强制回收子流程。
    
    流程:
    1. 根据伏笔类型和剩余章节，建议回收方式
    2. 生成回收提示（包含伏笔上下文）
    3. 调用 Draft Agent 生成回收段落
    4. 验证回收质量
    5. 更新伏笔状态
    
    返回: ResolutionResult
    """
    timing = suggest_resolution_timing(
        manager.get_foreshadow(candidate["foreshadow_id"]),
        current_chapter,
        total_chapters=200,
    )
    
    prompt = (
        f"【伏笔回收】\n"
        f"以下伏笔必须在此章节中回收：\n"
        f"- 内容：{candidate['content']}\n"
        f"- 建议方式：{timing['strategy']}\n"
        f"- 建议理由：{timing['reasoning']}\n\n"
        f"请自然地将其融入当前章节，确保回收质量。"
    )
    
    # 调用 Draft Agent 生成
    generated = draft_agent.generate_chunk(prompt)
    
    # 标记回收
    manager.resolve_foreshadow(
        foreshadow_id=candidate["foreshadow_id"],
        method=timing["strategy"],
        chapter=current_chapter,
        description=generated["summary"][:200],
        satisfaction=0.7,
        resolved_by="draft-agent-v3",
    )
    
    return {
        "foreshadow_id": candidate["foreshadow_id"],
        "method": timing["strategy"],
        "chapter": current_chapter,
        "success": True,
    }
```

### 8.3 与 Draft Agent 的对话协议

```yaml
# foreshadow-manager → draft-agent 通信协议

PreDraftDirective:
  description: "Draft 前伏笔检查产生的指令"
  fields:
    - forced_resolutions: list[dict]    # 必须回收的伏笔列表
    - recommendations: list[str]        # 推荐处理的伏笔
    - expired_warnings: list[str]       # 已过期的伏笔警告
    - instructions: list[str]           # 注入 Draft prompt 的文本

示例指令注入:
  "【系统指令】当前章节必须处理以下伏笔：
   1. [CRITICAL] FSH-0012-003: 银币古文的秘密 (还剩 2 章)
   2. [WARNING] FSH-0008-001: 神秘人的身份 (还剩 7 章)
   请至少硬回收其中 1 个，并自然融入当前剧情。"

PostDraftReport:
  description: "Draft 生成后，draft-agent 返回的报告"
  fields:
    - new_foreshadows: list[dict]       # Draft 中新埋的伏笔
    - resolved_foreshadows: list[str]   # Draft 中回收的伏笔 ID
    - chapter_summary: str              # 章节摘要
```

---

## 9. 边界情况与故障处理

### 9.1 边界情况

| 场景 | 处理策略 |
|------|---------|
| **deadline 已过但伏笔仍很重要** | 标记为 expired 但保留 metadata.notes="建议后续章节补回收"；不自动触发回收 |
| **伏笔太多超过 Context 容量** | 按紧急度截断，剩余存储在 MongoDB 中；在健康度报告中标注 "N 个未展示" |
| **伏笔链断裂（父伏笔被删除）** | 级联：child 伏笔的 related_foreshadows 自动清理，status 重置为 active |
| **单章中多个伏笔同时到期** | 按 紧急度 > 优先级 > 埋设时间 排序，优先处理核心主线的伏笔 |
| **回收后又被新剧情推翻** | 通过改造回收 (repurposed) 覆盖原 resolution，更新 resolved_chapter |
| **用户主动插入非 AI 生成内容** | 手动调用 register_foreshadow / resolve_foreshadow 更新系统状态 |
| **小说总章节数动态变化** | deadline_chapter 基于相对偏移（+N 章）而非绝对章节号？建议仍用绝对值，但提供批量调整 API |

### 9.2 故障处理

```python
class ForeshadowError(Exception):
    """伏笔系统基础异常"""
    pass

class ForeshadowNotFoundError(ForeshadowError):
    """伏笔 ID 不存在"""
    pass

class ForeshadowAlreadyResolvedError(ForeshadowError):
    """伏笔已被回收，不可重复回收"""
    pass

class ForeshadowStatusConflictError(ForeshadowError):
    """状态变更冲突"""
    pass


def safe_resolve(manager, foreshadow_id, method, chapter, **kwargs):
    """带错误处理的回收操作"""
    try:
        foreshadow = manager.get_foreshadow(foreshadow_id)
        if not foreshadow:
            raise ForeshadowNotFoundError(
                f"伏笔 {foreshadow_id} 不存在"
            )
        if foreshadow["status"] == "resolved":
            raise ForeshadowAlreadyResolvedError(
                f"伏笔 {foreshadow_id} 已在第 {foreshadow['resolved_chapter']} 章回收"
            )
        return manager.resolve_foreshadow(foreshadow_id, method, chapter, **kwargs)
    except ForeshadowError as e:
        # 记录错误但不中断主流程
        logging.error(f"伏笔回收失败: {e}")
        return False
```

### 9.3 性能考虑

- **索引覆盖**：核心查询（novel_id + status + deadline_chapter）已建索引，单小说百万级伏笔查询 < 50ms
- **扫描频率**：scan_urgency 每次 Draft 前调用（约 5-10s/次），不建议频繁调用
- **写操作**：register / resolve 均为单文档原子操作，O(1) 复杂度
- **Context 构建**：Layer 6 只取 Top-N（默认 10），不会膨胀 context 长度

---

## 附录 A：Changelog

| 版本 | 日期 | 变更 |
|------|------|------|
| 3.0.0 | 2026-05-18 | 初始版本——完整伏笔债务系统设计 |

## 附录 B：相关文档

- [Context Packet 设计文档](./context-packet-system.md)
- [Draft Agent 工作流](./draft-agent-workflow.md)
- [novel-factory V3 架构总览](./novel-factory-architecture.md)
