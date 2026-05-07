# Hermes Agent 多 Agent 模式：技术架构与使用场景

> 本文档为 NotebookLM 素材，按时间轴叙述 + 技术拆解结构编排。
> 适合制作单人播客解说或深度技术分析内容。

---

## 一、概述：为什么需要多 Agent？

Hermes Agent 由 Nous Research 开发，是目前 GitHub 上最受欢迎的开源 AI Agent 框架之一（Top 100 全历史仓库）。它的核心设计哲学是：**一个 Agent 解决不了所有问题，但一群 Agent 可以**。

Hermes 提供三种多 Agent 协作模式，覆盖从「临时组队」到「持久协作」的全频谱：

1. **Subagent Delegation（子代理委派）** — 主 Agent 在单轮对话中临时 fork 子 Agent 并行干活，结果归入上下文
2. **Kanban Multi-Agent Board（看板多代理协作）** — 持久化的任务看板，多个命名 Agent 异步协作，跨会话、可重启、可人类介入
3. **Profiles（多配置文件）** — 同一台机器运行多个完全独立的 Hermes 实例，各有独立的配置、记忆、技能和网关

这三种模式的技术栈深度依次递进，可以混用。

---

## 二、技术架构总览

### 2.1 核心架构分层

```
┌─────────────────────────────────────────┐
│           Gateway 层（消息网关）          │
│    Telegram / Discord / Slack / WhatsApp │
│    WeChat / Signal / iMessage / LINE / QQ│
│    CLI / TUI / Webchat / API Server      │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│         Agent 主循环（LLM Driver）        │
│   思考 → 工具调用 → 观察 → 思考...       │
│   系统提示 + MEMORY.md + USER.md 注入    │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│         工具层（Tool Surface）            │
│   terminal / file / web / browser / cron │
│   delegate_task / kanban_* / MCP Client  │
│   73+ 内置技能 + 社区技能 + 自定义技能    │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│         持久化层（Persistence）           │
│   SQLite FTS5（会话全文检索）             │
│   MEMORY.md / USER.md（文件级记忆）       │
│   Honcho（多 Agent 关联记忆）             │
│   Hindsight Cloud / Mem0 / Qdrant        │
└─────────────────────────────────────────┘
```

### 2.2 多 Agent 的核心基础设施

**Profile 机制**是整个多 Agent 架构的基础。每个 Profile 是一个独立的 Hermes 主目录，包含：

- `config.yaml` — 独立配置（模型、提供商、终端后端等）
- `.env` — 独立 API 密钥
- `SOUL.md` — 独立人格/身份定义
- `memories/` — 独立持久记忆
- `sessions/` — 独立会话历史
- `skills/` — 独立技能库
- `cron/` — 独立定时任务
- `kanban/` — 共享看板数据库（跨 profile 共享）

创建 profile 后自动生成命令行别名，例如 `hermes profile create coder` 即刻拥有 `coder chat`、`coder setup`、`coder gateway start` 等命令。

**看板数据库**是跨 profile 共享的 SQLite 文件（`~/.hermes/kanban.db`），所有 profile 读写同一张表，实现异步协作。

---

## 三、模式一：Subagent Delegation（子代理委派）

### 3.1 技术架构

这是最轻量的多 Agent 模式。主 Agent 通过 `delegate_task` 工具调用， spawn 出子 Agent 进程：

```
主 Agent (深度 0)
    │
    ├── delegate_task("研究话题 A")  → 子 Agent 1 (深度 1)
    ├── delegate_task("研究话题 B")  → 子 Agent 2 (深度 1)  
    └── delegate_task("修复 Bug")    → 子 Agent 3 (深度 1)
         │
         └── (深度 2，需 orchestrator 模式)
              └── 子 Agent 3.1
```

**关键机制：**

- 每个子 Agent 获得**完全隔离的对话上下文**（fresh conversation）
- 子 Agent 有自己的**独立终端会话**（separate terminal session）
- 父 Agent 必须通过 `goal` + `context` 参数传递所有必要信息
- 子 Agent 完成后，**仅最终摘要**进入父 Agent 的上下文（token 高效）
- 使用 `ThreadPoolExecutor` 实现并行执行

