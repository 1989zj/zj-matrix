---
name: novel-cli-web-integration
description: 小说系统 CLI 统一入口 + Web CLI 控制台的完整实现与维护。包含 20 个可执行脚本的命令清单、~/.local/bin/novel 入口脚本、Flask API 端点及前端控制台页面。
---

# Novel CLI + Web 集成维护指南

## 架构总览

```
~/.local/bin/novel          # 统一 CLI 入口（bash 调度脚本）
~/.local/bin/novel-factory   # 小说工厂 V3（独立入口）

~/.hermes/skills/content-creation/
  ├── hermes-novel-factory/         # 小说工厂 V3
  │   └── scripts/init_collections.py
  ├── novel-reconstruction/         # Phase 0 重建
  │   └── scripts/novel-reconstruct.py
  ├── novel-review-pipeline/        # 质检评审
  │   └── scripts/novel-judge.py
  ├── novel-refinement-branch/      # 精修分支
  │   └── scripts/
  │       ├── refine-chapter.py
  │       └── state-diff.py
  ├── dialogue-voice-refinement-runbook/  # 对话声音精修
  │   └── scripts/dialogue-voice-refiner.py
  ├── novel-factory-repair-workflow/  # 修复工作流
  │   └── scripts/audit-and-fix.py
  ├── novel-full-pipeline-sop/      # 全流程 SOP
  ├── novel-audit-fix/              # 审计修复
  └── web-novel-chapter/           # 网文单章
      └── scripts/count-chinese-chars.py

/root/zj-matrix/
  ├── app.py                        # Flask 入口
  ├── app/blueprints/novel.py       # 蓝图（含 CLI API）
  ├── templates/
  │   ├── novel_cli.html            # CLI 控制台页面
  │   └── components/sidebar.html   # 侧边栏（含 CLI 入口）
  └── NOVEL_COMMANDS.md             # 命令清单文档
```

## 命令清单（20 个可执行脚本）

| 子命令 | 实际脚本 | 路径 |
|---------|---------|------|
| `factory *` | novel-factory | `~/.local/bin/novel-factory` |
| `reconstruct *` | novel-reconstruct.py | `skills/novel-reconstruction/scripts/` |
| `judge *` | novel-judge.py | `skills/novel-review-pipeline/scripts/` |
| `refine *` | refine-chapter.py | `skills/novel-refinement-branch/scripts/` |
| `voice *` | dialogue-voice-refiner.py | `skills/dialogue-voice-refinement-runbook/scripts/` |
| `lore *` | lore-corrector.py | `skills/novel-refinement-branch/scripts/` |
| `state *` | state-diff.py | `skills/novel-refinement-branch/scripts/` |
| `audit *` | audit-and-fix.py | `skills/novel-factory-repair-workflow/scripts/` |
| `validate *` | novel-validate.py | `skills/novel-refinement-branch/scripts/` |
| `count` | count-chinese-chars.py | `skills/web-novel-chapter/scripts/` |
| `init-db` | init_collections.py | `skills/hermes-novel-factory/scripts/` |

## CLI 入口维护（~/.local/bin/novel）

### 添加新子命令
在 `novel` 脚本的 `case` 块新增分支：
```bash
mycommand)
    SCRIPT="skills/<skill>/scripts/<script>.py"
    exec python3 "$SKILL_DIR/$SCRIPT" "${@:2}"
    ;;
```
同时在 `print_help()` 和 Flask `api_cli_list()` 中添加。

## Flask API 端点

位置：`/root/zj-matrix/app/blueprints/novel.py`

### GET /api/novel/cli/
返回全部命令列表 JSON。格式：
```python
commands = {
    "模块名": {
        "description": "描述",
        "subcommands": {"子命令": "用法示例"}
    }
}
```

### POST /api/novel/cli/
两种调用模式：
1. `{"command": "judge", "args": ["review", "诡异游戏"]}`
2. `{"full_command": "novel judge review '诡异游戏'"}`
3. 可选 `timeout`（默认 180s，factory new 自动 600s）

### NOVEL_ACTIONS — 小说级快捷操作（新增）
定义在 `novel.py` 中的字典 `NOVEL_ACTIONS`，将 UI 按钮映射到 `novel` CLI 命令。

