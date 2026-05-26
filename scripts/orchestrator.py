#!/usr/bin/env python3
"""
起点小说工厂 · 自动化调度系统

用法:
  python3 orchestrator.py new <书名> <类型>    创建新书 → 全自动流水线
  python3 orchestrator.py resume <项目ID>       恢复中断的项目
  python3 orchestrator.py daily <项目ID>       日更模式（写下一章）
  python3 orchestrator.py batch <项目ID> <章节数>  批量生成 N 章
  python3 orchestrator.py status [项目ID]      查看项目/看板状态
  python3 orchestrator.py list                 列出所有项目

交互模式（无参数启动）:
  python3 orchestrator.py
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_service import MemoryService
from agent_runner import run_agent, build_context_for_agent, parse_draft_output
from anti_rep import run_anti_rep

# ============================================================
# 流水线阶段定义
# ============================================================
PIPELINE_STAGES = [
    ("research",        "选题研究",     "分析起点当前热门趋势，确定题材方向和差异化切入点"),
    ("world_building",  "世界观构建",   "构建完整世界观：地图、历史、规则、修炼体系、势力分布"),
    ("character_design","角色设计",     "设计主角+核心配角+反派的人设、成长线、关系网"),
    ("arc_planning",    "ARC规划",     "设计第一卷 ARC 的起承转合、核心事件、反转点、尾钩"),
    ("outline",         "章节大纲",     "将 ARC 拆解为具体章节大纲，每章标注功能和线索"),
]


def build_stage_prompt(stage: str, project_id: str) -> str:
    """构建每个阶段的 Agent 提示词"""
    from memory_service import get_memory
    mem = get_memory()
    proj = mem.get_project(project_id)
    title = proj.get("title", "")
    genre = proj.get("genre", "")

    world = mem.get_world_bible(project_id)
    chars = mem.get_characters(project_id)
    arcs = mem.get_arcs(project_id)

    world_text = ""
    if world:
        import json as _j
        world_text = _j.dumps(world, ensure_ascii=False, default=str)[:3000]

    char_text = ""
    if chars:
        char_text = "\n".join([f"{c['name']}（{c.get('role','')}）: {c.get('personality','')}"
                               for c in chars[:8]])

    arc_text = ""
    if arcs:
        arc_text = "\n".join([f"ARC {a.get('arc_number','')}: {a.get('title','')} - {a.get('goal','')}"
                              for a in arcs])

    prompts = {
        "research": f"""你是一本起点小说的选题研究专家。

【小说信息】
书名：{title}
类型：{genre}
平台：起点中文网
目标：500万字精品长篇

【任务】
请完成以下研究并输出：

【市场分析】
- 当前起点该类型的 TOP3 作品及各自特色
- 该类型读者的核心爽点和期待

【差异化定位】
- 本作的独特卖点（至少3个）
- 与竞品的差异化路径

【标题方向】
- 推荐5个起点风格的候选书名
- 每个附简短说明

【标签策略】
- 推荐标签组合
- 目标读者画像

输出为结构化文本，不要用表格。""",

        "world_building": f"""你是起点小说世界观架构师。

【小说信息】
书名：{title}
类型：{genre}

【已有设定】
{world_text if world_text else '（暂无，请从零构建）'}

【任务】
请构建完整的世界观圣经，包括：

【世界名称与核心概念】
- 世界名称
- 核心运行规则（5-8条）
- 世界的独特之处

【地理与区域】
- 主要区域划分（至少5个）
- 各区域特色、势力、资源

【历史】
- 重要历史事件（至少3个关键节点）
- 当前时代背景

【修炼/力量体系】
- 等级划分（至少8个境界）
- 突破条件与代价
- 各境界的战力天花板

【势力分布】
- 主要势力（宗门/家族/国家等，至少5个）
- 势力间的敌对/联盟关系
- 势力目标

【禁忌规则】
- 世界中不可触碰的规则（至少3条）
- 违反规则的代价

