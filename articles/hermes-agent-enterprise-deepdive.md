# Hermes Agent 命令详解与企业级使用场景

> 开源 AI Agent 框架的完整命令行体系与生产环境部署指南

Hermes Agent 是 Nous Research 开源的一款全功能 AI Agent 框架，它通过终端、消息平台和 IDE 与用户交互，并内置了一套完备的命令系统和可扩展的插件体系。

## 一、整体架构

Hermes Agent 的运行方式与其构建模式一致：agent 运行在当前流程中——终端会话、网关后台服务或子调度任务。主进程（AIAgent）运行一个推理-工具调用-观察的循环，直到完成用户的任务。

核心组件分层如下：

```
┌─ 交互层 ──────────────────────────────────┐
│  CLI (hermes)  │  Gateway (Telegram/微信等) │  IDE (ACP)  │  API Server  │
├─ 核心引擎 ─────────────────────────────────┤
│  对话循环 (run_conversation)               │
│  工具发现 & 分发 (model_tools.py)           │
│  上下文管理 (压缩/记忆)                      │
├─ 工具层 ───────────────────────────────────┤
│  Terminal  │  File  │  Web  │  Browser    │
│  Memory    │  Cron  │  MCP  │  Delegation  │
├─ 扩展层 ───────────────────────────────────┤
│  技能 (Skills)  │  插件 (Plugins)  │  配置  │
├─ 存储层 ───────────────────────────────────┤
│  SQLite 会话 │ 记忆文件 │ 配置 YAML │ Git  │
└────────────────────────────────────────────┘
```

每一个层之间通过严格分隔的接口进行交互。工具通过注册中心（registry）在启动时发现，技能按需加载，插件拦截关键生命周期事件。

## 二、命令体系全解

Hermes Agent 的命令体系分为三层：**二进制 CLI 命令**、**内部 Slash 命令**、**子命令体系**。三层之间各司其职，层层递进。

### 第一层：hermes CLI 顶层命令

`hermes` 是唯一的入口二进制文件，没有子命令时默认进入交互式聊天模式。

```
hermes [global flags] [command]
```

全局标志在运行任何命令之前解析：

| 标志 | 用途 | 典型场景 |
|---|---|---|
| `-p, --profile NAME` | 选择配置隔离环境 | 多用户/多项目场景 |
| `-s, --skills SKILL` | 预加载技能（可重复指定） | 固定工作流的自动化 |
| `-w, --worktree` | 自动创建隔离的 git worktree | 代码修改实验的并行跑 |
| `-r, --resume SESSION` | 按会话 ID 恢复会话 | 跨日对话延续 |
| `-c, --continue` | 恢复最近会话 | 终端中关闭重启 |
| `--yolo` | 跳过危险命令确认 | 沙箱环境/CI 流水线 |

### 第二层：配置与管理子命令

完整的子命令体系覆盖了整个生命周期，从安装到运维：

**初始化和诊断**：
```
hermes setup          安装向导（首次启动或重新配置）
hermes doctor         诊断配置、依赖完整性
hermes status        显示各组件运行状态
hermes dump          一键导出诊断报告（粘贴到 GitHub Issue）
```

**模型和 Provider 管理**：
```
hermes model          交互式选择模型和 Provider
hermes auth           管理同一 Provider 下的多 API Key 轮换池
hermes fallback       设置 Provider 故障切换链
```

**会话和产出管理**：
```
hermes sessions list/browse/rename/delete/prune
hermes backup         全量配置备份（zip，含 SQLite 快照备份）
hermes export/import  会话导出、导入
```

**网关和消息平台**：
```
hermes gateway run/start/stop/install/status  网关生命周期
hermes pairing list/approve/revoke           用户授权管理
```

**技能系统**：
```
hermes skills browse/search/install/list/update/publish
hermes curator run/status/pin/archive         技能自动维护守护进程
```

