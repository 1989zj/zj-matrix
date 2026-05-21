# 万印道主 · `novel-factory new` 实操记录

> 最后更新：2026-05-19
> 项目 slug: `xian-xia-shen-hua`
> 本文件记录首次大型修仙项目（300万字设定）的完整运行过程，供后续续写时参考。

## 命令与执行

```bash
novel-factory new '大型修仙小说，市面通用修仙体系（炼气→筑基→金丹→元婴→化神→大乘），300万字长篇设定，要有独创性的大世界观和新鲜剧情，避免套路化'
```

**执行模式**: background=true（terminal），无前台超时限制
**总耗时**: ~36分钟（进程持续运行，后台监控）
**完成**: 5章 + 全部元数据（Research/Outline/Character/World/Foreshadow）

## 核心设定

| 要素 | 内容 |
|------|------|
| 世界观 | 修仙界是试验场（道印体系替代传统功法） |
| 冲突核心 | 道争而非力斗（不是谁拳头大谁赢） |
| 核心系统 | 万印之印——能解析+复制万道的上古禁忌道印 |
| 主角 | 林尘，天才变废材→废印中觉醒万印 |
| 女主 | 暂无明确CP线（双女主计划） |
| 反派体系 | 6层递进（孙鸣家族→血杀门→五大圣宗→道印猎手→...） |
| ARC数 | 4个 |
| 章节前20章规划 | Outline 已完整写入 task-cards/outline-card.md（20,665字） |

## 里程碑时间线

| 时间(相对) | 事件 | 产出 |
|-----------|------|------|
| T+0 | 提交 CLI | background=true 启动 |
| ~30s | ARC规划完成 | 4个ARC写入MongoDB + task-cards |
| ~60s | Research完成 | 14,130字市场分析/竞品对比/爽点分布 |
| ~3min | Outline完成 | 20,665字逐章大纲/600章全线分布 |
| ~5min | Character完成 | 18,883字角色数据（18角色+道印体系） |
| ~6min | World State + Foreshadow | MongoDB 写入完成 |
| ~8min | ch001 Draft → Validator(PASS) | ch001_废材道印.md（4,292字） |
| ~10min | ch001 Editor（精简17处） | 2134→1966字，番茄风格加强 |
| ~12min | ch002 Draft | ch002_万印初现.md（5,378字） |
| ~14min | ch002 Editor | 编辑完成，字数达标 |
| ~16min | ch003 Draft | ch003_不能说的秘密.md |
| ~18min | ch003 Editor | 编辑完成 |
| ~20min | **Clarify 超时** | orchestrator 等待120s → 自动继续 |
| ~24min | ch004 Draft + Editor | ch004_藏拙之道.md |
| ~28min | ch005 Draft | ch005_小试牛刀.md |
| ~32min | ch005 Editor | ch005_小试牛刀.md 最终版 |
| ~36min | exit 0 | 全部完成，进程正常退出 |

## 各章剧情速览

| 章 | 标题 | 核心剧情 | 字数 | 质量评级 |
|----|------|---------|------|---------|
| 1 | 废材道印 | 测试大典被判废印，孙鸣背叛，后山道印觉醒「万」字 | 4,292 | ⭐⭐⭐⭐ |
| 2 | 万印初现 | 兽栏受辱→赤鳞蟒暴走→万印解析兽印反弹→云鹤真人惊恐警告 | 5,378 | ⭐⭐⭐⭐ |
| 3 | 不能说的秘密 | 师尊揭示万印传说（五大圣宗诛杀万印之主），手札遗物「研究它的人活不过三年」 | ~1,800 | ⭐⭐⭐⭐ 强钩子 |
| 4 | 藏拙之道 | 师尊布七层灵力罩伪装废印，三天杀人倒计时，林尘闭关修炼 | ~1,800 | ⭐⭐⭐⭐ |
| 5 | 小试牛刀 | 孙鸣上门挑衅→演练场对决→万印复制火鸦诀→平手收场+杀手定位 | ~1,800 | ⭐⭐⭐⭐⭐ 爽感+钩子 |

## 写作风格

番茄小说风格贯穿始终：
- ✅ 短段落（平均2-4句一段，不要超过5行）
- ✅ 强画面感（视觉描写先行）
- ✅ 节奏紧凑（每章至少1个冲突/推进）
- ✅ 章末钩子（每章结尾留悬念）
- ✅ 对话推进剧情，少旁白说明
- ✅ 情绪起伏合理（紧张→释放→新悬念）

## Pipeline 行为明细

### Draft Agent 输出示例（ch003）
```
师尊交给林尘一本残破手札：「这是当年那位留下的唯一遗物。但记住——研究它的人，没有一个活过三年。」
```
角度：对话+揭秘为主，制造「巨大秘密+致命危险」的压迫感。
林尘情绪线：震惊→恐惧→坚定（我要活下去）。

### Editor 1st Pass 示例（ch003 审校）
输出到 `/root/ch003_editor.txt`，完成了逐行审校、精简废话、保持番茄风格、不改剧情。

### 任务卡结构（ch003-task-card.md）
```
# 第3章 不能说的秘密
## 核心冲突
## 场景大纲（3个场景）
## 章末钩子
## 写作要求
```

## 文件产出映射

| 路径 | 内容 | 是否最终版 |
|------|------|-----------|
| `/root/novel-factory/xian-xia-shen-hua/ch001_废材道印.md` | 最终版 | ✅ |
| `/root/novel-factory/xian-xia-shen-hua/ch002_万印初现.md` | 最终版 | ✅ |
| `/root/novel-factory/xian-xia-shen-hua/ch003_不能说的秘密.md` | 最终版 | ✅ |
| `/root/novel-factory/xian-xia-shen-hua/ch004_藏拙之道.md` | 最终版 | ✅ |
| `/root/novel-factory/xian-xia-shen-hua/ch005_小试牛刀.md` | 最终版 | ✅ |
| `/root/ch001_废材道印.txt` | Draft 原始输出 | ❌ 临时 |
| `/root/ch001_editor.txt` | Editor 输出 | ❌ 临时 |
| `/root/ch003_不能说的秘密.txt` | Draft 原始输出 | ❌ 临时 |
| `/root/ch004_藏拙之道.txt` | Draft 原始输出 | ❌ 临时 |
| `/root/ch005_小试牛刀.txt` | Draft 原始输出 | ❌ 临时 |

## MongoDB 状态（运行结束时）

```python
novel_factory.projects: 1 doc (status="连载中", total_words=11014)
novel_factory.characters: 4 docs（含旧项目遗留数据）
novel_factory.event_log: 7 events（新项目）+ 153 旧事件
novel_factory.foreshadow: 7 docs（新项目）+ 30 旧
	
novel.chapters: 0（未同步！需要运行 sync-novel-to-mongodb.py）
```

## 续写要点

1. **下一章方向**（按 Outline）：第6章「杀手来袭」—— 孙鸣家族派出血杀门杀手找到林尘，第一次生死实战
2. **MongoDB 同步**：运行 `python3 sync-novel-to-mongodb.py --proj-dir xian-xia-shen-hua` 同步到 novel 库
3. **风格一致**：继续番茄小说风格，短段落+强画面+快节奏
4. **伏笔管理**：手札的「三年死亡倒计时」已启动，需在后续30章内释放信息
5. **战力节奏**：林尘前期只能偷偷用万印，不能暴露