输出请完整详细，每个部分都要充分展开。""",

        "character_design": f"""你是起点小说角色设计师。

【小说信息】
书名：{title}
类型：{genre}

【世界观约束】
{world_text[:2000] if world_text else '请基于该类型常见设定'}

【任务】
请设计核心角色阵容（至少6个角色）：

【主角】
- 姓名、年龄、外貌
- 性格特质（至少5个维度）
- 背景故事（完整叙述）
- 初始处境
- 核心动机/目标
- 独特能力/天赋
- 成长路线（长期）
- 性格缺陷（至少2个致命的）
- 行为禁忌（绝对不会做的事）

【核心配角】（至少3个）
每人包含：姓名、角色定位、与主角关系、性格、动机、在故事中的作用

【反派】（至少1个）
- 姓名、定位
- 动机（必须有合理性，不能是纯粹的恶）
- 与主角的冲突源头
- 反派自身的成长线（不能是静态的靶子）

【关系网络】
- 角色间的初始关系
- 潜在冲突
- 感情线走向

输出请完整详细，每个角色都要有充分的血肉。""",

        "arc_planning": f"""你是起点小说 ARC 规划师。

【小说信息】
书名：{title}
类型：{genre}

【已有角色】
{char_text[:1500]}

【任务】
请设计第一卷 ARC（第1-200章）的完整规划：

【ARC 信息】
- ARC 标题
- 核心主题
- 主角在本 ARC 的成长目标

【七阶段结构】
按「起-承-爆-反转-高潮-余波-新坑」设计：

起（第1-30章）：
- 开篇事件
- 世界观初次展示
- 主角初始处境建立

承（第31-70章）：
- 第一次能力提升
- 第一次势力接触
- 第一次重大选择

爆（第71-100章）：
- 第一个爆点事件
- 读者预期被打破
- 战力/地位跃升

反转（第101-140章）：
- 核心反转（颠覆已有认知）
- 隐藏线索回收
- 世界观层次提升

高潮（第141-170章）：
- ARC 终极对抗
- 情感高潮
- 核心伏笔回收

余波（第171-190章）：
- 战后世界变化
- 角色关系重塑
- 收获与代价

新坑（第191-200章）：
- 下一 ARC 的引子
- 新威胁/新世界的暗示
- 让读者必须追下去的钩子

【核心事件列表】
- 至少 15 个关键事件，标注大致章节位置

【伏笔规划】
- 至少 5 条长线伏笔，标注埋设点和计划回收点

【反转设计】
- 至少 3 个反转节点
- 每个反转的前置铺垫

输出请完整详细。""",

        "outline": f"""你是起点小说章节大纲规划师。

【小说信息】书名：{title}，类型：{genre}

【ARC 规划】
{arc_text[:2000]}

【角色】
{char_text[:1000]}

【任务】
请将第一卷 ARC 拆解为前 30 章的详细章节大纲：

输出格式（每章）：
第N章 | 功能标签（主线推进/战斗/感情/搞笑缓冲/伏笔/反转） | 本章核心事件（一句话） | 需要推进的线索 | 埋下的伏笔

要求：
- 前 3 章必须快速建立读者期待（黄金三章）
- 每 5 章有一个小高潮
- 每 10 章有一个情绪转折
- 章节之间逻辑连贯，无断层

