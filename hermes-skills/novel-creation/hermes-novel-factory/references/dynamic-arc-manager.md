# 动态 ARC 系统（V3）

## 1. 概述

动态 ARC Manager 是 V3 的核心战略层组件，解决 V2 Outline 一次性静态生成 20 章的致命缺陷。其核心理念是：**ARC 结构是活的**——根据写作进度、读者反馈、角色热度动态调整，而非一次性定死。

系统定位：位于 Story Engine 之上、章节生成器之下，负责**宏观叙事节奏的实时编排**。

---

## 2. 四层 ARC 体系

动态 ARC 系统将整本书拆分为四层嵌套结构，每层有独立的生命周期和管理粒度：

```
World ARC         (1 个)     ← 整本书的终极目标，500 万字
  └─ Phase ARC    (5-6 个)   ← 完整的故事阶段，~100 章
       └─ Beat ARC   (~30 个)  ← 一个故事节拍，~20 章
            └─ Chapter Goal   (~600 个) ← 当下写作的微观目标，3 章
```

### 2.1 World ARC（世界级 ARC）

| 属性 | 值 |
|------|-----|
| 数量 | 1（整本书唯一） |
| 跨度 | 全本（~500 万字，~600 章） |
| 状态 | 永不 archived |
| 内容 | 终极主题、世界观基石、最终矛盾的种子 |
| 变更 | 仅当作者主动发起"世界观重构"时修改 |

**定义字段：**
- `world_theme` — 整本书的唯一核心主题
- `ultimate_conflict` — 最终矛盾的抽象描述
- `world_end_condition` — 世界 ARC 完成条件（如：主角达成终极目标）
- `fates_unchanged` — 不可动摇的关键命运节点（作者锁死的事件）

### 2.2 Phase ARC（阶段 ARC）

| 属性 | 值 |
|------|-----|
| 数量 | 5-6 个（V2 6-ARC 模板映射） |
| 跨度 | ~100 章 |
| 状态机 | `planning → active → climax_building → completed → archived` |
| 重构触发器 | 每 30 章自动触发 Phase ARC 结构优化 |

**映射到 V2 六弧模板：**

| Phase | V2 弧 | 章节范围 | 核心任务 |
|-------|-------|---------|---------|
| Phase 1 | 起 | 1-100 | 世界建立、低冲突引入 |
| Phase 2 | 承 | 101-200 | 风险升级、首个主要反派 |
| Phase 3 | 爆 | 201-300 | 冲突爆发、中期转折 |
| Phase 4 | 反转 | 301-400 | 反转、新力量体系层 |
| Phase 5 | 高潮 | 401-500 | 巅峰冲突、全部伏笔回收 |
| Phase 6 | 余波 | 501-600 | 结局、新世界种子 |

**定义字段：**
- `phase_goal` — 本阶段的核心叙事目标
- `phase_antagonist` — 本阶段的主要对手（必须与其它 Phase 的 antagonist 不同 archetype）
- `conflict_escalation_level` — 1-10 的冲突烈度指数（逐阶段递增）
- `required_payoffs` — 本阶段必须回收的伏笔列表（引用 foreshadow IDs）
- `required_seeds` — 本阶段必须种下的新伏笔列表
- `climax_event` — 阶段高潮事件的描述
- `transition_hook` — 衔接下一阶段的钩子

### 2.3 Beat ARC（小高潮 ARC）

| 属性 | 值 |
|------|-----|
| 数量 | ~30 个（每个 Phase 5-6 个 Beat） |
| 跨度 | ~20 章 |
| 状态机 | `planning → active → completed → archived` |
| 重算触发器 | 每 10 章自动触发 Beat ARC 方向调整 |

**Beat ARC 模板（七步结构）：**

```
起 → 承 → 爆 → 反转 → 高潮 → 余波 → 新坑
```

