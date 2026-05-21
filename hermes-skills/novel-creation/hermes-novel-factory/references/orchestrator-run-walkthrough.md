# Orchestrator Run Walkthrough — V3 实操记录

> 最后更新：2026-05-18
> 本文件记录 V3 架构下的 `new` / `continue` 完整执行过程，供续写会话参考

## V3 变化概览

V3 在 V2 基础上做了以下关键变化：

| 变化 | 说明 |
|------|------|
| Context Packet | 续写时自动组装状态包，不再依赖模型记忆 |
| 7 层 17 阶段 | 较 V2 13 阶段增加 4 个新阶段（World/Foreshadow/Validator/Event Sourcing） |
| 批量续写 | 推荐每轮 `continue` 写 3-5 章（约 4.5 分钟），写 20 章需要 6 轮 |
| 疲劳检测 | 自动检测重复剧情/情绪单色调，有告警则切换写悬疑线/副线 |

## 新项目创建 (`new`)

```bash
novel-factory new '都市系统流，3万字，开局足够吸引人，爽文'
```

### 执行流程（V3）

| 阶段 | 预估耗时 | 说明 |
|------|---------|------|
| 选型决策 | ~60s | 自动选型（不再等待 clarify 超时） |
| 0. Context Packet | 跳过（new 跳过） | |
| 1-4. Research + Outline + Character | ~300s | 同 V2，输出到 MongoDB |
| 5. World State 初始化 | ~10s | 创建初始 world_state（V3 新增） |
| 6. Foreshadow 规划 | ~15s | 伏笔队列初始化（V3 新增） |
| 7-9. Draft Ch1 + Validator + Editor | ~90s | 第 1 章写 + 校验 + 审校 |
| 10-12. State Update + Event Log | ~5s | 角色/世界状态更新 + 事件写入（V3 新增） |
| 14. Foreshadow 回收检查 | ~5s | 检查到期伏笔（V3 新增） |
| 16. Ops | ~5s | MongoDB 保存 |
| **总计** | **~500s** | |

### V2→V3 时间变化

- Research/Outline/Character 阶段不变（~300s）
- V3 新增阶段（5/6/8/10/11/12/14/15）约 +35s
- **总时间约 500s，比 V2 的 600s 减少**，主要因为选型不再需要 clarify 超时

## 续写 (`continue`)

```bash
# 指定 ARC 或从上次中断处继续
novel-factory continue '项目名'

# 或指定具体 ARC
novel-factory continue '项目名' --arc 'ARC-003'
```

### 执行流程（V3 continue）

| 步骤 | 预估 | 说明 |
|------|------|------|
| 0. Context Packet 恢复 | ~15s | 从 MongoDB 组装 Context Packet（V3 核心改进） |
| 7-9. Draft 3-5 章 + Validator + Editor | ~270s | 每章 ~90s（含校验和审校） |
| 10-12. State Update + Event Log | ~15s | 每章 ~5s 批量处理 |
| 14. Foreshadow 回收 | ~10s | 检查到期伏笔 |
| 15. Snapshot（如需） | ~5s | 每 100 events 触发 |
| 16. Ops | ~5s | MongoDB 保存 |
| **总计（3-5 章）** | **~320s** | 约 5.3 分钟 |

### Context Packet 恢复详解

续写时总控层自动执行：

```
1. 读 projects → 项目元数据（arc/字数/状态）
2. 读 event_log 最后 50 条 → 最近变更全景
3. 读 snapshot_store 最新快照 → 世界状态恢复
4. 读 world_state + character_states → 当前状态
5. 读 chapter_memory 最近 10 章 → 剧情摘要
6. 读 foreshadow_queue → 到期需回收的伏笔
7. 读 anti_fatigue → 疲劳检测报告
8. 组装为 Context Packet → 注入 draft agent
```

**为什么需要 Context Packet？** 纯靠模型记忆 10 章剧情 + 角色状态 + 世界状态几乎不可能准确。Context Packet 是结构化的压缩状态包，减少幻觉。

## 批次化策略（V3 推荐）

```bash
# 轮次 1: ARC-001 前 5 章
novel-factory continue '项目名' --chapters '1-5'

# 轮次 2: ARC-001 中 5 章
novel-factory continue '项目名' --chapters '6-10'

# 轮次 3: ARC-001 后 5 章
novel-factory continue '项目名' --chapters '11-15'

# 轮次 4: ARC-001 尾 5 章 + ARC 收束
novel-factory continue '项目名' --chapters '16-20'
```

每轮约 5.3 分钟，20 章 ≈ 21 分钟，尚可。如果超时（>600s），减少每轮章数或跳过 Editor。

## V3 抗疲劳策略

V3 的 anti_fatigue 系统会自动检测以下疲劳信号：

| 信号 | 检测阈值 | 建议动作 |
|------|---------|---------|
| 情绪色调单一（如连续 10 章"悬疑"） | >10 章同色调 | 插入轻松场景或回忆线 |
| 词汇重复率过高 | 同词在 3 章内出现 >5 次 | 通知 editor 替换词汇 |
| 对话占比过高/过低 | >70% 或 <15% | 调整叙事节奏 |
| 角色互动固定组合 | 同一对话对连续 5 章 | 引入第三方搅局 |

检测到疲劳后，系统会建议切换写法，但不强制——最终决定权在 writer agent。

## V2 已知问题在 V3 的解决状态

| V2 问题 | V3 解决方式 | 状态 |
|---------|------------|------|
| 600s 超时导致 Editor 未完成 | 批量化续写 + Context Packet 恢复 | ✅ |
| 章节间场景跳跃 | Live Validator 检查衔接 | ✅ |
| 角色在 50 章后消失 | Character State Machine 追踪所有角色 | ✅ |
| 伏笔埋了忘了收 | Foreshadow Queue 到期提醒 | ✅ |
| 世界观前后矛盾 | World State 追踪一致性 | ✅ |
| 续写时模型"不记得" | Context Packet 压缩状态注入 | ✅ |

## 故障排查

### 场景：continue 提示「项目不存在」或「无活动 ARC」

```bash
# 检查 MongoDB 项目状态
python3 -c "
from pymongo import MongoClient
client = MongoClient('mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin')
db = client['novel_factory']
from bson.json_util import dumps
for p in db.projects.find().sort('createdAt', -1).limit(3):
    print(dumps(p, indent=2))
"
```

### 场景：continue 写入的章节内容重复

检查 `anti_fatigue` collection：
```python
# 查看疲劳报告
for a in db.anti_fatigue.find().sort('createdAt', -1).limit(3):
    print(dumps(a, indent=2))
```

如果 `repetition_level` > 3，说明进入了创作疲劳区。建议换一个 ARC 或换一条故事线写。

### 场景：Context Packet 恢复后剧情错误

检查 event_log 的完整性：
```python
last_events = list(db.event_log.find({'project_id': pid}).sort('version', -1).limit(10))
print(f"最后事件数: {len(last_events)}")
print(f"最新版本: {last_events[0]['version'] if last_events else '无'}")
```

如果 event_log 为空，说明 event sourcing 未正常工作——检查阶段 12 的写入逻辑。
