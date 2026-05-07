# Hermes Agent 多Agent模式 — 视频制作包

---

## 一、视频元数据

**标题（3选1）：**
1. 一个Agent不够？开源框架Hermes教你用一群AI打工
2. 深度拆解Hermes Agent：三种多Agent架构，谁才是终极方案？
3. 我用一群AI Agent并行干活，结果效率翻了3倍

**时长建议：** 8-12分钟（中视频，B站知识区/YouTube硬核科普）

---

## 二、关键词

**中文关键词（12个）：**
#开源Agent #多Agent协作 #HermesAgent #AI自动化 #子代理委派 #Kanban看板 #AI工作流编排 #智能体架构 #NousResearch #Agent联邦 #LLM工具调用 #AI生产力

**英文关键词（8个）：**
multi-agent system, agent orchestration, subagent delegation, kanban board AI, hermes agent tutorial, AI agent collaboration, agent workflow automation, LLM tool calling

**搜索标签：**
Hermes Agent, 多Agent架构, AI Agent教程, 开源智能体, 大模型应用

---

## 三、视频画面 & 口播完整脚本

以下为「单人解说 + 画面演示」风格，可直接用于：
- AI 视频生成（Runway/Pika/Kling 逐段生图/生视频）
- 人工剪辑配音（配合 Keynote/PPT 演示）
- 录屏 + Voiceover 解说

---

### 阶段 1：认知打破（0:00 - 0:40）

| 画面 | 口播 |
|------|------|
| 【画面】黑色背景，中央浮现一个灰色 Agent 图标，然后分裂成 3 个彩色 Agent，各自奔向不同方向。粒子动画。 | 你有没有遇到过这种情况：让 AI 帮你写代码，它写到一半忘了上下文；让它同时调研三个话题，它只能一个一个来。 |
| 【画面】三个 Agent 并行工作，每个头顶显示进度条，整体速度是单个的 3 倍。 | 但如果我说，现在有一个开源框架，能让你的 AI Agent 在单次对话里，同时 fork 出好几个子 Agent 并行干活，而且各自有独立上下文，互不干扰——最后只把结果总结给你。 |
| 【画面】Hermes Agent 的 GitHub 页面（stars 计数 + 仓库首页展示），快速切到「GitHub 全历史 Top 100」徽章。 | 这就是 Hermes Agent——由 Nous Research 开发，目前 GitHub 全仓库历史排名前 100 的开源项目。今天我从技术架构层面，拆解它的三种多 Agent 模式。 |

---

### 阶段 2：Subagent Delegation — 最轻量的并行利器（0:40 - 3:00）

| 画面 | 口播 |
|------|------|
| 【画面】一个「父 Agent」坐在驾驶室，面前三个屏幕，每个屏幕里是一个「子 Agent」在独立工作。隐喻：一个项目经理派出三个下属。 | 第一种模式：Subagent Delegation，子代理委派。这是最常用的模式，可以理解为一个项目经理分配任务给下属——每个下属有完全独立的办公室（上下文）和工具包（toolsets），互不通气，只向经理汇报结果。 |
| 【画面】代码高亮显示 delegate_task 调用：<br>`delegate_task(goal="研究话题A", toolsets=["web"])`<br>下方动画展示 3 个任务并行执行，ThreadPoolExecutor 示意图。 | 技术上，父 Agent 通过一个叫 `delegate_task` 的工具来启动子 Agent。你可以传单个任务，也可以传一个任务数组——数组模式下，Hermes 会用 ThreadPoolExecutor 线程池并行执行，默认最多 3 个并发子 Agent。 |
| 【画面】树状图展示嵌套深度：depth=1 平面 vs depth=2 带 orchestrator vs depth=3 三层。数字叠加：3×3×3=27 | 默认是平面委派——子 Agent 不能再生子。但你可以开启「orchestrator 模式」，允许子 Agent 再派自己的下属。深度最高 3 层，如果每层 3 个并发，最坏情况下你的钱包要同时养 27 个 Agent 同时干活。成本是乘数效应。 |
| 【画面】沙漏图标 + 禁止符号。子 Agent 列表：❌clarify ❌memory ❌send_message | 一个关键约束：子 Agent 是同步的。父 Agent 必须等所有子 Agent 完成才能继续。如果用户中途打断父 Agent，所有子 Agent 立即取消，进行中的工作直接丢弃。所以不适合持久化任务。 |

---

### 阶段 3：降维比喻 — 项目经理 vs 车间看板（3:00 - 4:00）

| 画面 | 口播 |
|------|------|
| 【画面】左半边：一个经理对着三个员工发号施令（delegate_task）。右半边：一个车间大屏幕看板，多个工人自由领取任务、更新状态。 | 到这里你可能会问：那需要持久化的任务怎么办？答案是看板模式。把 delegate_task 想象成一个经理给下属临时派活——任务做完就完，不留记录。而看板模式，是一个车间里的电子看板，所有工人共享，谁有空谁领取，干完了更新状态，其他人能看到。 |
| 【画面】对比表格浮现在屏幕中央：左侧 delegate_task — 右侧 Kanban。关键字段高亮：匿名 vs 命名、不持久 vs SQLite、无审计 vs 完整历史。 | 它们的核心区别在这里：一个是一次性的 RPC 调用，子 Agent 甚至没有名字；另一个是持久化的消息队列，每个任务有身份、状态机、有完整的审计追踪，而且支持人类中途介入。 |