**定义字段：**
- `beat_theme` — 本 Beat 的独特主题
- `beat_antagonist` — 本 Beat 的冲突对手
- `primary_conflict_type` — 冲突类型（战斗/智斗/情感/探索/政治/生存等）
- `twist_schedule` — 本 Beat 内的 twist 时间表（第几章发生什么 twist）
- `emotional_arc` — 读者情感曲线设计（起伏节奏）
- `pacing_target` — 节奏目标（fast/medium/slow burn）
- `foreshadow_plants` — 本 Beat 内种下的新伏笔
- `foreshadow_payoffs` — 本 Beat 内回收的旧伏笔
- `character_spotlight` — 本 Beat 的主视角角色

### 2.4 Chapter Goal（即时章节目标）

| 属性 | 值 |
|------|-----|
| 数量 | ~600 个（每章一个，但以 3 章为单位规划） |
| 跨度 | 3 章（滚动窗口） |
| 状态机 | `planned → writing → drafted → revised → finalized` |
| 调整粒度 | 每次生成新章时滚动更新 |

**定义字段：**
- `chapter_purpose` — 本章在全弧中的功能（setup/payoff/transition/character_moment/world_building/climax）
- `key_scene_goal` — 本章关键场景要达成的目标
- `pov_character` — 视角角色
- `emotional_target` — 目标读者情绪（tension/release/hope/despair/surprise/warmth）
- `cliffhanger_required` — 是否需要章末悬念
- `word_count_target` — 字数目标区间
- `must_include` — 必须包含的元素列表
- `must_avoid` — 必须避免的元素列表

---

## 3. MongoDB Schema：arc_plans Collection

### 3.1 通用字段（所有 ARC 类型共享）

```json
{
  "_id": "ObjectId",
  "arc_id": "string (唯一标识，如 'world_001', 'phase_002', 'beat_015', 'chapter_342')",
  "type": "string (enum: 'world' | 'phase' | 'beat' | 'chapter')",
  "parent_arc_id": "string (引用父级 ARC 的 arc_id，world 级为 null)",
  "status": "string (状态机，见下方)",
  "goal": "string (本 ARC 的一句话目标)",
  "conflict": "object (冲突描述)",
  "twists": "array[string] (主要 twist 列表)",
  "created_at": "ISODate",
  "updated_at": "ISODate",
  "version": "integer (乐观锁版本号)",
  "history": "array[object] (变更历史，见 3.6)",
  "metadata": "object (扩展字段，按 type 不同)",
  "completion_criteria": "array[string] (完成条件 checklist)"
}
```

### 3.2 状态机

```
world:    active (永不改变)
phase:    planning → active → climax_building → completed → archived
          (可回退: active ←→ planning, climax_building → active)
beat:     planning → active → completed → archived
          (可回退: completed → active [若需扩展])
chapter:  planned → writing → drafted → revised → finalized
```

状态转换约束：
- `planning → active`：必须有完整的 `conflict` 和 `twists` 定义
- `active → climax_building`：仅 phase 类型，阶段进度 > 70%
- `completed → archived`：父级 ARC 确认完成后自动触发
- 任何回退操作需记录原因到 `history`

### 3.3 Phase ARC 专有字段

```json
{
  "phase_number": "integer",
  "chapter_start": "integer",
  "chapter_end": "integer",
  "escalation_level": "integer (1-10)",
  "antagonist_id": "string (引用角色 ID)",
  "antagonist_archetype": "string",
  "required_payoffs": ["foreshadow_id_1", "foreshadow_id_2"],
  "required_seeds": ["foreshadow_id_3", "foreshadow_id_4"],
  "climax_event": "string",
  "transition_hook": "string",
  "reconstruct_count": "integer (重构次数统计)",
  "last_reconstruct_at": "ISODate"
}
```

### 3.4 Beat ARC 专有字段

