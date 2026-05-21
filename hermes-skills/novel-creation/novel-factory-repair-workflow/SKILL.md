---
name: novel-factory-repair-workflow
description: 小说工厂 V2 全量问题诊断→数据修复→新ARC设计的一站式工作流。包含角色登场审计、摘要修补、时间线补全、消失角色处理、伏笔回调规划、新ARC启动方案生成。
---

# Novel Factory 修复与ARC启动工作流

## 触发条件

当用户说"修复出现的问题""系统性修复""按生产规范修复""修复消失的人"时加载本 skill。

## Step 1: 深度审计

### 1.1 连接 MongoDB
```python
from pymongo import MongoClient
# ⚠️ 必须加 ?authSource=admin，否则认证失败
client = MongoClient('mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin')
db = client['novel_factory']
```

### 1.2 角色出场矩阵扫描

扫描所有 chapter_memory 的 `content` 字段（正文）和 `summary` 字段，构建角色出场矩阵：

- 正文登场集数
- 摘要提及集数
- 标题提及集数
- 摘要漏报数（正文出场但摘要没写）
- 首次/末次出场章节

角色别名映射（以诡异游戏为例，按项目调整）：
```python
char_identities = {
    '林远': ['林远'],
    '顾晚': ['顾晚'],
    # ... 其他角色
}
```

### 1.3 消失角色分析

- 检查每个角色的末次主动出场（有对话/动作，非回忆/旁白提及）
- 统计后续间接提及数

### 1.4 时间线密度检查

- 每章最小事件数
- 零事件章节列表
- ARC 事件分布均匀性

## Step 2: 摘要批量修复

### 2.1 追加出场角色名

遍历每章，对正文出场但摘要未提及的角色，追加到摘要末尾：

```
原摘要内容

出场角色：林远、顾晚、方晴★
```

★ 标记首次出场角色。

用 `bulk_write` + `$set` 批量操作，不修改其他字段。

### 2.2 验证

抽样检查 ch1、ch3、ch5、ch11、ch70、ch100、ch135 确认格式正确。

## Step 3: 时间线补全

### 3.1 补充事件

对每章提取 1-2 个核心事件，补充到 timeline 集合。文档结构：
```json
{"project_id": "...", "chapter": 1, "event": "事件描述", "importance": 1-5, "arc_id": "ARC-001"}
```

### 3.2 去重

检查已存在事件的 `event` 字段，避免重名。

### 3.3 消失角色退场说明

基于正文最后一幕的内容，添加合理的退场/留守/转岗事件。**不编造正文没有的信息。**

## Step 4: 角色数据修复

### 4.1 修复关系字段

检查 characters 集合中 `relationships` 字段的完整性：
- 每条的 `with`（关系对象）不可为空
- 每条的 `type`（关系类型）和 `description`（描述）要有内容

### 4.2 添加 Introduction Plan

对正文从未登场的角色（设定存在但写作为0），添加 introduction_plan 字段：
```json
{
  "introduction_plan": {
    "recommended_arc": "ARC-005",
    "recommended_ch": "ch4-8",
    "context": "场景上下文",
    "first_line_trigger": "角色首次登场的第一句切入点"
  }
}
```

### 4.3 更新角色类型/别名

补全 `type`、`aliases` 等基础字段。

## Step 5: 伏笔回调计划

### 5.1 拉取所有 foreshadow

```python
foreshadows = list(db['foreshadow'].find({'project_id': pid}).sort('setup_chapter', 1))
```

### 5.2 计算紧急度

```
pending_chs = 当前最后一章 - setup_chapter
pending >= 80 → 🔴 紧急（下个ARC前半段必须回调）
pending >= 50 → 🟡 中等（下个ARC前半段安排）
pending >= 30 → 🟢 正常（下个ARC中后段）
pending >= 10 → 🟢 近期（下个ARC后半段或下下个ARC）
pending < 10  → 🟢 最新（下个ARC结尾）
```

### 5.3 生成回调映射

为每条伏笔生成 suggested_callback_arc 和 suggested_callback_ch，写回 foreshadow 集合。

### 5.4 保存计划文档

输出 markdown 文档，按紧急度排序，路径：`~/zj-matrix/novel-factory/callback-plan-<书名>.md`

## Step 6: 新ARC启动方案

### 6.1 阅读现有角色数据

读取 characters 集合的全部数据+正被引入的角色和旧角色，理解定位。

### 6.2 阅读当前结尾章节

读取最后一章的 content 最后 500 字，确认 ARC 过渡点。

### 6.3 设计 ARC-{N+1} 方案

内容包括：
- 第一幕：主要新角色引入（如陆沉）
- 旧角色回归节点（如赵铁、周文、老钱）
- 已有伏笔回调映射
- 第二/三幕设计
- 每章一句话剧情提炼

### 6.4 预置 Timeline 事件

为规划中的章节添加 ARC-{N+1} 的 timeline 文档。

### 6.5 更新 project 记录

将 character_introductions、character_returns、callback 映射写入 projects 集合。

## Step 7: 全链路内容一致性修复（Full-Chain Content Fix）

**触发条件**：正文中存在跨章节的金额/数字/名称/事件描述不一致（如标题写「返三亿」但正文写「三百万」）。

### 7.1 全量扫描（不要先动手改——先搞清楚波及范围）

同时扫描以下所有数据源，不遗漏：