**其他**：
```
hermes cron           定时任务管理
hermes webhook        Webhook 订阅管理
hermes mcp            MCP 服务器管理
hermes kanban         多 Agent 协作白板
hermes insights       使用分析报告
hermes update         更新到最新版本
```

### 第三层：Slash 命令

在交互式会话中可以输入以 `/` 开头的命令：

**会话控制**：`/new` `/retry` `/undo` `/rollback` `/compress` `/background`

**配置查询**：`/model` `/config` `/provider` `/reasoning` `/voice`

**工具 & 技能**：`/tools` `/skills` `/cron` `/plugins`

**诊断**：`/usage` `/insights` `/profile`

这些 slash 命令在 CLI、Telegram、Discord、Slack 等平台的交互体验是一致的。

## 三、企业级部署模式

### 3.1 多用户隔离（Profiles）

`profiles` 是企业部署的核心基础设施。每个 profile 是**完全隔离的 Hermes 实例**，拥有独立的：

- 配置文件 (`config.yaml`)
- 环境变量 (`.env`)
- 会话历史 (SQLite DB)
- 技能目录
- 记忆文件 (MEMORY.md, USER.md)

**典型场景**：为团队中不同角色创建专用 Agent。

```bash
# 创建两个隔离的容器
hermes profile create dev-team
hermes profile create ops-bot

# 设置各自的网关端口（必须写入各 profile 的 .env，因为 API_SERVER_* 是环境变量）
echo "API_SERVER_ENABLED=true
API_SERVER_PORT=8643
API_SERVER_KEY=dev-secret" > ~/.hermes/profiles/dev-team/.env

echo "API_SERVER_ENABLED=true
API_SERVER_PORT=8644
API_SERVER_KEY=ops-secret" > ~/.hermes/profiles/ops-bot/.env

# 分别启动
hermes -p dev-team gateway start
hermes -p ops-bot gateway start
```

每个 profile 的 API server 自动以 profile 名作为模型 ID 注册到 Open WebUI 等前端，团队可以从同一个 Web 界面连接不同的 Agent。

### 3.2 Docker 容器化部署

Hermes 官方提供 Docker 镜像 `nousresearch/hermes-agent`，支持两种模式：

**模式 A：Agent 运行在容器内**（推荐生产隔离）
```bash
mkdir -p ~/.hermes
docker run -it --rm \
  -v ~/.hermes:/opt/data \
  nousresearch/hermes-agent setup
```

配置写入宿主机的 `~/.hermes/.env`，容器本身是无状态的。升级镜像不会丢失任何配置。

**模式 B：Docker 作为 Terminal Backend**（终端沙箱化）

Agent 自身运行在宿主机，但每个终端命令执行在独立容器中：
```yaml
# ~/.hermes/config.yaml
terminal:
  backend: docker
  docker_image: python:3.11-slim  # 持久化容器，共享整个进程生命周期
```

这个模式下，`pip install foo` 一次，后续所有命令（包括子 Agent）都能访问已安装的依赖。

### 3.3 多 Agent 并行（Git Worktrees）

在同一个仓库中并行运行多个 Agent，每个 Agent 有独立的分支和工作目录：

```bash
# 自动模式（推荐）
cd /repo
hermes -w -q "实现用户认证模块"   # 自动创建 .worktrees/hermes-<hash>/
hermes -w -q "实现支付接口"        # 第二个 Agent 自动创建另一个 worktree
```

`-w` 标志让 Hermes 自动完成 git worktree 创建、分支设置和隔离。两个 Agent 互不干扰，最后手动合并分支即可。

### 3.4 生产部署检查清单

**网关部署（面向团队）：**

1. 显式配置用户允许列表（`allowed_users`），绝不用 `GATEWAY_ALLOW_ALL_USERS=true`
2. 设置容器终端后端（`terminal.backend: docker`）隔离命令执行
3. 限制资源上限（CPU、内存、磁盘）
4. 配置 DM Pairing 授权机制而不是硬编码用户 ID
5. 设置 `MESSAGING_CWD`，不让 Agent 从敏感目录启动
6. 以非 root 用户运行网关
7. 监控 `~/.hermes/logs/` 日志审查未授权访问
8. 定期 `hermes update` 安全更新