请直接输出 30 行的章节大纲。""",
    }

    return prompts.get(stage, "")


# ============================================================
# 核心调度逻辑
# ============================================================
class Orchestrator:
    def __init__(self):
        self.mem = MemoryService()

    # ---- 新书创建 ----
    def create_new_project(self, title: str, genre: str) -> str:
        """创建新书并启动全自动流水线"""
        print(f"\n{'='*60}")
        print(f"  起点小说工厂 · 自动化调度")
        print(f"  书名：{title}")
        print(f"  类型：{genre}")
        print(f"  时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        project_id = self.mem.create_project(title, genre)
        print(f"✅ 项目已创建 | ID: {project_id}\n")

        # 阶段 1-5: 准备阶段
        for card_type, stage_name, desc in PIPELINE_STAGES:
            print(f"\n{'─'*50}")
            print(f"📋 阶段: {stage_name}")
            print(f"   {desc}")
            print(f"{'─'*50}")

            success = self._run_stage(project_id, card_type, stage_name)
            if not success:
                print(f"\n❌ 阶段 [{stage_name}] 失败，项目暂停。")
                print(f"   可用 `python3 orchestrator.py resume {project_id}` 恢复")
                return project_id

            time.sleep(2)  # API 调用间隔

        print(f"\n{'='*60}")
        print(f"  ✅ 准备阶段全部完成！")
        print(f"  项目 ID: {project_id}")
        print(f"  下一步: python3 orchestrator.py batch {project_id} 10")
        print(f"{'='*60}\n")
        return project_id

    # ---- 单阶段运行 ----
    def _run_stage(self, project_id: str, card_type: str,
                   stage_name: str, retry_count: int = 0) -> bool:
        """运行单个流水线阶段"""
        max_retries = 2

        agent_type = self.mem._card_to_agent(card_type)
        context = build_context_for_agent(project_id, agent_type)
        prompt = build_stage_prompt(card_type, project_id)

        if not prompt:
            print(f"   ⚠ 跳过: 无对应提示词")
            return True

        print(f"   🤖 调用 Agent: {agent_type}")
        stdout, stderr, ok = run_agent(agent_type, prompt, context, max_retries=2)

        if not ok:
            print(f"   ❌ Agent 调用失败: {stderr[:200]}")
            if retry_count < max_retries:
                print(f"   🔄 重试 ({retry_count+1}/{max_retries})...")
                time.sleep(3)
                return self._run_stage(project_id, card_type, stage_name, retry_count + 1)
            return False

        # 存储产出
        self._store_stage_output(project_id, card_type, stdout)
        self.mem.log_agent_run(project_id, agent_type, card_type, "success",
                               stdout[:300])

        print(f"   ✅ {stage_name} 完成 | 产出 {len(stdout)} 字符")
        return True

    # ---- 存储各阶段产出到 MongoDB ----
    def _store_stage_output(self, project_id: str, card_type: str, output: str):
        """解析 Agent 输出并存储到 MongoDB"""
        import re

        if card_type == "world_building":
            # 简单存全文，后续可解析
            self.mem.upsert_world_bible(project_id, {
                "raw_output": output,
                "updated_at": datetime.utcnow().isoformat(),
            })

        elif card_type == "character_design":
            # 尝试解析角色，简单按段落存
            self.mem.db.characters.delete_many({"project_id": project_id})
            sections = re.split(r'\n#{1,3}\s+', output)
            for sec in sections:
                if not sec.strip():
                    continue
                # 提取角色名
                name_match = re.search(r'[主角|配角|反派|核心配角].*?[：:]\s*(\S{1,8})', sec)
                if name_match:
                    self.mem.create_character(project_id, {
                        "name": name_match.group(1),
                        "raw_data": sec[:500],
                    })

        elif card_type == "arc_planning":
            self.mem.create_arc(project_id, {
                "arc_number": self.mem.get_arcs(project_id).__len__() + 1,
                "title": "第一卷",
                "goal": "ARC 规划",
                "start_chapter": 1,
                "end_chapter": 200,
                "raw_output": output[:5000],
            })

        elif card_type == "outline":
            self.mem.upsert_world_bible(project_id, {
                "outline": output[:5000],
                "updated_at": datetime.utcnow().isoformat(),
            })

    # ---- 批量章节生成 ----
    def batch_draft(self, project_id: str, chapter_count: int):
        """批量生成 N 章"""
        proj = self.mem.get_project(project_id)
        if not proj:
            print(f"❌ 项目不存在: {project_id}")
            return

        start_ch = proj.get("current_chapter", 0) + 1
        print(f"\n{'='*60}")
        print(f"  批量生成: 《{proj['title']}》")
        print(f"  章节: 第 {start_ch} - {start_ch + chapter_count - 1} 章")
        print(f"{'='*60}\n")

        for i in range(chapter_count):
            ch = start_ch + i
            chapter_title = f"第{ch}章"

            print(f"\n{'─'*50}")
            print(f"  📝 {chapter_title} / {start_ch + chapter_count - 1}")
            print(f"{'─'*50}")

            success = self._write_chapter(project_id, ch)
            if not success:
                print(f"\n  ❌ {chapter_title} 生成失败，已重试 3 次，跳过")
                continue

            # 更新项目进度
            self.mem.update_project(project_id, {
                "current_chapter": ch,
                "status": "writing",
            })

            time.sleep(3)  # API 调用间隔

        print(f"\n{'='*60}")
        print(f"  ✅ 批量生成完成")
        print(f"  生成: {chapter_count} 章")
        print(f"  当前进度: 第 {ch} 章")
        print(f"{'='*60}\n")

    # ---- 单章写作 ----
    def _write_chapter(self, project_id: str, chapter: int) -> bool:
        """写一章（写→审→改 完整流程）"""
        # 1. 写正文
        prompt = self._build_draft_prompt(project_id, chapter)
        context = build_context_for_agent(project_id, "draft-writer")

        print(f"   ✍️  drafting...")
        stdout, stderr, ok = run_agent("draft-writer", prompt, context, timeout=360)
        if not ok:
            print(f"   ❌ 写作失败: {stderr[:100]}")
            return False

        parsed = parse_draft_output(stdout)
        if not parsed:
            print(f"   ❌ 无法解析输出，可能为空或格式错误")
            return False

        word_count = parsed.get("word_count", 0)
        content = parsed.get("content", "")

        print(f"   📊 字数: {word_count} | 钩子: {parsed.get('hook','')[:40]}")

        if word_count < 500:
            print(f"   ❌ 字数过少 ({word_count})，可能失败")
            return False

        # ---- 反重复检测 ----
        print(f"   🔬 anti-rep...")
        prev_chapters = self.mem.get_recent_chapter_contents(project_id, 5)
        ar_result = run_anti_rep(content, prev_chapters)
        print(f"   📊 反重复评分: {ar_result['score']}/100", end="")
        if ar_result["pass"]:
            print(" ✅")
        else:
            print(" ⚠")
            if ar_result["cliche_details"]:
                phrases = [d["phrase"] for d in ar_result["cliche_details"][:5]]
                print(f"      模板用语: {', '.join(phrases)}")
            if ar_result["advice"]:
                print(f"      建议: {ar_result['advice']}")

        # 2. 编辑审校（传入反重复报告）
        print(f"   🔍 editing...")
        edit_prompt = self._build_edit_prompt(chapter, content, ar_result)
        edit_stdout, _, edit_ok = run_agent("editor", edit_prompt, timeout=180)

        edited_content = content
        if edit_ok and edit_stdout:
            # 尝试提取修改后的正文
            import re
            m = re.search(r'【修改后正文】\s*(.+?)(?=\n【|$)', edit_stdout, re.DOTALL)
            if m and len(m.group(1).strip()) > 100:
                edited_content = m.group(1).strip()
                print(f"   ✅ 编辑完成")
            else:
                print(f"   ⚠ 编辑未产生修改，保留原文")

        # 3. 起点精品审核
        print(f"   👁  reviewing...")
        review_prompt = self._build_review_prompt(chapter, edited_content)
        review_stdout, _, review_ok = run_agent("reviewer", review_prompt, timeout=120)
        if review_ok:
            # 检查是否通过
            if "通过" in review_stdout or "pass" in review_stdout.lower():
                print(f"   ✅ 审核通过")
            else:
                print(f"   ⚠ 审核有建议：{review_stdout[:100]}")

        # 4. 存储
        self.mem.create_chapter(project_id, {
            "chapter": chapter,
            "title": f"第{chapter}章",
            "content": edited_content,
            "raw_content": content,
            "edited_content": edited_content,
            "word_count": word_count,
            "chapter_goal": parsed.get("chapter_goal", ""),
            "foreshadow": parsed.get("foreshadow", ""),
            "hook": parsed.get("hook", ""),
            "growth": parsed.get("growth", ""),
            "review_notes": review_stdout[:500] if review_ok else "",
            "status": "published" if review_ok else "draft",
        })

        self.mem.log_agent_run(project_id, "draft-writer", f"ch{chapter}",
                               "success", f"第{chapter}章 完成 ({word_count}字)")

        print(f"   💾 已存储")

        # 5. 伏笔追踪
        n_saved, n_resolved = self._track_foreshadows(project_id, chapter, parsed, content)
        if n_saved > 0:
            print(f"   📌 伏笔: +{n_saved} 新埋", end="")
        if n_resolved > 0:
            print(f" / {n_resolved} 已回收", end="")
        if n_saved + n_resolved > 0:
            print()

        return True

    # ---- 伏笔追踪 ----
    def _track_foreshadows(self, project_id: str, chapter: int,
                           parsed: dict, content: str) -> Tuple[int, int]:
        """追踪本章伏笔：保存新埋的，检测回收的。返回 (新埋数, 回收数)"""
        import re

        # A. 保存新伏笔
        foreshadow_text = parsed.get("foreshadow", "")
        n_saved = 0
        if foreshadow_text:
            # 尝试按 "内容：" 分割多个伏笔
            items = re.split(r'[-•]\s*内容[：:]', foreshadow_text)
            if len(items) > 1:
                items = items[1:]  # 去掉第一个空白段
            else:
                items = [foreshadow_text]

            for item in items:
                item = item.strip()
                if len(item) < 5:
                    continue
                # 提取内容和类型
                content_match = re.search(r'^(.+?)(?=\s*[-•]\s*类型)', item, re.DOTALL)
                f_content = content_match.group(1).strip()[:300] if content_match else item[:300]

                type_match = re.search(r'类型[：:]\s*(.+?)(?:\s*[-•]|$)', item)
                f_type = type_match.group(1).strip()[:50] if type_match else ""

                plan_match = re.search(r'计划回收章号[：:]\s*(.+?)$', item)
                planned_ch = int(plan_match.group(1).strip()) if plan_match and plan_match.group(1).strip().isdigit() else 0

                self.mem.create_foreshadow(project_id, {
                    "setup_chapter": chapter,
                    "content": f_content,
                    "type": f_type,
                    "planned_payoff": planned_ch,
                })
                n_saved += 1

        # B. 检测伏笔回收（关键词匹配）
        n_resolved = 0
        active_fs = self.mem.get_active_foreshadows(project_id)
        payoff_signals = ["终于", "真相大白", "原来是", "揭开了", "明白了",
                         "原来如此", "难怪", "果然", "竟是"]

        for fs in active_fs:
            fs_content = fs.get("content", "")
            if not fs_content or len(fs_content) < 3:
                continue

            # 取伏笔内容的关键词（前10个汉字）
            keywords = re.findall(r'[\u4e00-\u9fff]{2,}', fs_content)
            key_phrase = ''.join(keywords[:3]) if keywords else fs_content[:6]

            # 检查本章是否包含该关键词 + 回收信号
            if key_phrase in content:
                for signal in payoff_signals:
                    # 关键词前后20字内出现回收信号
                    idx = content.find(key_phrase)
                    window = content[max(0, idx-20):idx+len(key_phrase)+20]
                    if signal in window:
                        self.mem.resolve_foreshadow(
                            project_id, fs["foreshadow_id"], chapter
                        )
                        n_resolved += 1
                        break

        return n_saved, n_resolved

    # ---- 提示词构建 ----
    def _build_draft_prompt(self, project_id: str, chapter: int) -> str:
        """构建章节写作提示词。世界观/大纲/角色等动态约束已由 build_context_for_agent 注入。"""
        proj = self.mem.get_project(project_id)

        return f"""你是《{proj["title"]}》的作者。请写第{chapter}章正文。

