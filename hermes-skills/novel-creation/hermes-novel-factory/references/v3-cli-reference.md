# V3 CLI 使用说明（novel-factory）

## 安装

```bash
# 已通过 symlink 安装到 ~/.local/bin/novel-factory
# 真实脚本路径：~/.hermes/skills/content-creation/hermes-novel-factory/scripts/novel-factory
which novel-factory  # 预期：/root/.local/bin/novel-factory（指向上述路径的软链）
```

## 子命令总表

| 子命令 | 完整用法 | 功能 | 内部调用链 |
|--------|---------|------|-----------|
| `new` | `novel-factory new '<需求描述>'` | 启动新项目，自动初始化 V3 MongoDB 集合 | `init_collections.py` → orchestrator（Research → Outline → Character → Draft） |
| `continue` | `novel-factory continue <项目名> [章节号]` | 中断恢复模式，自动组装 Context Packet 后续写 | `resume-project.py` status → `build-context-packet.py` → orchestrator → draft → `validate-chapter.py` → `snapshot-manager.py` → `event-log-writer.py` |
| `status` | `novel-factory status <项目名>` | 显示项目状态、恢复策略、Context Packet 摘要 | `resume-project.py` status |
| `snapshot` | `novel-factory snapshot <项目名> <章节号>` | 手动保存状态快照到 MongoDB + 本地文件 | `snapshot-manager.py` save |
| `validate` | `novel-factory validate <项目名> <章节号>` | 运行 7 维一致性校验，自动从数据库获取章节内容 | `validate-chapter.py` check（自动 MongoDB 读取） |
| `event` | `novel-factory event <项目名> <事件类型> <章节> [--data JSON]` | 手动写入事件溯源日志 | `event-log-writer.py` log |
| `arc` | `novel-factory arc <项目名> <arc_id>` | 直接写入指定 ARC 的完整内容 | `build-context-packet.py` → orchestrator |
| `refresh` | `novel-factory refresh <项目名>` | 触发全量数据刷新/重整理 | → orchestrator（analytics → 全库审计） |
| `-h` / `--help` | `novel-factory --help` | 显示帮助信息 | — |
| `*`（默认） | `novel-factory '<任意需求>'` | 向后兼容模式，直接路由到 orchestrator | → orchestrator |

## 详细说明

### `new` — 新项目启动

```bash
novel-factory new '写一本男频狼人吸血鬼爽文，目标300万字，番茄平台'
```

**执行流程**：
1. 运行 `init_collections.py` 确保所有 V3 集合存在（幂等）
2. 路由到 orchestrator，执行 Research → Outline → Character → Draft × N
3. 所有中间产物写入 MongoDB `novel_factory` 库
4. **注意**：超过 2 章的项目大概率在 `new` 期间超时（600s 限制）
   - 超时不是错误，项目数据已完整入库
   - 用 `novel-factory continue '项目名'` 接上继续写

**时间预算**（CPU + API 实测）：

| 项目规模 | 预计时间 | 推荐策略 |
|----------|---------|---------|
| 1-2 章（~3000 字） | 5-8 min | 一次 `new` 完成 |
| 3 万字（~20 章） | 40-60 min | `new` → `continue` |
| 10 万字（ARC） | 2-3 小时 | `new` → `continue` × N |

### `continue` — 中断恢复（V3 核心功能）

```bash
novel-factory continue '诡异游戏：我的规则别人看不见'
novel-factory continue '诡异游戏' 136  # 指定起始章节
```

**V3 流程**：
1. `resume-project.py status` → 从 `event_log` 和 `snapshot_store` 推断恢复策略
2. 三种策略自动选择：
   - `recover_snapshot` — 存在快照 → 从快照恢复状态 → 继续下一章
   - `clean_continue` — 无快照但有 `event_log` → 从 event_log 重建状态 → 继续
   - `edit_last_chapter` — 最后一章未完成 → 回到 editor 阶段
3. `build-context-packet.py` → 组装 Context Packet（world_state + character_states + active_plot_threads + last_10_chapters + foreshadow_queue）
4. Context Packet 注入 orchestrator → draft agent 续写
5. 写完后 `validate-chapter.py` 校验 → `snapshot-manager.py` 保存 → `event-log-writer.py` 记录

### `status` — 项目状态

```bash
novel-factory status '诡异游戏'
```

**输出内容**：JSON 格式，包含：
- project（标题、体裁、字数规划）
- progress（最后完成章节、下一章、数据库章节数）
- strategy（推荐恢复策略 + 原因）
- running_status（是否有后台进程在写）
- context_packet（完整 Context Packet，含 11 角色/20 伏笔/10 章摘要）
- next_steps（建议的下一步操作清单）

### `validate` — 章节校验

```bash
novel-factory validate '诡异游戏' 135
```

**7 维校验维度**：
1. 金额一致性 — 大额数字跳跃检测
2. 战力等级一致性 — 战力突升检测
3. 时间线一致性 — 事件顺序、日期矛盾
4. 称呼一致性 — 角色称呼一致性
5. 人设一致性 — 角色性格/能力偏离
6. 地点一致性 — 场景位置矛盾
7. 物品/技能一致性 — 物品状态延续

**自动获取内容**：无需提供 `--content-file`，脚本自动从 MongoDB 读取：
1. 先查 `novel.chapters`（V1 兼容层）
2. 再查 `novel_factory` 库
3. 最后尝试 `filename` 字段指向的本地文件

### `event` — 事件日志

```bash
novel-factory event 'proj_gui-yi-you-xi_d3acfcdd' chapter_generated 136 --data '{"word_count":2800}'
```

**事件类型枚举**：`chapter_started`, `chapter_generated`, `chapter_validated`, `editor_completed`, `world_updated`, `character_states_updated`, `foreshadow_created`, `foreshadow_resolved`, `snapshot_saved`, `arc_completed`, `project_created`, `resume_session`, `error`

### `snapshot` — 状态快照

```bash
novel-factory snapshot '诡异游戏' 135
```

保存范围：
- 项目元数据（projects）
- 世界观状态（world_state）
- 角色动态状态（character_states 全量）
- 当前 ARC 规划（arc_plans 活跃项）
- 时间线（timeline 近 50 条）
- 生成时间戳

## V3 Agent Profiles

V3 新增 5 个可独立调用的 agent profiles：

| Profile | 命令 | 职责 |
|---------|------|------|
| **arc-manager** | `hermes -p arc-manager chat` | 四层 ARC 规划（World→Phase→Beat→Chapter），动态调整 |
| **character-state-agent** | `hermes -p character-state-agent chat` | 角色状态机，每章后更新情绪/信任/战力/关系图 |
| **world-simulator** | `hermes -p world-simulator chat` | 世界状态模拟器，推演经济/舆论/势力因果链 |
| **foreshadow-manager** | `hermes -p foreshadow-manager chat` | 伏笔队列管理，deadline 监控，强制回收提醒 |
| **live-validator** | `hermes -p live-validator chat` | 7 维实时一致性校验（金额/战力/时间线/称呼/人设/地点/物品） |

## MongoDB 连接信息

```
数据库: novel_factory
地址:   192.168.2.30:27017
认证:   mongo_8F6dTZ / mongo_dxx8nA
参数:   ?authSource=admin

7 个 V3 集合:
  character_states — 角色动态状态
  world_state — 世界状态快照
  foreshadow_queue — 伏笔队列（带 deadline）
  event_log — 事件溯源日志
  snapshot_store — 状态快照
  arc_plans — 四层 ARC 规划
  anti_fatigue — 七维疲劳检测
```