**API Key 安全：**
```bash
chmod 600 ~/.hermes/.env
# .env 文件永远不提交到版本控制
```

**网络隔离：**
```yaml
terminal:
  backend: ssh              # Agent 在宿主机，命令执行在远程沙箱
```
```bash
# ~/.hermes/.env 中设置
TERMINAL_SSH_HOST=agent-worker.internal
TERMINAL_SSH_USER=hermes
TERMINAL_SSH_KEY=~/.ssh/hermes_agent_key
```

## 四、安全模型深入

### 4.1 安全扫描

Hermes 集成了 Tirith 安全策略引擎。在执行终端命令前，系统会扫描命令内容并对比预设的策略规则：

```yaml
security:
  tirith_enabled: true      # 启用扫描
  tirith_timeout: 5         # 扫描超时时间
  tirith_fail_open: false   # 扫描失败时阻止命令执行（生产推荐）
  redact_secrets: true      # 自动脱敏 API Key 输出
```

### 4.2 审批模式（Smart Approvals）

| 模式 | 行为 | 适用场景 |
|---|---|---|
| `manual`（默认） | 每条疑似危险命令都确认 | 个人开发 |
| `smart` | 辅助 LLM 评估风险，低风险自动放行 | 团队协作，减少审批疲劳 |
| `off` | 跳过所有检查 | CI/CD 流水线、沙箱环境 |

Smart 模式通过另一个轻量模型（如 Gemini Flash）在后台对命令做风险分类，低风险操作不需要用户介入。

### 4.3 网站黑名单

可以精确控制 Agent 能访问的域名范围：

```yaml
security:
  website_blocklist:
    enabled: true
    domains:
      - "*.internal.company.com"
      - "*.local"
      - "secrets.example.com"
```

规则支持精确匹配、通配符子域名和 TLD 模式。配置变更 30 秒内生效，无需重启。

### 4.4 检查点与回滚（Checkpoints）

在生产环境中，Agent 对文件的修改可以通过检查点机制回退。系统在每次写文件或破坏性命令执行前自动创建 git 快照：

```bash
hermes chat --checkpoints          # 启动会话时开启
# 或全局启用
```

```yaml
checkpoints:
  enabled: true
  max_snapshots: 20                # 每个项目保留的快照数
```

在会话中通过 `/rollback` 可以列出/恢复快照，或仅恢复单个文件。检查点存储在一个共享的裸 git 仓库下（`~/.hermes/checkpoints/store/`），通过 git 的对象寻址跨项目去重。

## 五、多租户与团队协作

### 5.1 Kanban Boards

Hermes 内置了一个完整的 Kanban 系统，用于跨 profile 的团队协作。每个 board 是一个独立的 SQLite DB，可以设置不同的 dispatcher 作用域。

**典型流程：**

```bash
# 创建一个项目 Board
hermes kanban boards create release-v2 \
  --name "Release v2" --icon 🚀

# 创建任务，指定执行人和租户标记
hermes kanban create "数据库迁移脚本" \
  --assignee dev-team \
  --tenant project-a \
  --workspace dir:~/projects/a/data/

# 分配任务链
hermes kanban link T-001 T-002    # T-001 完成后才执行 T-002

# 任务完成后自动通知原创建人所在的平台（Telegram/Discord）
```

Agent 工作线程通过专用的 `kanban_*` 工具集与 board 交互（`kanban_show`、`kanban_complete`、`kanban_block` 等），无需通过 CLI shell 调用。

### 5.2 多用户 Web 界面

通过 Open WebUI 整合多个 profile，团队成员可以在同一界面上选择不同的 Agent：

