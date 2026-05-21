---
name: dialogue-voice-refinement-runbook
description: 对话声音精修 SOP — 批量修改小说对白使角色声线差异化。脚本 + 实测踩坑 + 重试策略，适合诡异游戏/任意中文网文。
tags:
  - novel
  - refinement
  - dialogue
  - voice-profile
---

# 对话声音精修 Runbook

对任意小说章节批量执行「对话声音重塑」，使每个角色的对白具有辨识度。

## 前置条件

- MongoDB novel 库有完整章节数据
- Hermes config 配置了 DeepSeek 或其他 API
- `novel-refinement-branch` skill 已安装且脚本在 `scripts/` 目录

## 一键命令

```bash
# 精修 + 同步 + 合并
python3 dialogue-voice-refiner.py '小说全名' --chapters 10-20
python3 sync-after-refinement.py '小说全名' --chapters 10-20 --merge --llm-hooks
```

## 角色声音定义

默认在脚本内的 `DEFAULT_PROFILE`，以诡异游戏为例核心规则：

| 角色 | 声音特征 |
|------|---------|
| 林远 | 直接短促果断，从不拖泥带水 |
| 顾晚 | 话少、准确、结论先行 |
| 周文 | 学术严谨，提问驱动 |
| 方晴 | 提问型对话，爱追问 |
| 刘闯 | 短句、口语化、接地气 |
| 赵铁 | 短准汇报风 |
| 老钱 | 沉稳啰嗦，爱总结 |

## 踩坑 & 对策

### 1. MongoDB 密码为 `***` 占位符

所有精修脚本的 `MONGO_URI` 中的密码都是 `***`，首次运行必须先 patch：

```bash
python3 -c "
import pymongo
# 验证连接：用真实密码替换 ***
"
```

### 2. DeepSeek API 间歇性返回空

约 30-60% 的章节调用会返回空响应（错误：`Expecting value: line 1 column 1`），**不是内容问题，是 API 波动**。

**对策**：
- 先跑全批量（`--chapters 31-40`），再看哪些章节失败
- **不要立即重试** — 连续无间隔重试几乎 100% 失败
- 失败章节用 `retry-refine.py` 重试（独立脚本在 `dialogue-voice-refinement-runbook/scripts/`，更轻量）
- **重试前 sleep 至少 8 秒**，关键发现：
  - ⚡ 间隔 0 秒 → 全部失败
  - ⚡ 间隔 8 秒 → 部分通过（约 50%）
  - ⚡ 间隔 20 秒 → 全部通过
- **推荐分批重试策略**：先 `sleep 10 && retry`，检查结果；未过的再 `sleep 20 && retry`；若单章连续 3 次失败，等 30 秒后单独重试那 1 章
- **实测上限**：单个章节可能需 **3 次** 重试才通过（如 ch47: 第1次空、第2次空、第3次 4 处修改成功），不要把"2次"当硬上限
- **不建議一次重试太多章节**：`--chapters 45,46,47,48` 4 章一起重试时，部分章可能因 API 拥塞再次失败；先重试 2 章效果更好

**识别已失败的章节**：主脚本输出中带 `[ERROR] LLM call failed` 的行就是失败章节。

### 3. 脚本 apply 阶段可能漏改

对话-voice-refiner.py 的 apply 逻辑在批量模式下可能跳过部分补丁。
- 表现：脚本显示 `Applied N patches` 但实际检查发现部分对话未修改
- 对策：精修后用以下方法验证关键改动是否生效

```python
ch = db['chapters'].find_one({'novelName':'xxx','chapterNumber':10})
# 检查期望的替换是否存在于 content 中
'记住' in ch['content']
```

### 4. 必须用完整小说名

MongoDB 中的 `novelName` 是完整标题（如 `诡异游戏：我的规则别人看不见`），不是简称。
脚本按精确匹配 `{'novelName': args.novel_name}` 查找章节，传简称会提示「缺失章节」。

### 5. 超时处理

11 章精修（dry-run + apply）约需 3-5 分钟。
建议分两批（10-15, 16-20），每批 timeout=300s。
background + notify_on_complete 模式更适合。

## 验证清单

精修后需要验证：

- [ ] 对白修改在 `novel.chapters.content` 中生效
- [ ] chapter_memory 的 summary/hook 已更新
- [ ] status=merged，refinement_log 有记录
- [ ] wordCount 反映实际字数
- [ ] 不会改叙述旁白（只改「」内内容）

## 回滚

如果精修效果不理想，从 Git 恢复或从备份 chapter_memory 的 `original_word_count` 回退。