---

### 阶段 4：Kanban 看板 — 最强大的多 Agent 协作（4:00 - 7:30）

| 画面 | 口播 |
|------|------|
| 【画面】SQLite 数据库图标 + 任务状态机流程图：triage → todo → ready → running → blocked → done → archived。状态转换用箭头动画连接。 | 看板背后是一张 SQLite 数据库表。每个任务有 7 个状态：triage（待分类）→ todo（待办）→ ready（就绪可领取）→ running（执行中）→ blocked（阻塞）→ done（完成）→ archived（归档）。 |
| 【画面】两个 Profile 图标（不同颜色）在 SQLite 数据库两侧，同时读写同一张表。数据库上方标注 `~/.hermes/kanban.db`。 | 最关键的是——这张表是所有 Profile 共享的。Hermes 的 Profile 可以理解为完全独立的 Agent 实例，各有各的配置、API key、记忆、会话历史。但它们都读写同一张 kanban.db。这就实现了「多个独立 Agent 异步协作」。 |
| 【画面】一个调度器（dispatcher）图标在监控看板，发现 ready 任务 → spawn 一个 worker 进程 → worker 工作 → worker 更新状态。如果 worker 崩溃（红色 X），任务自动回到 ready。 | 每个 Profile 的网关里跑着一个调度器线程，它会轮询看板，发现状态为 ready 且指派给自己的任务，就 spawn 一个完整的 Hermes 进程去执行。如果 worker 意外崩溃——没错，任务自动回到 ready，等着别的 worker 捡起来。 |
| 【画面】一条任务的时间线：worker-A 取了 → 阻塞 → 人类评论 → worker-B 捡起继续 → 完成 → 下个 worker 收到交接记录。 | 任务可以接力。一个 worker 干到一半卡住了，可以标记 blocked 并说明原因。人类或者其他 Agent 评论后，另一个 worker 可以捡起来继续。每次交接都附带 summary 和 metadata——改了哪些文件、测试结果、遗留问题，全在 `task_runs` 表里。 |
| 【画面】一个「双入口」图示：左侧 Agent 拿着工具（hammer图标），右侧人类拿着键盘和 Dashboard。两者都指向同一个 SQLite 数据库。 | 看板有两个入口：Agent 通过 `kanban_*` 工具集操作，人类通过 CLI 命令 `hermes kanban ...` 或者 Web Dashboard 操作。两边看到的、写的是同一张表，不存在数据不一致。 |

---

### 阶段 5：八种协作模式速览（7:30 - 8:30）

| 画面 | 口播 |
|------|------|
| 【画面】8 个小卡片排列成 2×4 网格，每个卡片一个图标 + 名称。依次高亮。 | Hermes 看板设计上支持八大协作模式。单人模式——自己跟自己。指派模式——指定给谁就是谁。舰队模式——一个 Agent 管理 50 个社媒账号。研究分类——多个研究者并行，一个分析师汇总，一个人审核。 |
| 【画面】后四个卡片高亮：定时运维（日历图标）、数字分身（两个相同头像）、工程流水线（齿轮链条）、角色流水线（设计→开发→测试→部署箭头）。 | 定时运维——每天 9 点自动跑日报。数字分身——你有 3 个永久在线的助理：inbox-triage、ops-review、research。工程流水线——拆任务→并行实现→自动 review→迭代→提 PR。角色流水线——设计 Agent 写完传给开发，开发测完传给 QA，QA 通过了自动部署。 |

---

### 阶段 6：Profiles — 完全隔离方案（8:30 - 9:30）

| 画面 | 口播 |
|------|------|
| 【画面】一台服务器图标，里面有三个独立的小房子（Profile），每个房子有自己的门牌号、钥匙（API key）、书柜（记忆）、工具箱（技能）、电话线（gateway）。 | 第三种模式：Profiles。如果说 delegate_task 是临时工，Kanban 是车间协作，那 Profiles 就是三栋独立的别墅。每栋有自己的钥匙（API key）、书架（记忆）、工具箱（技能）、独立的电话线（gateway 绑定不同平台）。 |
| 【画面】终端演示：`hermes profile create coder` → 立刻出现 `coder chat` 命令。然后 `coder setup` → `coder gateway start` | 创建 Profile 的命令只有一行。`hermes profile create coder`，然后你就多了个 `coder chat` 命令。这个 coder 有自己的 config.yaml、自己的 .env、自己的 SOUL.md 人格定义、自己的会话历史和日志。 |
| 【画面】终端演示 `hermes -w` 自动创建 git worktree + 独立分支。两个终端窗口分别跑 `hermes -w`，各有不同分支高亮。 | 更绝的是与 git worktree 的集成。`hermes -w` 一条命令，自动创建隔离的工作树和独立分支。开两个终端跑 `hermes -w`，两个 Agent 在同个仓库里互不干扰地并行开发。 |