```python
NOVEL_ACTIONS = {
    "audit": {
        "label": "全量审核修复",
        "icon": "fact_check",
        "desc": "...",
        "command": "novel audit {name}",   # {name} 由 slug 解析替换
        "timeout": 300,                     # 子进程超时秒数
        "warning": "会修改章节内容"          # None = 安全操作
    },
    # ... 其他操作类似
}
```

**关键模式**：命令模板用 `{name}` 占位，运行时通过 `slug_to_name(slug)` 从 MongoDB 查询小说名替换。

### POST /api/novel/<slug>/action/
根据 `action` 从 `NOVEL_ACTIONS` 查找命令模板，拼装完整命令后 `subprocess.run()` 执行。

- 请求体：`{"action": "audit", "params": {"dry_run": true, "chapters": "1-5"}}`
- 响应：`{"success": bool, "returncode": int, "stdout": "...", "stderr": "..."}`
- 异常处理：超时（`subprocess.TimeoutExpired`）、命令不存在（`FileNotFoundError`）均返回友好错误
- 危险操作（audit/reconstruct-run/voice-refine）需要前端 `confirm()` 确认

### GET /api/novel/<slug>/actions/
返回该小说可用的操作列表（含配置描述），用于前端动态渲染按钮。

## Web 控制台页面（templates/novel_cli.html）

- Tailwind CSS + Material Symbols
- 左侧命令面板：从 `/api/novel/cli/` 动态加载，可点击填充
- 右侧终端：暗色风格，stdout/stderr 分色
- 命令历史：localStorage，↑/↓ 浏览，最多 100 条
- 支持引号包裹参数

## 小说级快捷操作 — 前端按钮组

两处模板都实现了基于 `NOVEL_ACTIONS` 的操作按钮：

### novel.html（具体小说详情页右侧栏）
- 独立的「AI 创作工具」卡片（`bg-surface-container-lowest rounded-2xl`）
- 每个按钮独占一行，带 Material Symbols 图标和悬停 `play_arrow` 提示
- 按钮分组：审核类 → 分隔线 → 评审类 → 分隔线 → 优化类 → 分隔线 → 检测类

### chapters.html（管理中心 AI 侧边栏）
- 紧凑按钮组（`flex flex-wrap gap-1.5`），放在 AI 助手面板最顶部
- 按钮尺寸更小（`text-xs px-2.5 py-1.5`），标签只显示两个字

### 执行结果弹窗（通用组件）
两页共用同一个弹窗结构（`#action-modal`）：

```
┌─ 执行中...                        [运行中] [X] ─┐
│  $ novel audit 诡异游戏                            │
│                                                    │
│  ┌────────────────────────────────────────┐       │
│  │  stdout/stderr 输出（等宽字体白底）       │       │
│  │                                          │       │
│  └────────────────────────────────────────┘       │
│  [命令执行成功/失败]           [复制输出] [关闭]   │
└────────────────────────────────────────────────────┘
```

**关键 JS 函数**：
- `runNovelAction(action)` — 发送 POST 请求，更新弹窗状态
- `closeModal(e)` — 点击遮罩层或关闭按钮隐藏弹窗
- `copyModalOutput()` — 复制输出内容

**危险操作确认流**：`['audit', 'reconstruct-run', 'voice-refine']` 触发时先 `confirm()`

## 常见问题

- **Flask 启动失败（No module named 'dotenv'）**：使用 Hermes venv 的 Python：
  ```bash
  /opt/hermes-agent/venv/bin/python3 app.py
  ```
- **命令超时**：factory new 默认 600s，其他 180s，POST 中可传 `timeout` 覆盖
- **脚本路径不存在**：用 `find ~/.hermes/skills/content-creation -name '*.py'` 扫描实际路径
- **侧边栏双上下文陷阱**：NovelStudio 的侧边栏有两个分支——
  - `{% if slug and meta %}` 小说专属侧边栏（作品管理）
  - `{% else %}` 全局管理侧边栏（系统管理）
  **任何新全局导航条目（例如 CLI 控制台）必须在两个分支中都加**，否则用户在小说页面内看不见入口。小说侧边栏底部紧接 `</nav>` 后加独立 `div` 插入导航项；全局侧边栏加在 `nav` 内的 `a` 列表中。修改后重启 Flask 服务才生效。