### 3.2 并行批次细节

```yaml
delegation:
  max_concurrent_children: 3      # 每批次并行数（默认3，无硬上限）
  max_spawn_depth: 1              # 嵌套深度（1=平面，2=允许orchestrator，3=三层）
  orchestrator_enabled: true      # 主开关
  model: "google/gemini-flash-2.0"  # 可选：子Agent用便宜模型
  provider: "openrouter"           # 可选：路由到不同提供商
  child_timeout_seconds: 600       # 子Agent静默超时（默认10分钟）
```

- 并行数可通过 `DELEGATION_MAX_CONCURRENT_CHILDREN` 环境变量覆盖
- 批次超过上限时返回工具错误（不会静默截断）
- CLI 模式下实时显示树状进度视图
- 结果按任务索引排序（与完成顺序无关）
- 中断父 Agent 会级联中断所有子 Agent

### 3.3 嵌套编排（Orchestrator 模式）

`max_spawn_depth` 控制委派树的深度（1~3，默认1）：

- **depth=1**（默认）：平面委派，子 Agent 不能再委派，`role="orchestrator"` 被静默降级为 leaf
- **depth=2**：orchestrator 子 Agent 可 spawn 叶子孙 Agent
- **depth=3**：三层树，根→orchestrator→leaf，最大可达 3×3×3 = 27 个并发叶子

**成本警告**：每个层级成倍放大 token 消耗，需有意识地调整。

### 3.4 子 Agent 工具限制

子 Agent 被禁止使用的工具（无论指定什么 toolsets）：

- `delegate_task` — 叶子子 Agent 默认禁用（orchestrator 保留）
- `clarify` — 不能向用户提问
- `memory` — 不能写入共享持久记忆
- `send_message` — 不能发送 Telegram 等跨平台消息

### 3.5 生命周期与持久性

> ⚠️ **关键约束**：`delegate_task` 是同步操作，运行在父 Agent 当前回合内。
> - 父 Agent 被中断（新消息、/stop、/new）→ 所有子 Agent 被取消
> - 子 Agent 的进行中工作**被丢弃**
> - 不是持久化后台作业队列

需要持久化、后台运行的工作应使用 `cronjob` 或 Kanban。

---

## 四、模式二：Kanban 多 Agent 看板

### 4.1 技术架构

Kanban 是 Hermes 最强大的多 Agent 协作模式。它是一张持久化的 SQLite 任务看板，**所有 Profile 共享**：

```
                    ┌─────────────────┐
                    │  ~/.hermes/     │
                    │  kanban.db      │
                    │  (SQLite)       │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
   │ Profile:    │   │ Profile:    │   │ Profile:    │
   │ orchestrator│   │ worker-1    │   │ worker-2    │
   │ (调度者)     │   │ (执行者)     │   │ (执行者)     │
   └─────────────┘   └─────────────┘   └─────────────┘
```

### 4.2 与 delegate_task 的关键区别

| 维度 | delegate_task | Kanban |
|------|--------------|--------|
| 模式 | RPC 调用（fork → join） | 持久化消息队列 + 状态机 |
| 父进程行为 | 阻塞等待子进程返回 | 创建任务后即 fire-and-forget |
| 子进程身份 | 匿名子 Agent | 命名 Profile + 持久记忆 |
| 可恢复性 | 无 — 失败即失败 | Block → unblock → re-run |
| 人工介入 | 不支持 | 可评论 / 可手动修改状态 |
| 每个任务的 Agent 数 | 一个子 Agent | N 个 Agent 接力（重试/审核/跟进） |
| 审计追踪 | 上下文压缩后丢失 | SQLite 持久化，永不过期 |
| 协作模式 | 层级（调用者→被调者） | 对等 — 任何 Profile 可读/写任何任务 |

**一句话区别**：`delegate_task` 是函数调用，Kanban 是工作队列。

### 4.3 核心概念

**Board（看板）**：一个独立的 SQLite 任务队列 + 工作目录 + 调度循环。单机可建多个 board（按项目/仓库/领域分），单项目用户只用 `default`。

