---
name: novel-audit-fix
description: 诡异游戏全章节全流程审核+自动修复——角色出场审计、时间线补全、ARC元数据、hooks、伏笔紧急度、7维一致性、Anti-fatigue、Editor质量检查
trigger: 全量模式 全量 审核 诡异游戏 audit-and-fix 全章节审核
---

# Novel Audit & Fix — 全量模式

## 概述

一条命令跑完对「诡异游戏」所有已有章节（ch1-135+）的全流程审核和自动修复。8 步流程，4 步自动修 + 4 步只报告不改。

## 脚本位置

```
~/.hermes/skills/content-creation/novel-audit-fix/scripts/audit-and-fix.py
```

## 用法

```bash
# 全量模式：审核 + 自动修复（缺角色补摘要、缺事件补时间线、缺钩子自动生成）
python3 ~/.hermes/skills/content-creation/novel-audit-fix/scripts/audit-and-fix.py '诡异游戏'

# 只审核不修改
python3 ~/.hermes/skills/content-creation/novel-audit-fix/scripts/audit-and-fix.py '诡异游戏' --report-only

# 跳過某些步骤（例如跳过step3 ARC元数据检查）
python3 ... --skip-steps 3
python3 ... --skip-steps 1,2,3  # 跳过多个
```

## 8步流程

| 步 | 名称 | 动作 | 说明 |
|----|------|------|------|
| 1 | 角色出场审计 | **自动修** | 扫描正文→角色→摘要，补`出场角色：xxx` |
| 2 | 时间线密度检查 | **自动修** | 每章≤1条事件时，自动从摘要提取补到≥2条 |
| 3 | ARC元数据完整性 | **自动修** | 缺 core_conflict/title/起止章节时填"待填充" |
| 4 | Chapter hooks覆盖率 | **自动修** | 从摘要最后一句自动生成钩子 |
| 5 | 伏笔紧急度计算 | **自动修** | 根据等待章数写回 urgency + suggested_callback_arc |
| 6 | 7维一致性 | 只报告 | 金额/称呼/字数/对话比例/时间线矛盾 |
| 7 | Anti-fatigue扫描 | 只报告 | 对白重复率/战斗密度/情绪比 |
| 8 | Editor质量检查 | 只报告 | 废话词/空行/开头突兀/结尾悬念 |

## 输出

- 控制台实时输出每一步的过程和结果
- 自动保存 JSON 审核报告到 `/root/zj-matrix/novel-factory/audit-report-*.json`
- 建议下一步: `novel-factory continue '诡异游戏'` 继续创作

## ⚠️ 前置条件

在运行本 skill 之前, **必须先跑 Phase 0: Novel Reconstruction** (`content-creation/novel-reconstruction`)。
重建层会做全量元数据恢复（timeline 迁移、伏笔分类、ARC 元数据、Canonical Bible 编译）。
重建后再跑本 skill 做深度审计和修补, 效果最优。

## 前置检测（跑审核前建议先做）

### 章节截断检查

某些章节可能在初始生成时末尾被截断（比如 ch2 缺了最后一句）。建议跑审核前先扫描一遍：

```
python3 -c "
exec(open('~/.hermes/skills/content-creation/novel-audit-fix/references/chapter-truncation-detection.md').read())
"  # 参见 references/chapter-truncation-detection.md
```

扫描出截断章节后，人工补完再跑审核，避免误判。

## 注意

- 只修改 MongoDB 元数据（summary/hook/timeline/foreshadow/arcs），不碰正文
- 7维/疲劳/editor 检查纯报告，不自动修改正文
- 步1 使用角色别名表（林远=主角, 顾晚=顾晚姐等）提高匹配精度
- 步5 按等待章数分级：>=80🔴紧急 / >=50🟡中等 / >=30🟢正常 / 其他🟢近期
- 首次运行建议先用 `--report-only` 预览，确认无意外再跑全量模式