```json
{
  "beat_number": "integer (在 Phase 内的序号)",
  "chapter_start": "integer",
  "chapter_end": "integer",
  "beat_theme": "string",
  "primary_conflict_type": "string",
  "emotional_arc": {
    "opening_emotion": "string",
    "rising_emotion": "string",
    "climax_emotion": "string",
    "falling_emotion": "string",
    "closing_emotion": "string"
  },
  "pacing_target": "string (fast/medium/slow_burn)",
  "twist_schedule": [
    {"chapter_offset": 5, "twist": "twist description"},
    {"chapter_offset": 12, "twist": "twist description"}
  ],
  "character_spotlight": ["char_id_1", "char_id_2"],
  "foreshadow_plants": ["foreshadow_id"],
  "foreshadow_payoffs": ["foreshadow_id"],
  "recalc_count": "integer (重算次数统计)",
  "last_recalc_at": "ISODate",
  "recalc_reasons": ["array[string] (历次重算原因记录)"]
}
```

### 3.5 Chapter Goal 专有字段

```json
{
  "chapter_number": "integer",
  "chapter_purpose": "string (setup/payoff/transition/character_moment/world_building/climax)",
  "key_scene_goal": "string",
  "pov_character": "string",
  "emotional_target": "string",
  "cliffhanger_required": "boolean",
  "word_count_target": {"min": 4000, "max": 6000},
  "must_include": ["element_1", "element_2"],
  "must_avoid": ["element_1"],
  "draft_content_ref": "string (引用已生成的草稿内容路径)",
  "revision_notes": ["string"]
}
```

### 3.6 变更历史记录

每个 ARC 文档维护一个 `history` 数组，记录所有重要变更：

```json
{
  "history": [
    {
      "timestamp": "ISODate",
      "action": "string (created/status_change/recalc/reconstruct/rebuild/prune/promote/manual_edit)",
      "trigger": "string (auto/scheduled/manual)",
      "trigger_detail": "string (触发原因详细描述)",
      "changes": "object (变更内容的摘要)",
      "changed_by": "string (agent_id 或 'author')",
      "version_before": "integer",
      "version_after": "integer"
    }
  ]
}
```

---

## 4. arc-manager Agent 职责与调度策略

arc-manager 是一个后台常驻 agent，按固定间隔执行周期性任务。

### 4.1 周期任务调度表

| 任务 | 周期 | 级别 | 触发方式 | 执行时间估计 |
|------|------|------|----------|-------------|
| **recalc**（重算） | 每 10 章 | Beat ARC | 自动调度 | ~30 秒 |
| **reconstruct**（重构） | 每 30 章 | Phase ARC | 自动调度 | ~2 分钟 |
| **rebuild**（重建） | 每 100 章 | World 状态 | 自动调度 | ~5 分钟 |
| **prune**（修剪） | 每 10 章 | 角色池 | 自动调度 | ~10 秒 |
| **promote**（提升） | 每 5 章 | 角色池 | 自动调度 + 手动触发 | ~10 秒 |
| **health_check**（健康检查） | 每 1 章 | 全局 | 自动调度 | ~5 秒 |

### 4.2 recalc（重算方向）

**触发条件：** 每完成 10 章，或 analytics agent 发出 `DIRECTION_ALERT`。

**执行流程：**
```
1. 收集最近 10 章的 analytics 数据（读者情绪、留存、角色热度）
2. 评估当前 active Beat ARC 的进度（% complete）
3. 根据 analytics 判断是否需要调整方向：
   a. 读者情绪偏离预期 → 调整下一个 Beat 的 pacing_target
   b. 角色热度异常 → 触发 promote 或 prune 作为副作用
   c. 冲突烈度不适应 → 调整 primary_conflict_type
   d. 伏笔回收率低 → 增加 payoff 密度
4. 输出调整后的下一个 Beat ARC 规划
5. 如果调整幅度 > 阈值，通知 写作 agent 调整写作方向
```

**输出：**
- 更新当前 Beat ARC 的 `recalc_count`、`last_recalc_at`、`recalc_reasons`
- 如果调整幅度大，创建新的 Beat ARC 规划文档（status=planning）
- 生成 `ARC_RECALC_EVENT` 写入事件总线

**调整幅度分级：**