**Task（任务）**：
- 字段：标题、正文、assignee（profile 名）、状态（triage | todo | ready | running | blocked | done | archived）
- 可选的 tenant 命名空间、幂等键（用于自动化重试的去重）

**Link（链接）**：`task_links` 表记录父子依赖关系。调度器在所有父任务 done 后自动把子任务从 todo→ready。

**Comment（评论）**：Agent 间协议。Agent 和人类可追加评论；worker 被（重新）spawn 时读取完整评论线程作为上下文。

**Workspace（工作区）**：worker 的操作目录。三种类型：
- `scratch`（默认）— 每个 worker 独立的临时目录
- `project` — 指向现有 git 仓库工作树
- `branch` — 自动创建独立的 git 工作树 + 分支

**Run（运行记录）**：每个任务可产生多次 run（重试、审核、接力）。每次 run 记录：
- `summary` — 人类可读的交接说明
- `metadata` — 自由格式 JSON（变更文件列表、测试结果等）
- `result` — 简短日志行

### 4.4 任务状态机

```
triage → todo → ready → running → blocked → ready ...
                         ↓
                       done → archived
```

- `triage`：待分类，调度器不触碰
- `todo`：已分类但依赖未满足
- `ready`：依赖满足，可被 worker 领取
- `running`：worker 正在执行
- `blocked`：等待人类或其他 Agent 决策
- `done`：完成
- `archived`：归档（保留记录）

### 4.5 调度器（Dispatcher）机制

调度器是一个监控线程，在每个 profile 的 gateway 中运行：

1. 轮询 `kanban.db` 中 `status=ready` 且 `assignee=当前profile` 的任务
2. 为每个任务 spawn 一个完整的 `hermes chat -p <profile>` 进程
3. 向 worker 进程注入上下文（任务详情 + 评论线程 + 历史 run 记录）
4. worker 执行任务，通过 `kanban_*` 工具更新状态
5. 调度器监测 run 的超时和健康状态（heartbeat）
6. worker 进程退出后，调度器检查最终状态
7. 如果 worker 意外崩溃（进程退出但未完成），任务自动标记为 `ready` 可被其他 worker 捡起

调度器确保：
- 每个 `ready` 任务最多被一个 profile 领取（行级锁）
- 崩溃或超时的 worker → 任务自动回退到 `ready`
- 调度器本身 crash 后，运行中的任务不受影响（通过 heartbeat 机制监测）

### 4.6 双入口设计

看板有两个前端入口，同源（同一 SQLite）：

**Agent 入口**（通过工具调用）：
- `kanban_show` — 查看任务详情
- `kanban_complete` — 完成任务（附 summary + metadata）
- `kanban_block` — 标记阻塞（附原因）
- `kanban_heartbeat` — 健康心跳
- `kanban_comment` — 追加评论
- `kanban_create` — 创建任务
- `kanban_link` — 建立依赖关系

**人类/脚本入口**（CLI/看板命令）：
- `hermes kanban list` — 列表查看
- `hermes kanban create` — 创建任务
- `hermes kanban complete` — 完成任务
- `/kanban` — 网关中的斜杠命令
- Web Dashboard — 图形化界面

### 4.7 八大协作模式

看板支持八种经典协作模式：

1. **Single-player（单人）** — 一个 profile 领任务-完成，简单跟踪
2. **Assignment（指派）** — 指定 profile 领指定任务
3. **Fleet（舰队）** — 一个 specialist 管理 N 个 subject（50 个社媒账号、12 个监控服务）
4. **Research Triage（研究分类）** — 并行研究者 + 分析师 + 写手，人工 HITL
5. **Scheduled Ops（定时运维）** — 每天生成简报，长期积累
6. **Digital Twins（数字分身）** — 持久命名助理（inbox-triage、ops-review）积累长期记忆
7. **Engineering Pipeline（工程流水线）** — 拆解→并行实现→review→iterate→PR
8. **Role Pipeline（角色流水线）** — 多个 profile 接力（设计→开发→审核→测试→部署）

---

## 五、模式三：Profiles + Git Worktree（多实例并行）