【重要】以上「世界观设定」「本卷 ARC 完整规划」「角色列表」是你必须遵循的硬约束。所有设定（修炼体系、世界法则、势力关系、人物性格）必须严格遵守，不得自行创造或修改。

【章节要求】
1. 字数：2200-2800 汉字
2. 推动至少 2 条线索（成长线/势力线/感情线/世界观线）
3. 埋设至少 1 个可回收伏笔
4. 章尾设置强力钩子
5. 对话使用 ASCII 双引号 ""
6. 禁止 AI 模板化表达（眼中闪过、嘴角浮现、瞳孔收缩等）
7. 禁止低级打脸流水线
8. 沉浸感优先，用五感描写
9. 严格遵循上述世界观中的修炼体系、境界划分、世界规则

请按以下格式输出：

【本章目标】
一句话

【正文】
（完整章节正文）

【线索推进报告】
- 成长线：
- 势力线：
- 感情线：
- 世界观线：
（至少填 2 条）

【新埋伏笔】
- 内容：
- 类型：
- 计划回收章号：

【章尾钩子】
（让读者必须翻下一章）

【角色状态更新】
- 主角变化：
- 配角变化："""

    def _build_edit_prompt(self, chapter: int, content: str, anti_rep_result: dict = None) -> str:
        # 构建反重复提示
        ar_section = ""
        if anti_rep_result and not anti_rep_result.get("pass", True):
            cliches = [d["phrase"] for d in anti_rep_result.get("cliche_details", [])[:5]]
            ar_section = f"""