| 级别 | 阈值 | 动作 |
|------|------|------|
| minor | 调整 1-2 个字段 | 仅更新当前 Beat ARC |
| moderate | 调整 3-4 个字段 或 修改 twist_schedule | 更新 + 通知 writing agent |
| major | 更换 beat_theme 或 primary_conflict_type | 更新 + 通知 writing agent + 通知 planner |

### 4.3 reconstruct（重构阶段结构）

**触发条件：** 每完成 30 章，或 Phase ARC 进度偏离 > 20%。

**执行流程：**
```
1. 加载整个 Phase ARC 的所有 Beat ARC
2. 收集本 Phase 所有完成的 Beat 的 analytics 数据
3. 评估 Phase ARC 的整体结构健康度：
   a. 冲突烈度曲线是否符合预期
   b. 伏笔种植 vs 回收比例
   c. 角色利用率
   d. 读者留存趋势
4. 对后续未完成的 Beat ARC 进行结构性优化：
   a. 合并或拆分节奏过慢/过快的 Beat
   b. 调整剩余 Beat 的 pacing_target
   c. 重新分配伏笔种植和回收计划
   d. 调整 climax_building 阶段的节奏
5. 如果 Phase 的 goal 已不再合理，更新 phase_goal
6. 输出重构报告
```

**输出：**
- 更新 Phase ARC 的 `reconstruct_count`、`last_reconstruct_at`
- 批量更新剩余 Beat ARC 的规划
- 生成 `ARC_RECONSTRUCT_EVENT` 写入事件总线

### 4.4 rebuild（重建世界状态）

**触发条件：** 每完成 100 章，或 World ARC 出现重大偏离。

**执行流程：**
```
1. 加载 World ARC 定义
2. 评估当前世界状态 vs 原始规划：
   a. 地图扩张进度是否符合预期
   b. 新势力/新文明引入节奏
   c. 力量体系演化路径
   d. 终极矛盾的前置条件积累
3. 决定是否需要引入新地图/新势力：
   a. 如果当前地图已探索完毕 → 规划新地图
   b. 如果当前势力格局已稳定 → 引入新势力制造动荡
   c. 如果力量体系需要升级 → 设计新力量层
4. 评估最终目标的可达性，必要时调整 world_end_condition
5. 输出重建报告，更新世界观蓝图
```

**输出：**
- 更新 World ARC 的 metadata
- 更新世界观文档（world-building reference）
- 生成 `ARC_REBUILD_EVENT` 写入事件总线

### 4.5 prune（自动淘汰无用角色）

**触发条件：** 任意角色连续 20 章未出场，自动触发检查。

**执行流程：**
```
1. 扫描所有角色，标记最近出场章节
2. 对连续 20 章未出场角色：
   a. 检查角色在 arc_plans 中的引用（是否在 future Beat 中有规划）
   b. 如果有规划 → 保留，标记为 "dormant_scheduled"
   c. 如果无规划 → 进入 standby 池，标记 status = "standby"
3. 对连续 50 章未出场且无 future 规划的角色：
   a. 建议作者是否彻底移除
   b. 如果作者确认，标记 status = "archived"
4. 输出 prune 报告
```

**Standby 角色的处理：**
- 从 active 角色池中移除，不再占用 token budget
- 保留完整角色资料，可在 future ARC 中 reactivate
- reactivate 时自动生成角色状态摘要（这段时间角色在做什么）

### 4.6 promote（自动提升高热角色戏份）

**触发条件：** 每 5 章自动检查，或 analytics agent 发送 `CHARACTER_HOT_ALERT` 时立即触发。

**执行流程：**
```
1. 从 analytics agent 获取角色热度排名
2. 识别热度 Top 3 但当前戏份不足的角色
3. 对每个待 promote 角色：
   a. 检查角色在当前 Beat ARC 中的出镜规划
   b. 如果出镜率 < 阈值 → 增加 upcoming chapters 中的出镜计划
   c. 如果角色适合当前冲突 → 提升为 sub-antagonist 或 key ally
   d. 如果角色有未展开的背景 → 策划专门的 character_moment chapter
4. 调整 Chapter Goal 的 must_include，增加 promote 角色的戏份
5. 输出 promote 报告
```

