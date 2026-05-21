# 世界状态模拟器（V3）

> **所属系统**: novel-factory V3  
> **负责 Agent**: world-simulator  
> **版本**: 3.0  
> **最后更新**: 2026-05-18

---

## 目录

1. [设计目标](#1-设计目标)
2. [MongoDB Schema（world_state collection）](#2-mongodb-schemaworld_state-collection)
3. [world-simulator Agent 职责](#3-world-simulator-agent-职责)
4. [世界状态变化规则](#4-世界状态变化规则)
5. [因果链详解](#5-因果链详解)
6. [事件日志（事件溯源）](#6-事件日志事件溯源)
7. [与 Draft Agent 的集成](#7-与-draft-agent-的集成)
8. [Python/MongoDB 伪代码](#8-pythonmongodb-伪代码)
9. [演化示例：主角买下公司](#9-演化示例主角买下公司)
10. [可视化状态转移图](#10-可视化状态转移图)

---

## 1. 设计目标

V2 只有章节/角色/大纲，缺乏一个关键的抽象——**「世界正在发生什么」**。这导致：

| 问题 | 后果 |
|------|------|
| 没有经济周期 | 神豪流、商战流缺乏宏观背景约束 |
| 没有公众舆论 | 主角行为的社会反馈缺失，角色如同在真空中行动 |
| 没有资本关注度 | 收购、上市等情节缺乏「市场反应」 |
| 没有势力动态 | 多方势力同时存在时，相互关系和演变无迹可寻 |
| 没有新闻热点 | 事件缺乏传播效应和连锁反应 |

**世界状态模拟器** 的核心目标：

| 目标 | 说明 |
|------|------|
| **动态世界** | 世界状态随剧情推进持续演化，而非静态背景 |
| **因果链** | 主角动作 → 社会反应 → 状态变化，形成完整因果链路 |
| **惯性约束** | 状态变化需连续积累，防止「一夜翻天」式的跳变 |
| **阈值触发** | 影响力/关注度突破阈值时触发新事件或新势力介入 |
| **写作可读** | Draft Agent 写作前读取最新 world_state，确保情节与世界状态一致 |

---

## 2. MongoDB Schema（world_state collection）

```python
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId

# ─────────────────────────────────────────────
# 世界状态主模型
# ─────────────────────────────────────────────

class NewsItem(BaseModel):
    headline: str               # 新闻标题
    impact: str                 # 影响描述（eg. "股价+3%", "主角声望-5"）
    timestamp: datetime         # 发生时间
    tags: list[str] = []        # 标签（eg. ["economy", "protagonist", "tech"]）

class FactionPower(BaseModel):
    faction_name: str           # 势力名称
    power_level: int            # 势力强度 0-100
    attitude_to_protagonist: str  # 对主角态度: hostile / wary / neutral / friendly / allied

class CrisisState(BaseModel):
    type: str                   # 危机类型（eg. "economic", "hostile_takeover", "scandal"）
    severity: int               # 严重程度 0-100
    involved_factions: list[str]  # 涉事势力名称列表
    started_at: datetime        # 危机开始时间
    resolved: bool = False      # 是否已解决

class WorldState(BaseModel):
    """MongoDB world_state collection 文档模型"""
    novel_id: ObjectId          # 关联小说 ID
    chapter_id: ObjectId        # 当前章节 ID（最后更新的章节）

    # ── 宏观经济 ──
    economy: str = "stable"     # 经济周期: bull(bullish) / bear / stable / crisis / recovery

    # ── 公众舆论 ──
    public_opinion: dict[str, float] = {}  # {character_name: score}
    # score 含义:
    #   -100 ~ -51: 遭唾弃
    #   -50 ~  -1: 声誉不佳
    #     0 ~  20: 普通人
    #    21 ~  60: 有好感
    #    61 ~ 100: 备受爱戴

    # ── 资本市场 ──
    capital_attention: int = 0  # 资本市场关注度 0-100（神豪流核心指标）
    # 0: 无人关注
    # 1-30: 局部关注（行业内）
    # 31-60: 市场关注（财经媒体）
    # 61-90: 广泛关注（主流媒体）
    # 91-100: 全民热议

    # ── 主角城市影响力 ──
    city_influence: int = 0     # 主角在该城市的影响力范围 0-100
    # 0: 无名之辈
    # 1-20: 小有名气
    # 21-40: 业界知名
    # 41-60: 城市名人
    # 61-80: 城市影响力人物
    # 81-100: 城市主宰级

    # ── 势力动态 ──
    faction_power: list[FactionPower] = []

    # ── 热点新闻 ──
    news_feed: list[NewsItem] = []  # 当前热点事件，最多保留近 5 条

    # ── 当前危机 ──
    current_crisis: Optional[CrisisState] = None

    # ── 元数据 ──
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

---

## 3. world-simulator Agent 职责

world-simulator 是一个**后处理 Agent**，每次主角完成一章行动后，由 Orchestrator 触发执行。

### 3.1 核心职责

```
┌──────────────────────────────────────────────────┐
│               world-simulator                     │
│                                                    │
│  ① 读取本章主角动作                              │
│  ② 计算社会反应链                                │
│  ③ 更新 world_state 各字段                       │
│  ④ 维护新闻热点动态                              │
│  ⑤ 演化势力间关系                                │
│  ⑥ 生成事件日志                                  │
│  ⑦ 返回状态快照给 Orchestrator                   │
└──────────────────────────────────────────────────┘
```

### 3.2 职责详解

#### ① 读取本章主角动作

从章节正文或 structured_actions 中提取主角在本章的所有「可量化的动作」：

| 动作类型 | 示例 | 影响维度 |
|----------|------|----------|
| 经济动作 | 收购公司、投资、上市 | economy, capital_attention, city_influence |
| 社交动作 | 公开演讲、慈善、绯闻 | public_opinion, news_feed |
| 势力动作 | 打压对手、联盟、收编 | faction_power, current_crisis |
| 城市动作 | 基建、公益、地产 | city_influence, public_opinion |

#### ② 计算社会反应链

每个主角动作触发一系列连锁反应：

```
主角动作
  ├─→ 直接影响（直接修改对应字段）
  ├─→ 舆论扩散（public_opinion 传播）
  ├─→ 市场反应（capital_attention / economy 调整）
  ├─→ 势力反应（faction_power 态度变化）
  └─→ 新闻生成（news_feed 新增条目）
```

#### ③ 更新 world_state 各字段

按规则更新所有字段（详见 [第 4 节](#4-世界状态变化规则)）。

#### ④ 维护新闻热点动态

- 新增当前动作产生的头条新闻
- 淘汰最旧的新闻（最多保留 5 条）
- 旧新闻的 impact 可能衰减（热度消退）

#### ⑤ 演化势力间关系

- 每章结束后，所有势力进行一轮「关系再评估」
- 根据主角行为对势力利益的影响调整 attitude_to_protagonist
- 势力间可能因主角行为互相敌对或联合（通过当前危机体现）

#### ⑥ 生成事件日志

每次状态变化都记录事件日志（详见 [第 6 节](#6-事件日志事件溯源)）。

#### ⑦ 返回状态快照

将更新后的 world_state 压缩为结构化摘要，供 Orchestrator 和 Draft Agent 使用。

---

## 4. 世界状态变化规则

### 4.1 因果链原则

所有状态变化必须由**具体主角动作**触发。不允许「凭空」变化。

```
有效: 主角收购公司 → economy: stable→bull + capital_attention: 10→35
无效: economy: stable→bull（无原因）
```

### 4.2 惯性原则

状态不会瞬间大变，需要连续动作积累。

| 字段 | 单次最大变化量 | 说明 |
|------|---------------|------|
| economy | 不可直接跨两档 | stable→bull ✓, stable→crisis ✗（需经过 bear） |
| capital_attention | ±15 | 一个大型事件最多调动 15 点关注度 |
| city_influence | ±10 | 单一动作最多产生 10 点影响力变化 |
| public_opinion[character] | ±20 | 单一事件最多产生 20 点评分波动 |
| faction_power[].power_level | ±10 | 势力强度变化较慢 |
| faction_power[].attitude | 最多跨 1 档 | neutral→wary ✓, neutral→hostile ✗ |

### 4.3 阈值触发机制

当某些字段突破特定阈值时，自动触发新事件或新势力介入。

```
capital_attention ≥ 30: 地方财经媒体开始报道
capital_attention ≥ 60: 全国财经媒体跟进
capital_attention ≥ 80: 央视 / 顶级媒体关注，敌对势力可能介入

city_influence ≥ 25: 地方势力注意到主角
city_influence ≥ 50: 市级势力主动接触/施压
city_influence ≥ 75: 省级势力介入

public_opinion[protagonist] ≥ 80: 主角成为城市偶像级人物
public_opinion[protagonist] ≤ -50: 可能爆发社会危机（current_crisis）
```

**阈值触发的处理流程**：

```
1. 检测到字段达到阈值
2. 检查当前 world_state 中是否已有对应事件/势力
3. 若无 → 生成新事件 / 引入新势力
4. 若有 → 升级事件严重度 / 改变势力态度
5. 记录事件日志
```

### 4.4 经济周期转移规则

```
bull（牛市）:
  - 连续 3+ 章 capital_attention ≥ 50 且无负面事件维持
  - 默认持续时间 3-5 章后自然转为 stable

bear（熊市）:
  - 连续 2+ 章出现大规模负面经济事件
  - 若危机不解除 → crisis

crisis（危机）:
  - 严重负面事件 + 舆论暴跌
  - 当前危机必须存在且 severity ≥ 60
  - 不可同时两场同类型危机

recovery（复苏）:
  - crisis 后连续 2+ 章正面消息上升
  - economy 自动转为 recovery
  - recovery 持续 2-3 章后转为 stable

stable（稳定）:
  - 默认状态
  - 无明显经济热点事件
```

### 4.5 舆论扩散模型

public_opinion 的变化具有**涟漪效应**：

```
主角正面事件 → 主角声望 +15
             → 关系好的朋友声望 +3（沾光）
             → 敌对角色声望 -5（对立对比）

主角负面事件 → 主角声望 -12
             → 关系好的朋友声望 -3（连带）
             → 敌对角色声望 +5（此消彼长）
```

### 4.6 新闻衰减机制

news_feed 中的新闻会随时间自然衰减：

```
第 1 章: 新闻生成，full impact
第 2 章: 仍在前 5 条中，impact 衰减 30%
第 3 章: 若仍在，impact 衰减 60%
第 4 章: 淘汰（除非被后续动作重新激活）
```

---

## 5. 因果链详解

### 5.1 完整因果链全景

```
[主角动作]
    │
    ├── [直接效应]
    │   ├── city_influence ±Δ
    │   ├── capital_attention ±Δ
    │   └── public_opinion[protagonist] ±Δ
    │
    ├── [经济效应]
    │   ├── economy 周期性调整
    │   └── 相关行业势力 power_level ±Δ
    │
    ├── [舆论效应]
    │   ├── public_opinion 涟漪扩散到其他角色
    │   └── news_feed 新增头条
    │
    ├── [势力效应]
    │   ├── 直接相关势力 attitude 调整
    │   ├── 间接相关势力 attitude 微调
    │   └── 阈值触发 → 新势力介入
    │
    ├── [危机效应]（如触发）
    │   ├── current_crisis 创建/升级/降级/解决
    │   └── economy 加速恶化
    │
    ├── [阈值检查]
    │   ├── 检查所有字段是否突破阈值
    │   └── 触发对应动作（生成事件/引入势力）
    │
    └── [事件日志]
        ├── 记录每个变化的因果链
        ├── 用于 Draft Agent 写作用
        └── 用于事后分析和剧情回顾
```

### 5.2 因果链追踪数据结构

```python
class CausalLink(BaseModel):
    """因果链中的一环"""
    action: str                 # 主角动作描述
    action_type: str            # 动作类型（economic/social/faction/urban）
    affected_field: str         # 受影响字段
    delta: int | str | float    # 变化量
    reason: str                 # 变化原因（自然语言）
    timestamp: datetime
```

每次 world-simulator 运行时，生成一个 `CausalChain` 列表：

```python
causal_chain = [
    CausalLink(action="收购天盛集团", action_type="economic",
               affected_field="capital_attention", delta=+15,
               reason="大规模收购引起资本市场关注"),
    CausalLink(action="收购天盛集团", action_type="economic",
               affected_field="city_influence", delta=+8,
               reason="收购本地龙头企业提升城市影响力"),
    CausalLink(action="收购天盛集团", action_type="economic",
               affected_field="economy", delta="stable→bull",
               reason="大规模资本运作推动市场情绪转向积极"),
    # ...
]
```

---

## 6. 事件日志（事件溯源）

### 6.1 日志存储

事件日志存储在单独的 MongoDB collection `world_event_logs`：

```python
class WorldEventLog(BaseModel):
    """事件日志文档"""
    novel_id: ObjectId
    chapter_id: ObjectId
    event_type: str             # 事件类型: state_change / threshold_trigger / crisis_trigger / faction_change / news_generated
    timestamp: datetime
    description: str            # 自然语言描述
    causal_chain: list[CausalLink]  # 触发这次事件的因果链
    before_state: dict          # 变化前的相关字段快照
    after_state: dict           # 变化后的相关字段快照
```

### 6.2 日志用途

| 用途 | 说明 |
|------|------|
| **Draft Agent 写作参考** | 写作前读取近 N 章的事件日志，了解世界变化轨迹 |
| **剧情回顾** | 用户或 Editor 可回溯世界状态变化 |
| **事件溯源** | 排查状态异常时，追踪具体变化原因 |
| **数据一致性** | 通过重放日志可重建任意时刻的 world_state |

### 6.3 日志示例

```json
{
  "_id": "...",
  "novel_id": "...",
  "chapter_id": "...",
  "event_type": "state_change",
  "timestamp": "2026-05-18T12:00:00Z",
  "description": "主角收购天盛集团后，资本市场关注度从 10 升至 25",
  "causal_chain": [
    {
      "action": "收购天盛集团",
      "action_type": "economic",
      "affected_field": "capital_attention",
      "delta": "+15",
      "reason": "天盛集团是本地龙头企业，收购引发行业关注"
    }
  ],
  "before_state": {"capital_attention": 10},
  "after_state": {"capital_attention": 25}
}
```

---

## 7. 与 Draft Agent 的集成

### 7.1 写作前读取流程

Draft Agent 在每章写作前必须读取最新的 world_state：

```
┌─────────────────┐     ┌─────────────────┐     ┌───────────────────┐
│  Orchestrator   │ ──→ │  MongoDB        │ ──→ │  Draft Agent      │
│  (调度写作任务)  │     │  (读取world_state) │     │  (注入上下文)     │
└─────────────────┘     └─────────────────┘     └───────────────────┘
       │                                                │
       │ ① 读取最新 world_state                          │
       │ ② 压缩为 ≤800 tokens 的世界快照                 │
       │ ③ 拼接最近的 world_event_logs（≤5条）           │
       │ ④ 注入 system prompt                            │
       └────────────────────────────────────────────────┘
```

### 7.2 Context Packet 中的世界状态层

世界状态在 Context Packet 中作为 **Layer 1**（最高优先级）呈现：

```python
# 世界状态快照（压缩版，≤800 tokens）
world_snapshot = {
    "economy": "bull",
    "period": "当前牛市已持续 4 章",
    "top_news": [
        "主角收购天盛集团，股价大涨",
        "地方媒体关注主角背景"
    ],
    "public_opinion": {
        "主角": 72,      # 备受好评
        "竞争对手": -30,  # 名声不佳
    },
    "active_crisis": "无",
    "key_factions": [
        {"name": "天盛原董事会", "power": 40, "attitude": "wary"},
        {"name": "地方商会", "power": 65, "attitude": "neutral"}
    ]
}
```

### 7.3 Draft Agent 的写作约束

Draft Agent 在写作时必须遵守：

1. **经济背景一致**：牛市时商业谈判应顺利，熊市时融资困难
2. **舆论反馈一致**：主角声望高时路人态度友好，声望低时可能被冷遇
3. **资本关注度一致**：capital_attention 高时主角的一举一动都可能被媒体放大
4. **势力态度一致**：敌对势力不会无缘无故示好
5. **新闻事件引用**：可引用 news_feed 中的热点事件作为剧情素材

---

## 8. Python/MongoDB 伪代码

### 8.1 初始化世界状态

```python
async def initialize_world_state(novel_id: ObjectId, initial_config: dict) -> WorldState:
    """新建小说时初始化世界状态"""
    world_state = WorldState(
        novel_id=novel_id,
        chapter_id=ObjectId(),  # 初始章节
        economy=initial_config.get("economy", "stable"),
        public_opinion=initial_config.get("initial_opinions", {}),
        capital_attention=0,
        city_influence=0,
        faction_power=[
            FactionPower(**f) for f in initial_config.get("initial_factions", [])
        ],
        news_feed=[],
        current_crisis=None
    )
    await db.world_state.insert_one(world_state.model_dump())
    return world_state
```

### 8.2 核心更新函数

```python
async def update_world_state(
    novel_id: ObjectId,
    chapter_id: ObjectId,
    protagonist_actions: list[dict],
) -> WorldState:
    """
    主角完成一章行动后，更新世界状态。
    
    Args:
        novel_id: 小说 ID
        chapter_id: 当前章节 ID
        protagonist_actions: 本章主角动作列表
            [
                {"type": "economic", "action": "收购公司", 
                 "target": "天盛集团", "scale": "large"},
                {"type": "social", "action": "公开演讲",
                 "topic": "慈善", "reach": 5000},
            ]
    
    Returns:
        更新后的 WorldState
    """
    # 1. 读取当前世界状态
    ws = await db.world_state.find_one({"novel_id": novel_id})
    
    # 2. 初始化因果链
    causal_chain = []
    events_log = []
    
    # 3. 逐动作处理
    for action in protagonist_actions:
        action_effects = compute_action_effects(action, ws)
        
        # 3a. 应用直接影响
        ws = apply_direct_effects(ws, action_effects)
        causal_chain.extend(action_effects.links)
        
        # 3b. 计算舆论涟漪
        opinion_ripple = compute_opinion_ripple(action, ws)
        ws = apply_opinion_effects(ws, opinion_ripple)
        causal_chain.extend(opinion_ripple.links)
        
        # 3c. 更新新闻
        news_item = generate_news_item(action, ws)
        ws.news_feed.insert(0, news_item)
        ws.news_feed = ws.news_feed[:5]  # 最多保留5条
        
        # 3d. 调整势力关系
        ws = adjust_faction_relations(action, ws)
        
        # 3e. 检查危机
        ws = check_crisis_trigger(action, ws)
    
    # 4. 惯性衰减（旧新闻影响力衰减）
    ws = apply_inertial_decay(ws)
    
    # 5. 阈值检查
    ws = check_all_thresholds(ws)
    
    # 6. 经济周期评估
    ws = evaluate_economy_cycle(ws)
    
    # 7. 更新元数据
    ws.chapter_id = chapter_id
    ws.updated_at = datetime.now(timezone.utc)
    
    # 8. 持久化
    await db.world_state.update_one(
        {"novel_id": novel_id},
        {"$set": ws.model_dump()}
    )
    
    # 9. 记录事件日志
    for event in events_log:
        await db.world_event_logs.insert_one(event)
    
    return ws
```

### 8.3 动作效应计算器

```python
def compute_action_effects(action: dict, ws: WorldState) -> ActionEffects:
    """计算单个动作对所有维度的影响"""
    effects = ActionEffects(links=[])
    
    action_type = action["type"]
    action_name = action["action"]
    scale = action.get("scale", "small")  # small / medium / large
    
    # 影响力度量
    delta_base = {"small": 3, "medium": 8, "large": 15}[scale]
    
    if action_type == "economic":
        # 经济动作影响 capital_attention + city_influence
        effects.capital_attention_delta = delta_base
        effects.city_influence_delta = delta_base // 2
        
        effects.links.append(CausalLink(
            action=action_name,
            action_type="economic",
            affected_field="capital_attention",
            delta=delta_base,
            reason=f"{action_name} 引起资本市场关注（规模: {scale}）"
        ))
        
        # 大型经济动作可能影响经济周期
        if scale == "large":
            effects.economy_shift = "bullish"  # 转向牛市
    
    elif action_type == "social":
        # 社交动作影响 public_opinion + news_feed
        polarity = action.get("polarity", "positive")  # positive / negative
        direction = 1 if polarity == "positive" else -1
        effects.public_opinion_delta[action.get("target", "protagonist")] = delta_base * direction
        
        effects.links.append(CausalLink(
            action=action_name,
            action_type="social",
            affected_field="public_opinion",
            delta=delta_base * direction,
            reason=f"{action_name} 影响公众看法（极性: {polarity}）"
        ))
    
    elif action_type == "faction":
        # 势力动作影响 faction_power
        target_faction = action.get("target_faction")
        attitude_shift = action.get("attitude_shift", "worsen")  # improve / worsen
        ws = adjust_faction(ws, target_faction, attitude_shift, delta_base)
    
    return effects
```

### 8.4 阈值检查器

```python
TRIGGER_THRESHOLDS = {
    "capital_attention": {
        30: {"event": "地方财经报道", "faction_intro": "地方媒体"},
        60: {"event": "全国财经报道", "faction_intro": "全国媒体"},
        80: {"event": "顶级媒体关注", "faction_intro": "敌对势力_市场监察"},
    },
    "city_influence": {
        25: {"event": "地方势力关注", "faction_intro": "地方势力"},
        50: {"event": "市级势力接触", "faction_intro": "市级势力"},
        75: {"event": "省级势力介入", "faction_intro": "省级势力"},
    },
    "public_opinion": {
        80: {"event": "城市偶像级声望", "faction_intro": "粉丝群体"},
        -50: {"event": "社会公敌级声望", "faction_intro": "反对者联盟"},
    }
}

async def check_all_thresholds(ws: WorldState) -> WorldState:
    """检查所有阈值，触发对应事件"""
    for field, thresholds in TRIGGER_THRESHOLDS.items():
        current_value = getattr(ws, field)
        for threshold, trigger_info in thresholds.items():
            if has_crossed_threshold(ws, field, threshold):
                # 检查是否已触发
                if not is_already_triggered(ws, field, threshold):
                    # 触发新事件/引入新势力
                    ws = trigger_event(ws, trigger_info)
                    
                    # 记录日志
                    await log_threshold_trigger(ws, field, threshold, trigger_info)
    
    return ws


def has_crossed_threshold(ws: WorldState, field: str, threshold: int) -> bool:
    """判断是否跨过阈值（从低于到高于，或从高于到低于）"""
    # 实际实现需对比更新前后的值
    # 这里简化：根据当前值与阈值方向判断
    current = getattr(ws, field)
    
    if isinstance(current, dict):
        # public_opinion 特殊处理：检查任意角色
        return any(abs(v) >= threshold for v in current.values())
    
    return current >= threshold if threshold > 0 else current <= threshold
```

### 8.5 新闻生成器

```python
def generate_news_item(action: dict, ws: WorldState) -> NewsItem:
    """根据主角动作生成新闻"""
    templates = {
        "economic_收购": "主角收购{target}，{target}股价大涨{percentage}%",
        "economic_投资": "主角向{target}投资{amount}亿，市场反应积极",
        "social_慈善": "主角捐赠{amount}万用于{project}，社会好评如潮",
        "social_绯闻": "主角被曝{scandal}，公众形象受损",
        "faction_打压": "主角与{faction}关系恶化，双方公开对峙",
        "faction_联盟": "主角与{faction}达成战略联盟，势力格局洗牌",
    }
    
    action_type = f"{action['type']}_{action['action']}"
    template = templates.get(action_type, "主角{action}引发关注")
    
    headline = template.format(**action.get("params", {}))
    
    return NewsItem(
        headline=headline,
        impact=f"capital_attention+{action.get('scale_delta', 5)}",
        timestamp=datetime.now(timezone.utc),
        tags=[action["type"], "hot"]
    )
```

---

## 9. 演化示例：主角买下公司

### 场景设定

- 初始 world_state: economy=stable, capital_attention=5, city_influence=3
- 初始势力: [天盛原董事会(power=70, attitude=neutral)]
- 主角动作: 收购天盛集团（大规模）

### 分步变化

#### 第 1 步：主角宣布收购

```
前状态:
  economy: stable
  capital_attention: 5
  city_influence: 3
  public_opinion: {主角: 10}
  news_feed: []

动作: 主角宣布收购天盛集团（大规模）→ 新闻稿发出

后状态（即时）:
  capital_attention: 5 → 20          (+15, 大规模收购效应)
  city_influence: 3 → 11            (+8, 本地企业收购)
  economy: stable → bull-ish 偏移    (大规模资本运作)
  public_opinion[主角]: 10 → 12     (+2, 舆论中性偏正面)
  news_feed: [
    "主角宣布收购天盛集团，业内震动" (impact: capital_attention+15)
  ]
```

#### 第 2 步：市场反应

```
受第 1 步 news_feed 影响，继续发酵

后状态（舆论扩散）:
  capital_attention: 20 → 30     (+10, 新闻发酵 + 财经媒体开始报道)
  city_influence: 11 → 15        (+4, 收购进程推进)
  public_opinion[主角]: 12 → 18  (+6, 积极报道)

⚠ 阈值触发: capital_attention ≥ 30
  → 地方财经媒体开始报道
  → 新势力介入: 地方媒体 (power=20, attitude=neutral)
  → 新闻新增: "天盛收购案引发地方财经关注"
```

#### 第 3 步：收购完成

```
动作: 收购完成，主角成为天盛集团实控人

后状态:
  capital_attention: 30 → 42     (+12, 收购完成 + 财经媒体深入报道)
  city_influence: 15 → 25        (+10, 实控本地龙头企业的权力效应)
  public_opinion[主角]: 18 → 28  (+10, 成功企业家形象深化)
  public_opinion[天盛原董事会]: 0 → -15  (被收购方声望受损)

⚠ 阈值触发: city_influence ≥ 25
  → 地方势力注意到主角
  → 新势力介入: 地方势力 (power=45, attitude=neutral→wary)
  
势力变化:
  天盛原董事会: power 70→60, attitude neutral→wary (被收购后势力缩减)
  地方势力: 新介入, power=45, attitude=wary (本地力量变化引发警惕)
```

#### 第 4 步：后续连锁反应

```
后状态:
  economy: stable → bull          (连续大规模资本运作 + 正面新闻累积)
  capital_attention: 42 → 50      (+8, 持续热度)
  city_influence: 25 → 30         (+5, 整合资源)
  public_opinion[主角]: 28 → 35   (+7, 成功案例持续发酵)
  public_opinion[天盛原董事会]: -15 → -25  (持续负面)
  
⚠ 阈值触发: capital_attention ≥ 50
  → 全国财经媒体开始报道
  → 敌对势力（天盛竞争对手）开始关注
  → 新闻新增: "天盛易主，行业格局或将重塑"

新闻衰减:
  第 1 条新闻 "主角宣布收购天盛集团" → impact 衰减 30%
```

### 完整因果链摘要

```
动作链:
  ① 宣布收购
      ├─→ capital_attention: 5→20  (宣布效应)
      ├─→ city_influence: 3→11
      └─→ 生成新闻
  ② 市场发酵
      ├─→ capital_attention: 20→30 (新闻发酵)
      ├─→ city_influence: 11→15
      ├─→ 阈值触发: 地方财经介入
      └─→ 生成新闻
  ③ 收购完成
      ├─→ capital_attention: 30→42
      ├─→ city_influence: 15→25
      ├─→ public_opinion[主角]: 18→28
      ├─→ public_opinion[天盛原董事会]: 0→-15
      ├─→ 阈值触发: 地方势力介入
      ├─→ 势力: 天盛原董事会缩水+态度转为wary
      └─→ 生成新闻
  ④ 连锁反应
      ├─→ economy: stable→bull
      ├─→ capital_attention: 42→50
      ├─→ city_influence: 25→30
      ├─→ 阈值触发: 全国财经介入
      ├─→ 新势力: 敌对竞争对手注意
      └─→ 新闻叠加 + 旧新闻衰减
```

---

## 10. 可视化状态转移图

### 10.1 核心字段关联图

```
                  ┌───────────────┐
                  │  主角动作     │
                  └───────┬───────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
   ┌──────────┐    ┌────────────┐    ┌──────────┐
   │ 经济效应  │    │ 社会效应   │    │ 势力效应  │
   └────┬─────┘    └─────┬──────┘    └────┬─────┘
        │                │                │
        ▼                ▼                ▼
  ┌──────────┐    ┌────────────┐    ┌──────────────┐
  │ economy  │    │public_opin │    │ faction_power │
  │ cycle    │    │ion map     │    │关系网        │
  └────┬─────┘    └─────┬──────┘    └──────┬───────┘
        │                │                 │
        └──────────┬─────┴────────┬────────┘
                   │              │
                   ▼              ▼
            ┌──────────┐   ┌───────────┐
            │capital_at│   │city_influ │
            │tention   │   │ence       │
            └────┬─────┘   └─────┬─────┘
                 │               │
                 ▼               ▼
          ┌───────────┐   ┌────────────┐
          │ 阈值触发  │   │ 新闻/事件  │
          │ (新势力)  │   │ 生成      │
          └───────────┘   └────────────┘
```

### 10.2 状态变化时序

```
章 N: 主角动作 → world-simulator 更新 world_state → 事件日志 → 提供给 Draft Agent 写章 N+1
                                               ↓
                                         阈值检查
                                               ↓
                                         新势力/新事件 → 后续章节的约束条件
```

---

## 附录 A：性能与存储考量

| 项 | 说明 |
|----|------|
| world_state 文档大小 | ~2KB（5条新闻时） |
| world_event_logs 增长速度 | 每章 ~5-10 条日志 |
| 单部小说完整日志总量 | ~200-500 条（按 50 章估算） |
| 查询频率 | 每章写前读 1 次，写后更新 1 次 |
| 索引 | novel_id + chapter_id 复合索引 |
| 历史数据归档 | 超过 100 章的旧日志可归档到冷存储 |

## 附录 B：与其他 Agent 的关系

```
                   Orchestrator
                        │
        ┌───────────────┼───────────────┐
        │               │               │
   world-simulator  character-state   Draft Agent
   (更新世界状态)   (更新角色状态)   (读取状态后写作)
        │               │               │
        └───────────────┴───────────────┘
                        │
                   MongoDB
               (world_state + 其他集合)
```

- **world-simulator** 更新 `world_state` collection
- **character-state-agent** 更新 `characters` collection（角色声望受 world_state 影响）
- **Draft Agent** 写作前读取两者
- **Editor Agent** 编辑时可查看 world_state 时间线
- **Analytics Agent** 使用 world_event_logs 进行趋势分析
