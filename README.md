# 起点小说工厂 · 自动化调度系统

基于 HermesAgent V3 + MongoDB + 8 Agent Profile 的工业化长篇小说创作系统。

## 架构

```
用户
  ↓
orchestrator.py（调度主控）
  ↓
agent_runner.py（Agent 调用封装）
  ↓  hermes -p qidian-<agent>
8 个独立 Agent Profile
  ↓
memory_service.py（MongoDB 读写）
  ↓
MongoDB novel_qidian（12 个集合）
```

## Agent 角色

| Profile | 角色 | 职责 |
|---------|------|------|
| qidian-orchestrator | 总调度师 | 任务分解、Kanban 管理 |
| qidian-world-builder | 世界架构师 | 世界观、修炼体系、势力 |
| qidian-arc-planner | ARC 规划师 | 长篇结构、反转、伏笔 |
| qidian-character-designer | 角色设计师 | 人设、关系、成长线 |
| qidian-draft-writer | 正文写手 | 唯一写章节的 Agent |
| qidian-editor | 审校编辑 | 精修、一致性、反重复 |
| qidian-reviewer | 精品审核官 | 起点风格把关 |
| qidian-memory-manager | 记忆管理器 | MongoDB 数据管理 |

## 使用方式

### 交互模式

```bash
cd ~/novel_factory/scripts
python3 orchestrator.py
```

### 命令行模式

```bash
# 创建新书（自动跑完准备阶段：研究→世界观→角色→ARC→大纲）
python3 orchestrator.py new "书名" "类型"

# 批量生成章节
python3 orchestrator.py batch <项目ID> 10

# 日更（写一章）
python3 orchestrator.py daily <项目ID>

# 查看状态
python3 orchestrator.py status [项目ID]
python3 orchestrator.py list

# 恢复中断项目
python3 orchestrator.py resume <项目ID>
```

### 完整流程

```
1. python3 orchestrator.py new "修仙模拟器" "修仙"
   → 自动完成：选题研究 → 世界观 → 角色 → ARC → 大纲
   
2. python3 orchestrator.py batch <项目ID> 10
   → 自动生成 10 章（每章：写→审→改→发布）
   
3. python3 orchestrator.py daily <项目ID>
   → 每天一章
```

## 文件结构

```
novel_factory/
├── scripts/
│   ├── memory_service.py    # MongoDB 数据服务层
│   ├── agent_runner.py       # Hermes Agent 调用封装
│   └── orchestrator.py       # 主调度脚本（入口）
├── profiles/                 # Agent 提示词（参考用）
│   ├── orchestrator.md
│   ├── world-builder.md
│   ├── arc-planner.md
│   ├── character-designer.md
│   ├── draft-writer.md
│   ├── editor.md
│   ├── reviewer.md
│   └── memory-manager.md
└── README.md
```

## 依赖

- Python 3.8+
- pymongo
- Hermes Agent V0.13+（8 个 Profile 已创建）
- DeepSeek V4 API

## 状态

✅ 8 个 Agent Profile 已创建  
✅ MongoDB novel_qidian 数据库已初始化  
✅ 调度脚本已完成  
🔲 待首次实战测试