**提升幅度：**

| 热度级别 | 当前戏份 | 提升动作 |
|----------|----------|----------|
| Top 1-3 | < 10% 出镜 | 增加为 upcoming 5 章的核心配角 |
| Top 1-3 | 10-30% 出镜 | 策划一个 character_moment 章节 |
| Top 1-3 | > 30% 出镜 | 考虑提升为 Phase ARC 的 sub-antagonist |
| 黑马（新角色突入 Top 5） | 任何 | 立即增加出镜 + 策划背景展开 |

---

## 5. 补偿机制

当 ARC 执行出现偏差时（读者反馈差、节奏崩坏、冲突疲软等），补偿机制自动触发。

### 5.1 触发条件与对应补偿

| 触发条件 | 检测指标 | 补偿动作 |
|----------|----------|----------|
| 读者情绪低迷 | analytics: sentiment < 0.3 持续 3 章 | 插入高情感冲击章节（emotional_target=relief/hope） |
| 节奏过慢 | analytics: pacing_score < 0.4 | 压缩后续 2 章内容量，增加冲突密度 |
| 冲突疲软 | analytics: tension_score < 0.3 | 引入意外的 twist 或新 antagonist 行动 |
| 角色脱节 | analytics: character_engagement < 0.3 | 执行 promote（最高优先级），策划角色高光章节 |
| 伏笔遗忘 | foreshadow_payoff_ratio < 0.3 | 在下一 Beat 增加 2+ 旧伏笔回收 |
| 读者流失 | analytics: retention < 0.7 | 执行 "救火协议"（见 5.2） |
| 世界观疲劳 | analytics: world_novelty < 0.3 | 触发 rebuild（轻量版），引入新地图/新势力 |

### 5.2 救火协议（Firefighting Protocol）

当读者留存率连续 5 章低于 0.7 时触发。

**执行流程：**
```
1. 暂停当前 Beat ARC 的正常推进
2. arc-manager 与 analytics agent 联合分析流失原因
3. 在 3 章内执行紧急补救：
   a. 如果是因为冲突疲软 → 插入 twist 章节
   b. 如果是因为角色无趣 → 执行 promote，策划 high-stakes 场景
   c. 如果是因为世界观枯燥 → 揭示隐藏设定
   d. 如果是因为节奏太慢 → 跳过过渡内容，直接进入高潮
4. 救火章节优先于当前 Chapter Goal 规划
5. 救火完成后恢复常规调度
```

### 5.3 补偿效果评估

每次补偿执行后，analytics agent 在 3 章内持续监控效果：

- **有效**（指标回升到阈值以上）：补偿机制终止，记录到案例库
- **无效**（指标未回升）：升级补偿力度，或触发更高级别重构
- **负面效果**（指标更差）：立即回滚补偿，触发 reconstruct

---

## 6. 与 analytics agent 的集成

arc-manager 与 analytics agent 通过**事件总线**和**共享状态**进行双向通信。

### 6.1 analytics agent → arc-manager 的事件

| 事件名称 | 负载 | 触发动作 |
|----------|------|----------|
| `DIRECTION_ALERT` | `{reason, metrics, severity}` | 触发 recalc |
| `CHARACTER_HOT_ALERT` | `{char_id, rank, trend}` | 触发 promote |
| `CHARACTER_COLD_ALERT` | `{char_id, absent_chapters}` | 触发 prune 检查 |
| `PACING_CRISIS` | `{beat_arc_id, pacing_score}` | 触发补偿机制 |
| `RETENTION_DROP` | `{retention_rate, duration}` | 触发救火协议 |
| `FORESHADOW_OVERDUE` | `{foreshadow_ids, overdue_chapters}` | 触发补偿（伏笔回收） |
| `SENTIMENT_REPORT` | `{chapter_range, sentiment_curve}` | 更新 emotional_arc 规划 |

