# 起点精品小说工厂 · 多 Agent 工业化创作系统

基于 HermesAgent + MongoDB + Kanban 的 500 万字长篇创作系统。

## 架构概览

8 个 Agent 角色通过 Kanban 看板流转任务，每个角色有独立 profile，运行时通过 `delegate_task` 切换。

```
用户 → Orchestrator（看板调度）
         ├── World Builder（世界观）
         ├── Character Designer（角色）
         ├── ARC Planner（剧情架构）
         ├── Draft Writer（正文）
         ├── Editor（审校）
         ├── Reviewer（审核）
         └── Memory Manager（数据库）
```

## 目录结构

```
novel_factory/
├── profiles/              # 8 个 Agent 的 system prompt
│   ├── orchestrator.md    # 总调度师
│   ├── world-builder.md   # 世界架构师
│   ├── arc-planner.md     # 剧情架构师
│   ├── character-designer.md  # 角色设计师
│   ├── draft-writer.md    # 正文写手
│   ├── editor.md          # 审校编辑
│   ├── reviewer.md        # 精品审核官
│   └── memory-manager.md  # 记忆管理器
├── kanban.py              # Kanban 卡片管理工具
└── README.md
```

## 使用方式

### 1. 启动新书项目

对 Hermes 说：

```
启动新书：书名《XXX》，题材：玄幻/修仙/高武/末世/科幻
```

Orchestrator 自动：
- 初始化 projects 记录
- 创建 Research → World Building → Character Design → ARC Planning 卡片
- 依次加载 profile 调 Agent，产出世界观、角色、ARC 规划

### 2. 日更生产

对 Hermes 说：

```
日更 3 章
```

Orchestrator 自动：
- 取出 Draft Queue 卡片 → 调 draft-writer
- 自动创建 editing 卡片 → 调 editor
- 自动创建 review 卡片 → 调 reviewer
- 通过后 → publishing，更新进度

### 3. 新 ARC 启动

对 Hermes 说：

```
启动 ARC 3
```

Orchestrator 自动：
- 调 world-builder 更新世界状态
- 调 character-designer 更新角色状态
- 调 arc-planner 规划新 ARC
- 创建 Outline 和 Draft 卡片

### 4. 查看进度

对 Hermes 说：

```
查看项目进度
```

Orchestrator 返回：
- 当前字数 / 目标字数
- 当前 ARC / ARC 总数
- Kanban 队列概况
- Reviewer 评分趋势

## Kanban 看板流转

```
Idea Pool → Research → World Building → Character Design
→ ARC Planning → Outline → Draft Queue → Editing
→ Review → Publishing → Archived
```

## Profile 切换机制

Orchestrator 通过 `read_file` 加载目标 Agent 的 profile 文件内容，将其注入 `delegate_task` 的 context 字段：

```
1. 读 ~/novel_factory/profiles/draft-writer.md
2. delegate_task(context=profile内容 + 具体任务, ...)
3. 子 Agent 以 draft-writer 的身份执行任务
4. 返回产出 → Orchestrator 更新 Kanban
```

## MongoDB

- 数据库：`novel_qidian`
- 连接：`mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/`
- 12 个 Collection：projects, world_bible, characters, arcs, chapters, timeline, foreshadows, factions, cultivation_system, kanban_cards, agent_logs, version_history

## 核心规则

- 所有长期信息必须进入 MongoDB
- 所有 Agent 通过 Kanban 卡片收发任务
- 正文生成前必须读取历史记忆
- 世界观修改必须经 world-builder
- 战力升级必须受 power_ceiling 约束
- 每章必须经 editor + reviewer
- 对话统一使用 ASCII 双引号 ""
- 禁止模板化表达和 AI 腔
