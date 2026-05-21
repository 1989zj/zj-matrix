# Novel System 统一 CLI 参考

## 概述

`novel` 是架设在所有小说子技能之上的统一 CLI 入口（`~/.local/bin/novel`），覆盖 novel-factory、reconstruction、judge、refine、voice、lore、state、audit 等全部子系统的 11 个子命令。同时配套 Flask API 端点和 Web 控制台页面，支持从浏览器远程调用。

---

## 一、CLI 用法

```bash
novel <子命令> [参数...]
```

### 子命令一览

| 子命令 | 模块来源 | 对应脚本 | 功能 |
|--------|---------|---------|------|
| `factory` | hermes-novel-factory | `~/.local/bin/novel-factory` | 小说工厂 V3 |
| `reconstruct` | novel-reconstruction | `novel-reconstruct.py` | Phase 0 重建 |
| `judge` | novel-review-pipeline | `novel-judge.py` | 质检评审 |
| `refine` | novel-refinement-branch | `refine-chapter.py` | 精修分析 |
| `voice` | dialogue-voice-refinement-runbook | `dialogue-voice-refiner.py` | 对话声音精修 |
| `lore` | novel-factory-repair-workflow | `lore-corrector.py` | 设定同步检测 |
| `state` | novel-factory-repair-workflow | `state-diff.py` | 状态差异 |
| `audit` | novel-factory-repair-workflow | `audit-and-fix.py` | 全量审核修复 |
| `validate` | novel-factory (V3) | `validate-chapter.py` | 章节校验 |
| `count` | web-novel-chapter | `count-chinese-chars.py` | 统计中文字数 |
| `init-db` | novel-factory | `init_collections.py` | 初始化 MongoDB 集合 |

### 用法示例

```bash
novel help                    # 显示子命令列表
novel factory new '男频系统流'  # 启动新项目
novel factory continue '诡异游戏'  # 续写
novel judge review '诡异游戏' --chapters 1-10  # 质检指定章节
novel reconstruct diagnose '诡异游戏'  # Phase 0 诊断
novel refine analyze '诡异游戏'  # 精修分析
novel voice refine '诡异游戏' --chapters 1-5  # 声音精修
novel audit '诡异游戏' --report-only  # 全量审核
novel count chapter-001.md    # 统计字数
```

### 程序可调用性

`novel` CLI 设计为 **程序可调用**（subprocess 友好）：
- stdout 输出正常结果
- stderr 输出错误信息
- exit code 0=成功 非0=失败
- 无交互式提示，纯参数驱动

```python
import subprocess
result = subprocess.run(
    ['novel', 'judge', 'review', '诡异游戏'],
    capture_output=True, text=True, timeout=180
)
print(result.stdout)
```

---

## 二、Flask API 端点

### 2.1 获取命令列表

```
GET /api/novel/cli/
Authorization: session cookie (admin required)
```

返回所有可用命令的 JSON 结构，供前端动态渲染。

### 2.2 执行命令

```
POST /api/novel/cli/
Authorization: session cookie (admin required)
Content-Type: application/json
```

**两种传参模式**：

模式 A — 拆分参数：
```json
{"command": "judge", "args": ["review", "诡异游戏", "--chapters", "1-10"]}
```

模式 B — 完整命令字符串：
```json
{"full_command": "novel judge review 诡异游戏 --chapters 1-10"}
```

**可选参数**：
- `timeout` (int, 默认180) — 超时秒数。`factory new` 自动设为600s

**返回格式**：
```json
{
  "success": true,
  "returncode": 0,
  "stdout": "...",
  "stderr": "",
  "timed_out": false
}
```

### 2.3 Web 控制台页面

```
GET /novel/cli/
Authorization: session cookie (admin required)
```

暗色终端风格页面，包含：
- 左侧命令面板（自动加载所有子命令，点击快速填充）
- 右侧终端输出区（stdout/stderr 分色显示）
- 历史命令（↑/↓ 浏览，localStorage 持久化 100 条）
- Ctrl+L 清屏
- Tab 点击补全

---

## 三、实现细节

### 3.1 CLI 脚本结构

```bash
# ~/.local/bin/novel 核心调度逻辑
case "$1" in
  help)     show_help ;;
  factory)  shift; exec novel-factory "$@" ;;
  reconstruct) shift; exec python3 "$SKILL_DIR/novel-reconstruction/novel-reconstruct.py" "$@" ;;
  judge)    shift; exec python3 "$SKILL_DIR/novel-review-pipeline/novel-judge.py" "$@" ;;
  refine)   shift; exec python3 "$SKILL_DIR/novel-refinement-branch/refine-chapter.py" "$@" ;;
  voice)    shift; exec python3 "$SKILL_DIR/dialogue-voice-refinement-runbook/dialogue-voice-refiner.py" "$@" ;;
  lore)     shift; exec python3 "$SKILL_DIR/novel-factory-repair-workflow/lore-corrector.py" "$@" ;;
  state)    shift; exec python3 "$SKILL_DIR/novel-factory-repair-workflow/state-diff.py" "$@" ;;
  audit)    shift; exec python3 "$SKILL_DIR/novel-factory-repair-workflow/audit-and-fix.py" "$@" ;;
  validate) shift; exec python3 "$FACTORY_DIR/scripts/validate-chapter.py" "$@" ;;
  count)    shift; exec python3 "$SKILL_DIR/web-novel-chapter/scripts/count-chinese-chars.py" "$@" ;;
  init-db)  exec python3 "$FACTORY_DIR/init_collections.py" ;;
  *)        echo "未知子命令: $1"; show_help; exit 1 ;;
esac
```

### 3.2 Flask 路由位置

```python
# /root/zj-matrix/app/blueprints/novel.py 中新增的 3 个路由：

@novel_bp.route('/api/novel/cli/', methods=['GET'])
def api_cli_list(): ...  # 返回命令列表 JSON

@novel_bp.route('/api/novel/cli/', methods=['POST'])
@admin_required
def api_cli_execute(): ...  # 执行命令并返回输出

@novel_bp.route('/novel/cli/')
@admin_required
def cli_console(): ...  # 渲染控制台页面
```

### 3.3 侧边栏集成

在 `/root/zj-matrix/templates/components/sidebar.html` 的全局管理区（`{% else %}` 分支）新增：
```html
<a href="{{ url_for('novel.cli_console') }}">
  <span class="material-symbols-outlined">terminal</span>
  <span class="font-label-md text-label-md">CLI 控制台</span>
</a>
```

### 3.4 模板位置

```
/root/zj-matrix/templates/novel_cli.html
```

---

## 四、命令清单文档

完整命令清单（含 20 个脚本的详细 argparse 说明）保存在：
```
/root/zj-matrix/NOVEL_COMMANDS.md
```