1. 为每个团队成员创建独立 profile（`hermes profile create alice`）
2. 每个 profile 启动独立的 API Server（绑定不同端口）
3. 在 Open WebUI 中添加多个连接，每个连接对应一个 profile
4. 用户从下拉菜单选择「alice」「bob」「ops-bot」等模型

每个连接背后的 Agent 运行在完全隔离的环境中，互不干扰。

## 六、运维与可观测性

### 6.1 使用分析

```bash
hermes insights --days 30                    # 过去 30 天的使用概况
hermes insights --days 7 --source telegram    # 按平台过滤
```

这个命令返回各模型的 token 消耗、成本估算和能力标签，支持按时间段和平台过滤。

### 6.2 备份恢复

```bash
# 完整备份（含所有配置、技能、会话、记忆）
hermes backup -o /backup/hermes-$(date +%Y%m%d).zip

# 快速状态快照（仅关键状态文件，秒级完成）
hermes backup --quick --label "pre-upgrade-v2.5"

# 恢复
hermes import /backup/hermes-20260510.zip
```

备份工具使用 SQLite 的 `backup()` API 进行一致性快照，即使 Agent 正在运行也能安全拷贝。备份中排除了 checkpoint 目录（按需重新生成）和 `hermes-agent` 代码本身。

### 6.3 定时任务与自动化

Cron 系统支持自然语言调度，且可绑定技能上下文：

```bash
hermes cron create --schedule "0 9 * * 1" \
  --prompt "生成上周的团队开发周报" \
  --skills "fetch-a-shares-news" \
  --deliver telegram
```

**每周一早上 9 点，系统自动**：
1. 加载 `docs-to-deepdive-article` 技能
2. 执行周报生成
3. 通过 Telegram 投递到团队群

Cron 作业支持 pause/resume/edit/run 全生命周期操作，技能加载失败时有独立错误处理逻辑。

### 6.4 Webhook 事件驱动

```bash
hermes webhook subscribe github-pr-review \
  --prompt "审查来自 {actor} 的 PR #{number}: {title}" \
  --events "pull_request" \
  --skills "github-code-review" \
  --deliver telegram
```

配置后，GitHub PR 事件自动触发 Agent 执行代码审查，结果投递到 Telegram。Webhook 支持 HMAC 签名验证、事件类型过滤和 `--deliver-only` 零 Token 模式（纯模板渲染，无需 LLM 推理）。

### 6.5 后台进程与并行执行

```bash
# 在会话中处理异步任务
/background 搜索最新的 LLM 基准测试数据并保存到 ~/research/benchmarks.md

# 该命令会在后台启动一个隔离的 Agent 实例，完成时通知你
# 你可以在前台继续其他工作
```

`/background` 使用 tmux 创建一个完整的独立 Agent 进程，双方互不阻塞。

## 七、成本控制与资费分析

### 7.1 模型路由

Hermes 支持模块化模型分配，不同任务可以使用不同的模型：

```yaml
# 主模型：高级推理
model:
  default: "anthropic/claude-opus-4.6"
  provider: "openrouter"

# 辅助任务用便宜模型
auxiliary:
  title_gen:    "google/gemini-3-flash-preview"  # 会话标题生成
  compression:  "gpt-4o-mini"                     # 上下文压缩
  vision:       "google/gemini-2.5-flash"         # 图像分析
  approval:     "gpt-4o-mini"                     # 危险命令审批
  web_extract:  "gpt-4o-mini"                     # 网页摘要
```

**哪个辅助任务在什么条件下应该覆盖：**

| 任务 | 推荐覆盖条件 | 成本节省 |
|---|---|---|
| 标题生成 | 几乎所有场景 | Opus → Flash 可减少 95% 成本 |
| 上下文压缩 | 主模型是长链推理模型时 | 压缩轮次减少 50-80% token |
| 图像分析 | 主模型不支持多模态时 | 避免换模型的额外开销 |
| 命令审批 | `approval_mode: smart` | 审批决策不需要强推理 |
| 网页摘要 | `web_extract` 使用频繁 | 摘要任务同样不需要推理 |