```python
import pymongo, re, os

# 1. novel.chapters（最终成品库）
novel_db = pymongo.MongoClient('mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/novel?authSource=admin')['novel']
for ch in novel_db.chapters.find({'novelName': '小说全名'}).sort('chapterNumber', 1):
    n, t, c = ch['chapterNumber'], ch.get('title',''), ch.get('content','')
    for m in re.finditer(r'关键词', c):
        print(f'novel.ch#{n}: ...{m.group()}...')

# 2. novel.novels（元数据）
novel = novel_db.novels.find_one({'title': '小说全名'})
print(f'synopsis: {novel.get("synopsis","")}')
print(f'description: {novel.get("description","")}')

# 3. 本地文件
for root, dirs, files in os.walk('/root/.hermes/projects/'):
    for f in files:
        if f.endswith(('.md', '.txt')):
            with open(os.path.join(root, f)) as fh:
                for i, line in enumerate(fh, 1):
                    if '关键词' in line:
                        print(f'本地 {f}:{i}: {line.strip()[:120]}')

# 4. Web UI 直接登录验证（需手动）
```

### 7.2 语境分类

对每个命中点，判断所属类型：

| 类型 | 处理方式 | 示例 |
|------|---------|------|
| **同事件引用** | 必须统一改 | 第1章「系统奖励三百万」→「三亿」 |
| **独立新事件** | 保留不动 | 第4章「三百万的豪车」（车价独立） |
| **数字公式** | 必须改 | `200×150,000=30,000,000`→`200×1,500,000=300,000,000` |
| **元数据描述** | 必须同步改 | synopsis / description 中的旧值 |

### 7.3 多位置同步更新

所有「同事件引用」「数字公式」「元数据描述」一次全改完：

```python
# novel.chapters — 用 novelName 字段（中文字符串，不是 ObjectId!）
novel_db.chapters.update_one(
    {'novelName': '小说全名', 'chapterNumber': 1},
    {'$set': {'content': fixed_content, 'title': fixed_title}}
)
# novel.novels — 元数据
novel_db.novels.update_one(
    {'title': '小说全名'},
    {'$set': {'description': fixed_desc, 'synopsis': fixed_synopsis}}
)
```

### 7.4 验证

改完后重新全量扫描，确认：
- 旧关键词已清零（除非是「独立新事件」的合理保留）
- 新关键词出现在预期位置
- 第4/5章等保留的不动值不受影响

### 7.5 Web 端验收

NovelStudio Web UI（端口 5003，默认部署在局域网 `192.168.2.46`）：

**登录方式**：手机号填 `admin`，验证码填密码 `456321zj`。勾选协议后点击登录 — 后端有 admin 后门绕过短信验证。

**章节验证路径**：
- 章节列表：`/novel/<slug>/chapters/`（slug 为小说名的拼音，如 `shen-ye-xiao-guan-de-wen-nuan-shou-ze`）
- 单章阅读：`/novel/<slug>/chapter/<N>/`

**验证要点**：点进每个修复过的章节，检查标题、正文开头和结尾，确认修改生效。

**Pitfall**：浏览器 session 可能过期（页面自动跳回登录页）。重新走 admin 后门登录即可恢复，登录后会自动跳回目标页。

### Pitfalls

- ❌ **不要凭记忆判断**——只相信全文 grep。模型说「后面的章节都不涉及」但实际上 grep 出来 3 处。
- ❌ **不要一次性改所有命中**——先分类。把「独立新事件」也改了会导致新矛盾（第4章的「三百万的豪车」和第5章的「借我三百万」就是合理的保留）。
- ❌ **不要改完不验证**——改后 grep + MongoDB 查询双重确认旧关键词清零。
- ⚠️ **novelName 是字符串不是 ObjectId**：`novel.chapters` 集合用 `novelName`（中文小说名，如「花钱就返利，开局买水返三亿」）关联章节，不是 `novel_id` 字段。写更新脚本时注意！
- ✅ 存疑的命中点优先改——让读者出戏的错误（金额、数字、重要事件）宁可多改不要漏改。
- ✅ **保留的不动值要单独确认**——修复脚本不能使用全局替换（如 `.replace('三百万', '三亿')`），必须按分类逐个命中点检查后再改。

## 常用MongoDB路径

### 双库结构

| 用途 | host | 库名 | 认证 |
|------|------|------|------|
| 最终成品（正文章节） | 192.168.2.30:27017 | `novel` | mongo_8F6dTZ / mongo_dxx8nA (?authSource=admin) |
| 创作中间态（V2） | 192.168.2.30:27017 | `novel_factory` | 同上 |

### 集合列表

#### `novel` 库（Web UI 数据源）
- `novels` — 小说元数据（用 `title` 作为唯一标识）
- `chapters` — 最终成品正文（用 `novelName` 字符串 + `chapterNumber` 关联）

> **坑**：`chapters` 的关联键是 `novelName`（中文小说名字符串），不是 ObjectId 的 `novel_id`！查询时必须用 `{'novelName': '花钱就返利，开局买水返三亿', 'chapterNumber': 1}`。

#### `novel_factory` 库（V2 创作层）
- `projects` — 项目状态（project_id, current_arc, total_words）
- `world_bible` — 世界观（数组类型字段！）
- `characters` — 角色（relationships/growth_arc/goals 都是数组类型）
- `timeline` — 时间线事件
- `arcs` — ARC 元数据
- `foreshadow` — 伏笔数据库
- `chapter_memory` — 章节记忆
- `anti_repetition` — 防重复/分析数据

## 输出规范

所有生成的规划文档上传至 `1989zj/zj-matrix/novel-factory/` 路径，使用 GitHub Content API（read token from `~/.git-credentials`，branch="master"，路径URL编码）。