### 5.1 技术架构

这是最重的多 Agent 模式：在单机上运行多个完全独立的 Hermes 进程：

```
┌──── 主机 ─────────────────────────────────┐
│                                            │
│  ┌── Profile: coder ───────────────┐      │
│  │  config.yaml: claude-opus       │      │
│  │  terminal.cwd: /project/feature-a│      │
│  │  gateway: Telegram Bot A        │      │
│  │  sessions/ memories/ skills/    │      │
│  └─────────────────────────────────┘      │
│                                            │
│  ┌── Profile: research ────────────┐      │
│  │  config.yaml: gemini-flash      │      │
│  │  terminal.cwd: /project/feature-b│      │
│  │  gateway: Discord Bot           │      │
│  │  sessions/ memories/ skills/    │      │
│  └─────────────────────────────────┘      │
│                                            │
│  ┌── Profile: personal ────────────┐      │
│  │  config.yaml: minimax-m2.7      │      │
│  │  gateway: WhatsApp + Telegram   │      │
│  │  SOUL.md: 私人助理性格           │      │
│  └─────────────────────────────────┘      │
│                                            │
└────────────────────────────────────────────┘
```

### 5.2 隔离级别

每个 Profile 完全独立：
- **配置隔离**：独立模型、提供商、API 密钥
- **记忆隔离**：独立 MEMORY.md、USER.md、会话历史
- **技能隔离**：独立技能库（可共享的看板数据库除外）
- **网关隔离**：可绑定不同消息平台
- **工作目录隔离**：可设置不同的 `terminal.cwd`

注意：Profile 不做**文件系统沙箱**（sandbox）。默认 local 后端下，Agent 仍然有相同用户权限。如需安全沙箱，使用 Docker/Singularity/Modal 终端后端。

### 5.3 Git Worktree 集成

Profile 与 git worktree 深度集成，特别适合并行开发：

```bash
hermes -w  # 自动创建隔离的 git worktree + 独立分支
```

自动执行的流程：
1. 在仓库下创建 `.worktrees/hermes-<hash>/` 临时工作树
2. checkout 独立分支 `hermes/hermes-<hash>`
3. 在该 worktree 内运行 Hermes CLI 会话

多个终端运行 `hermes -w` 各自获得独立的 worktree 和分支，互不干扰。

### 5.4 应用场景

- **同一仓库并行开发多个功能**：各有独立分支和 checkpoints
- **同一个 Agent 的不同人格版本**：coding assistant vs 私人助理 vs 交易机器人
- **生产/测试隔离**：production profile 连接正式 API keys，testing profile 连接测试环境
- **多个网关绑定不同平台**：Telegram 绑定 coder，Discord 绑定 research

---

## 六、三种模式的对比与选型指南

### 6.1 对比全景

| 维度 | Subagent Delegation | Kanban Board | Profiles + Worktree |
|------|--------------------|-------------|--------------------|
| 协作模式 | 父子（层级） | 对等（P2P） | 完全独立 |
| 生命期 | 回合内 | 跨会话、持久 | 长期运行 |
| 进程数 | N 个子进程 | N 个独立进程 | N 个独立进程 |
| 状态持久化 | 无 | SQLite + 文件系统 | 独立文件系统 |
| 人工介入 | 不支持 | 评论/状态变更 | 无（独立网关） |
| 失败恢复 | 失败即丢弃 | 自动重试/回收 | 各自独立 |
| 审计追踪 | 仅最终摘要 | 完整 Run History | 独立会话日志 |
| 内存/记忆 | 无共享 | 独立但通过看板衔接 | 完全独立 |
| 资源消耗 | 低（回合内） | 中（持久化进程） | 高（多进程常驻） |
| 混用可能 | Kanban worker 内可调用 | 可同时使用 delegation | 可部署多个 gateways |

### 6.2 选型决策树

```
需要立即得到结果？
  ├── 是 → 子任务需要推理/判断？
  │     ├── 是 → delegate_task（单个或并行）
  │     └── 否 → execute_code（机械数据处理）
  └── 否 → 工作跨 Agent 边界？
        ├── 是 → Kanban Board
        ├── 需要不同 API 配置/记忆？
        │     └── 是 → Profiles
        └── 需要完全独立运行？
              └── 是 → Profiles + 独立 Gateways
```