【反重复检测报告】
评分: {anti_rep_result['score']}/100
模板化用语: {', '.join(cliches) if cliches else '无'}
建议: {anti_rep_result.get('advice', '')}
"""
        return f"""你是起点小说审校编辑。请修改以下章节正文。{ar_section}
【第{chapter}章原文】
{content[:3000]}

【修改要求】
1. 修正错别字和语法错误
2. 消除 AI 模板化表达（替换为自然描写）。特别注意上述报告中的模板用语
3. 优化节奏（过慢的地方加速，过快的地方补充细节）
4. 确保对话使用 ASCII 双引号 ""
5. 确保角色行为符合人设
6. 保持原文章节结构和字数（2200-2800字）

请输出：

【修改后正文】
（完整修改后正文）"""

    def _build_review_prompt(self, chapter: int, content: str) -> str:
        return f"""你是起点精品审稿人。请审核以下章节。

【第{chapter}章】
{content[:2500]}

【审核维度】
1. 世界观深度：是否展示了足够的世界细节
2. 角色魅力：角色是否有血有肉
3. 追读价值：本章结尾是否让人想继续
4. 精品感：是否避免了网文常见套路
5. 模板化检测：是否存在 AI 高频用语

请输出：
- 评分（1-10）
- 主要问题（如有）
- 优化建议（如有）
- 最终判定：通过 / 需修改"""

    # ---- 交互式 CLI ----
    def interactive(self):
        """交互式菜单"""
        while True:
            print(f"\n{'='*50}")
            print(f"  起点小说工厂 | 总调度台")
            print(f"  项目数: {self.mem._db.projects.count_documents({})}")
            print(f"{'='*50}")
            print(f"  1. 创建新书（全自动流水线）")
            print(f"  2. 列出所有项目")
            print(f"  3. 查看项目状态")
            print(f"  4. 批量生成章节")
            print(f"  5. 日更（写下一章）")
            print(f"  0. 退出")
            print(f"{'='*50}")

            try:
                choice = input("  > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  再见！")
                break

            if choice == "1":
                title = input("  书名: ").strip()
                genre = input("  类型（玄幻/修仙/高武/末世/科幻/领主...）: ").strip()
                if title and genre:
                    self.create_new_project(title, genre)

            elif choice == "2":
                projects = list(self.mem._db.projects.find({}, {"_id": 0, "project_id": 1, "title": 1, "genre": 1, "status": 1, "current_chapter": 1}))
                if not projects:
                    print("  (无项目)")
                for p in projects:
                    print(f"  [{p['project_id']}] {p['title']} | {p['genre']} | {p['status']} | 第{p.get('current_chapter',0)}章")

            elif choice == "3":
                pid = input("  项目 ID: ").strip()
                self._show_status(pid)

            elif choice == "4":
                pid = input("  项目 ID: ").strip()
                n = input("  章节数（默认10）: ").strip()
                self.batch_draft(pid, int(n) if n else 10)

            elif choice == "5":
                pid = input("  项目 ID: ").strip()
                self.batch_draft(pid, 1)

            elif choice == "0":
                print("  再见！")
                break

            else:
                print("  未知选项")

    def _show_status(self, project_id: str):
        """显示项目详情"""
        proj = self.mem.get_project(project_id)
        if not proj:
            print(f"  ❌ 项目不存在")
            return

        print(f"\n  📖 {proj['title']}")
        print(f"  类型: {proj['genre']} | 状态: {proj['status']}")
        print(f"  进度: 第 {proj.get('current_chapter', 0)} 章")
        print(f"  ARC: 第 {proj.get('current_arc', 1)} 卷")

        chars = self.mem.get_characters(project_id)
        print(f"  角色: {len(chars)} 个")

        arcs = self.mem.get_arcs(project_id)
        print(f"  ARC: {len(arcs)} 个")

        foreshadows = self.mem.get_active_foreshadows(project_id)
        print(f"  活跃伏笔: {len(foreshadows)} 条")


# ============================================================
# 入口
# ============================================================
def main():
    orch = Orchestrator()

    if len(sys.argv) == 1:
        orch.interactive()
        return

    cmd = sys.argv[1]

    if cmd == "new":
        if len(sys.argv) < 4:
            print("用法: python3 orchestrator.py new <书名> <类型>")
            sys.exit(1)
        title, genre = sys.argv[2], sys.argv[3]
        orch.create_new_project(title, genre)

    elif cmd == "batch":
        if len(sys.argv) < 4:
            print("用法: python3 orchestrator.py batch <项目ID> <章节数>")
            sys.exit(1)
        pid, n = sys.argv[2], int(sys.argv[3])
        orch.batch_draft(pid, n)

    elif cmd == "daily":
        if len(sys.argv) < 3:
            print("用法: python3 orchestrator.py daily <项目ID>")
            sys.exit(1)
        orch.batch_draft(sys.argv[2], 1)

    elif cmd == "status":
        if len(sys.argv) < 3:
            projects = list(orch.mem._db.projects.find({}, {"_id": 0, "project_id": 1, "title": 1, "genre": 1, "status": 1, "current_chapter": 1}))
            if not projects:
                print("(无项目)")
            for p in projects:
                print(f"[{p['project_id']}] {p['title']} | {p['genre']} | {p['status']} | 第{p.get('current_chapter',0)}章")
        else:
            orch._show_status(sys.argv[2])

    elif cmd == "list":
        projects = list(orch.mem._db.projects.find({}, {"_id": 0, "project_id": 1, "title": 1, "genre": 1, "status": 1, "current_chapter": 1}))
        for p in projects:
            print(f"[{p['project_id']}] {p['title']} | {p['genre']} | {p['status']} | 第{p.get('current_chapter',0)}章")

    elif cmd == "resume":
        if len(sys.argv) < 3:
            print("用法: python3 orchestrator.py resume <项目ID>")
            sys.exit(1)
        pid = sys.argv[2]
        print(f"恢复项目 {pid}... (跳过已完成阶段，继续未完成的)")
        # TODO: 检测进度并继续
        print("请使用 batch 命令继续生成章节")

    else:
        print(f"未知命令: {cmd}")
        print("可用: new, batch, daily, status, list, resume")


if __name__ == "__main__":
    main()