### 6.2 arc-manager → analytics agent 的事件

| 事件名称 | 负载 | 触发动作 |
|----------|------|----------|
| `ARC_RECALC_EVENT` | `{beat_arc_id, changes}` | analytics 更新评估基准 |
| `ARC_RECONSTRUCT_EVENT` | `{phase_arc_id, changes}` | analytics 重建阶段评估模型 |
| `ARC_REBUILD_EVENT` | `{world_state_changes}` | analytics 重置世界观评估指标 |
| `COMPENSATION_TRIGGERED` | `{type, target, action}` | analytics 进入监控模式 |
| `PROMOTION_EXECUTED` | `{char_id, chapters_affected}` | analytics 跟踪角色热度变化 |
| `PRUNE_EXECUTED` | `{char_ids, action}` | analytics 更新角色池统计 |

### 6.3 共享状态

两个 agent 共同维护一个 `analytics_arc_bridge` 集合：

```json
{
  "_id": "ObjectId",
  "beat_arc_id": "string",
  "phase_arc_id": "string",
  "analytics_snapshot": {
    "sentiment_avg": "float",
    "tension_avg": "float",
    "pacing_score": "float",
    "retention_rate": "float",
    "character_engagement": "object",
    "foreshadow_payoff_ratio": "float",
    "world_novelty": "float"
  },
  "arc_health_score": "float (综合健康度 0-1)",
  "last_sync_at": "ISODate",
  "pending_alerts": ["array[string]"],
  "compensation_active": "boolean",
  "compensation_type": "string or null"
}
```

---

## 7. 实现注意事项

### 7.1 数据一致性

- arc_plans 的更新使用 MongoDB 乐观锁（version 字段）
- 跨 ARC 类型更新（如 recalc 同时更新 Beat 和 Chapter）使用事务
- history 记录不可变，仅追加

### 7.2 性能考量

- recalc 和 prune 设计为轻量操作（~30 秒），reconstruct 和 rebuild 为重量操作
- 重量操作安排在写作间隔期（如作者休息时段）执行
- analytics_arc_bridge 的更新频率最高为每章一次

### 7.3 人工兜底

- 所有自动操作的变更都经过 `history` 记录，支持一键回滚
- arc-manager 不直接修改正在写作的章节内容，只更新规划
- 作者可随时手动覆盖任何 ARC 规划，覆盖后 24 小时内自动调度暂停
- 提供 `force_recalc`、`force_reconstruct`、`force_rebuild` 手动触发接口

### 7.4 启动与初始化

首次启用时，arc-manager 执行初始化流程：

```
1. 从 V2 Outline 导入 6-ARC 结构，创建 World ARC + 6 个 Phase ARC
2. 为 Phase 1 创建首个 Beat ARC（planning 状态）
3. 为前 10 章创建 Chapter Goal（planned 状态）
4. 执行初始角色池扫描（标记所有角色的最近出场章节）
5. 通知 analytics agent 初始化评估基准
6. 启动周期性调度器
```

---

## 8. 附录：术语表

| 术语 | 英文 | 定义 |
|------|------|------|
| ARC | Arc | 故事弧，一段有起承转合的结构化叙事单元 |
| recalc | Recalculate | 基于新数据重新计算 Beat ARC 的方向 |
| reconstruct | Reconstruct | 对 Phase ARC 的结构进行优化调整 |
| rebuild | Rebuild | 重建世界观状态，引入新地图/新势力 |
| prune | Prune | 淘汰长期未出场的无用角色 |
| promote | Promote | 提升高热角色的戏份权重 |
| twist | Twist | 情节转折，读者预期之外的剧情变化 |
| cliffhanger | Cliffhanger | 章末悬念，引导读者继续阅读 |
| pacing | Pacing | 叙事节奏，控制信息释放的速度 |
| compensation | Compensation | 当 ARC 偏离预期时的自动修复机制 |
|救火协议 | Firefighting Protocol | 应对读者大量流失的紧急补救流程 |