### 7.2 Credential Pools（API Key 轮换池）

单个 Provider 下的多个 API Key 可以组成池，实现自动轮换和故障转移：

```bash
hermes auth add openrouter --api-key sk-or-v1-xxx
hermes auth add openrouter --api-key sk-or-v1-yyy
hermes auth add openrouter --api-key sk-or-v1-zzz

# 查看池状态
hermes auth list openrouter
```

当池中某个 Key 触发 rate limit 或返回错误时，Hermes 自动切换到下一个 Key。所有 Key 都耗尽时再触发 fallback provider 链。

### 7.3 Fallback Provider（故障切换链）

```bash
hermes fallback add    # 选择 OpenRouter 的 Grok 3，添加到切换链
hermes fallback add    # 选择本地 Ollama 的 Qwen2.5，再添加
hermes fallback list   # 确认切换顺序
```

切换链的顺序是依次尝试的，只有当前 Provider 完全不可用时才触发。对关键业务部署，建议配置至少 2 个备用 Model。

### 7.4 子 Agent 委派的资源隔离

子 Agent 的模型可独立配置，父 Agent 用 Opus，子 Agent 用 Flash 即可：

```yaml
delegation:
  model: "google/gemini-3-flash-preview"   # 子 Agent 默认模型
  max_concurrent_children: 3               # 默认并行数，无硬性上限
  max_spawn_depth: 1                        # 树深度，1 = 扁平委派
```

成本缩放公式：`成本 × 轮次 × 并行度 × 深度`。深度为 3、并行 3 时，一次分支可能产生 27 个并行子 Agent，因此建议 `delegation.max_spawn_depth` 保持默认 1，非必要不上调。

## 八、与主流竞品的对比

### 技术维度

| 特性 | Hermes Agent | Claude Code | OpenAI Codex | 开源方案（如 OpenClaw） |
|---|---|---|---|---|
| Provider 无关 | 18+ Provider 自由切换 | 仅 Anthropic | 仅 OpenAI | 多数支持单 Provider |
| 消息平台网关 | 14+ 平台（含微信/飞书/企业微信） | 无 | 无 | 有限 |
| 跨会话记忆 | 文件存储器 + 8 个外部 Provider | 有限 | 有限 | 基础文件存储 |
| 技能系统 | 社区 Hub + 自动维护 Daemon | 手动 Project 文件 | 无 | 手动 Markdown |
| 子 Agent | 并行委派 + Kanban + 多深度 | 串行 | Codex CLI 内 | 有限 |
| 定时任务 | Cron + Webhook + 技能绑定 | 无 | 无 | 部分支持 |
| 多 Profile | 完全隔离（配置/会话/技能） | 无 | 无 | 有限的 Worktree |
| 网络隔离后端 | SSH/Docker/Singularity/Modal | 无 | 本地 | 本地 |
| 成本优化 | 辅助模型路由 + Credential Pool + Fallback 链 | 单一 Key | 单一 Key | 单一 Key |

### 选型决策矩阵

| 你的场景 | 推荐方案 | 理由 |
|---|---|---|
| 个人开发助手 | Claude Code 或 Hermes | 需要单强的选 Claude，需跨 Provider 的选 Hermes |
| 团队协作（消息平台） | Hermes | 14+ 平台网关无竞品可匹敌 |
| SaaS 产品内置 AI Agent | Hermes Open WebUI 整合 | API Server + 多 Profile |
| 企业内部自动化流水线 | Hermes Cron + Webhook | 定时/事件驱动完整 |
| 多模型 A/B 测试 | Hermes | 同一框架切换 Provider 无需代码改动 |
| 成本敏感的生产环境 | Hermes + 辅助模型路由 | Credential Pool + Fallback 链保证高可用 |

## 九、实战部署场景

### 场景 1：团队代码审查 Bot

**目标**：GitHub PR 提交后自动代码审查，结果推送到团队 Telegram 群。