---

### 阶段 7：真实案例 + 思想实验（9:30 - 11:30）

| 画面 | 口播 |
|------|------|
| 【画面】12 个 Agent 图标排列成矩阵，每个图标上面快速闪过不同功能：bug fix、代码审查、测试、文档。一个开发者坐在屏幕前看着 12 个画面。 | 这些不是纸上谈兵。Hermes Agent 的创始人 @Teknium 每天跑 12 个 Hermes 实例并行开发 Hermes 本身。社区有人用 9 个 Hermes 模拟了两家 AI 公司互相竞争 GitHub stars——每个 Agent 自主写代码、创建技能、积累记忆、提交 commit，全程无人干预。 |
| 【画面】网络状示意图：Hermes Gateway（中心）→ Telegram、Discord、Slack、WhatsApp、WeChat、Signal、CLI 等图标环绕。MCP 协议向外连接到 Claude Code、Cursor 等其他框架。 | 而且 Hermes 内置了 MCP 协议的客户端和服务端能力。它既可以当 MCP Client 连接外部工具，也可以用 `hermes mcp serve` 把自己的 73 个技能和 15 个消息平台暴露给其他 Agent 框架。这意味着 Claude Code、Cursor、VS Code 等都能调用 Hermes 的能力——真正意义上的 Agent 联邦。 |
| 【画面】深色背景，中央浮现一个问题：「当你的 Agent 学会雇佣其他 Agent，你的角色是什么？」画面聚焦、渐暗。 | 最后留一个问题：当一个 AI Agent 能够动态地 fork 子 Agent、独立决策、持久化协作，甚至通过 MCP 协议与其他框架的 Agent 互联——你的角色会从「操作者」变成什么？是管理者？还是被管理者？ |

---

## 四、AI 视频生成提示词（分镜用）

以下为可逐段输入 AI 视频生成工具（Runway Gen-3 / Pika 2.0 / Kling / Sora）的画面提示词：

**镜01：** A minimalist AI agent icon splits into three colorful agents flying in different directions, particle effects, dark background, cinematic lighting, 4K

**镜02：** Three AI agents working in parallel on separate screens, progress bars above each head, 3x speed visualization, clean tech aesthetic

**镜03：** GitHub repository page of Hermes Agent with star count, smooth zoom into code, modern UI, dark mode

**镜04：** A manager sitting at a cockpit with three subordinate agents on separate monitors, each in their own office room, cinematic metaphor shot

**镜05：** Code snippet of delegate_task() highlighted, animated data flow showing ThreadPoolExecutor spawning children, technical visualization

**镜06：** Tree diagram showing depth-1 flat vs depth-2 orchestrator vs depth-3 nested delegation, nodes lighting up sequentially, 3D isometric

**镜07：** Split screen: left side a manager giving orders (delegate), right side a factory Kanban board with workers picking tasks, animated transition

**镜08：** SQLite database spinning, then expanding into a full state machine flowchart (triage→todo→ready→running→blocked→done→archived), data particles

**镜09：** Two colored AI profiles (coder and research) reading and writing to the same database table simultaneously, data sync visualization

**镜10：** A dispatcher icon monitoring a Kanban board, spawning worker processes, worker crash shown in red flash, task auto-returns to ready

**镜11：** Timeline visualization: worker A picks task → blocks → human comments → worker B continues → completes → handoff metadata transfer

**镜12：** 8-card grid layout showing 8 collaboration patterns with icons and names, cards light up one by one

**镜13：** Server rack with three separate house icons inside, each with distinct keys (API), bookshelves (memory), toolboxes (skills), phone lines (gateway)

**镜14：** Terminal window showing `hermes -w` command, then split into two terminal windows with different git branches highlighted

**镜15：** 12 AI agent icons arranged in a 4x3 grid, each showing different work activity, a developer watching all of them

**镜16：** Network diagram: Hermes Gateway at center, 15+ messaging platforms around it, MCP protocol connecting to Claude Code and Cursor icons

**镜17：** Dark screen, single question fades in: "When your AI agent hires other AI agents, what becomes your role?" contemplative, slow fade to black

---

## 五、制作备注

**配音建议：** 男声/女声，沉稳偏快语速（1.25x），技术科普节奏。可用 Edge-TTS 的 `zh-CN-YunxiNeural` 或本地 CosyVoice。

**配乐：** 开头阶段用低沉电子音制造悬念，技术解说阶段用中速 Lo-fi 保持节奏，结尾思想实验阶段用环境音渐淡。

**封面图提示词：** Split screen showing 3 AI agent silhouettes in parallel, connected by flowing data streams, dark blue and purple color scheme, tech minimalism, 3D isometric, high contrast, cinematic lighting --ar 16:9

---