### 6.3 实际用户用例（来自社区）

- **12 个 Hermes 实例每天并行运行**：用于构建 Hermes Agent 本身（@Teknium）
- **Plan → Code → QA → Ship 流水线**：主 Agent 拆计划，coder Agent 实现，QA Agent 测试，修复→发布（@gkisokay）
- **4 层 Polymarket 交易监控**：同时监控订单簿、链上地址、新闻时差、仓位变化（@adiix_official）
- **9 个 Hermes 模拟两家 AI 公司竞争**：各 Agent 写代码、创建技能、积累记忆、git commit，完全自主（GLADIATOR 项目）
- **家族 WhatsApp 群**：一个 $200 ChatGPT 额度供全家用，每人绑定独立 profile（@EXM7777）
- **看板调度 + delegate_task 执行**：Kanban 分派任务，worker 内部用 delegation 并行子研究

---

## 七、MCP 集成：多 Agent 的扩展边界

Hermes 内置原生 MCP Client，支持两种集成方式：

1. **客户端模式**：Hermes 作为 MCP Client 连接外部 MCP Server（文件系统、数据库、API 等）
2. **Server 模式**（`hermes mcp serve`）：Hermes 自身作为 MCP Server 暴露 15+ 消息平台、SQLite 持久化、73 技能的工具面，其他 MCP Client 可直接调用

这意味着 Hermes 的多 Agent 能力可以通过 MCP 协议与**其他 Agent 框架**（Claude Code、Cursor、VS Code 等）互联，形成跨框架的 Agent 联邦。

---

## 八、底层技术亮点

### 8.1 可观测性

- **TUI 的 `/agents` 面板**：实时树状展示所有子 Agent 的调用链、成本、token、文件变更
- **零调用超时诊断**：子 Agent 零 API 调用超时时，自动写入结构化诊断日志到 `~/.hermes/logs/subagent-timeout-<session>-<timestamp>.log`
- **Run History 持久化**：看板中每个 run 的事件被记录到 SQLite，Web Dashboard 可回溯查看

### 8.2 看板的异常处理设计

- **崩溃回收**：Worker 进程意外退出 → 任务自动标记为 `ready`，可被其他 worker 捡起
- **空闲超时**：超过 `child_timeout_seconds`（默认10分钟）无任何 API/工具调用 → 自动 kill
- **Bulk close 保护**：批量完成任务时禁止传入相同的 `--summary`（防止机械粘贴）
- **合成 run**：人类从 Dashboard 标记一次从未被领取的任务为 done 时，自动创建零时长 run 记录

### 8.3 安全与合规

- **approval gate**：支持 DM 中的人工审核门控
- **credential stripping**：从输出中剥离凭证信息
- **OSV malware 检查**：MCP 包的安全扫描
- **审计日志**：所有看板事件可导出，满足 EU AI Act 合规要求

---

## 九、部署方案参考

最低配置：
- **CPU-only VPS**（$5/月 Hetzner）：Minimax M2.7 模型，子 Agent 用 Gemini Flash
- **桌面/工作站**：本地 Ollama + GGUF 模型，完全离线
- **Android 手机**：Termux 运行，利用 SMS/传感器（$10/5天 token 成本）
- **Docker**：`nousresearch/hermes-agent` 官方镜像，持久化卷映射

---

## 十、素材搜索关键词（NotebookLM）

- Hermes Agent multi-agent architecture
- Subagent delegation parallel batch processing
- Kanban multi-agent board SQLite state machine
- Hermes profiles vs worktree isolation
- Agent-to-agent collaboration patterns
- Nous Research Hermes Agent technical deep dive
- Durable task queue for AI agents
- Multi-agent orchestration with LLM
- Agent task lifecycle management
- MCP protocol multi-agent federation

---

> 本文档基于 Hermes Agent v1.0+ 官方文档整理。数据来源：hermes-agent.nousresearch.com/docs