```
实现步骤：
1. hermes profile create code-review （创建隔离 profile）
2. 设置 Terminal Backend 为 Docker （命令隔离执行）
3. 安装 github-code-review + webhook-subscriptions 技能
4. 配置 webhook 订阅 GitHub PR 事件
5. 设置 Telegram 投递目标
6. hermes gateway start
```

关键配置：`approvals.mode: smart` 减少人工确认；`delegation.model` 用便宜模型做语法检查，主模型做逻辑审查。

### 场景 2：7×24 市场监控 Bot

**目标**：监控多只 ETF 和基金净值，异常时推送飞书。

```
实现步骤：
1. 安装 etf-monitoring-system 技能
2. 创建 cronjob，每 30 分钟扫一次数据
3. 对比数据使用 change-detection 模式
4. 无变化时 [SILENT] 静默
5. 异常数据通过 Feishu 推送到工作群
```

关键配置：`cron` 的 `no_agent: true` 模式（纯脚本执行，零 token 消耗）；脚本内实现指数退避防爬。

### 场景 3：内容生产线（AI 短剧）

**目标**：创意→剧本→配音→视频→发布，全部自动化。

```
核心流程：
1. Kanban Board 管理任务状态
2. 多个 Profile 分别负责不同角色：
   - writer: LLM 生成剧本
   - audio: Edge-TTS / CosyVoice 配音
   - video: FFmpeg 合成
3. 任务链联动（剧本完成→自动触发配音→自动触发合成）
4. 完成后推送到内容发布平台
```

关键配置：子 Agent 委派中 `max_concurrent_children: 3` 支持并行流水线阶段；本地 CPU 模型（TTS-Nano、GGUF）控制成本。

### 场景 4：SaaS 多租户 AI 助手

**目标**：为不同客户提供隔离的 AI Agent 服务。

```
实现方案：
1. 每个客户对应一个 Hermes Profile
2. 每个 Profile 绑定不同的：
   - Provider 和 API Key 池（客户自己的配额）
   - 技能（客户定制的业务逻辑）
   - 记忆（客户数据隔离）
3. 通过 Open WebUI 统一的界面，按菜单切换客户
4. 使用 API Server 暴露为 OpenAI 兼容接口
```

关键配置：每个 Profile 的 `.env` 中设置不同的 `API_SERVER_PORT`；通过 Nginx 反向代理统一入口。

## 十、总结

Hermes Agent 在企业级部署上的核心优势在于三点：

1. **资源隔离** — Profiles 和 Worktrees 保证了多用户、多项目的完全隔离，Docker/SSH 后端将 Agent 的命令执行范围锁定在可控边界内。
2. **弹性成本** — Credential Pools 绕过单一 Key 的 Rate Limit，Fallback 链保证了单 Provider 故障不中断服务，辅助模型路由将辅助任务的 Token 消耗降低一个数量级。
3. **全链路自动化** — Cron 定时 + Webhook 事件驱动 + Kanban 任务编排，让 Agent 从被动响应变为自主工作流引擎。

从独立开发者到企业团队，Hermes 的命令体系提供了从开发调试到生产运维的完整覆盖。整个框架的设计以 Provider 无关为底线，团队可以在不修改任何代码的前提下更换底层模型，这是与其他 Agent 框架最根本的区别。

---

### NotebookLM 素材搜索关键词

**关键词 1**：「Hermes Agent production deployment multi-user profiles gateway」→ 获取官方文档中的部署实践和配置参考

**关键词 2**：「AI agent framework comparison 2026 Claude Code Codex OpenClaw」→ 获取竞品对比和选型分析视角

**关键词 3**：「open source AI agent enterprise security authentication credential pool」→ 获取企业级 AI Agent 安全最佳实践

**关键词 4**：「Hermes Agent Nous Research GitHub releases changelog」→ 获取最新版本特性和迭代方向

**关键词 5**：「MCP server enterprise integration agent tool calling」→ 获取 MCP 协议在企业集成中的应用案例
