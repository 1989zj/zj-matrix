#!/usr/bin/env python3
"""
起点小说工厂 · Agent 调用封装
每个 Agent Profile 通过 `hermes -p <profile> -z <prompt>` 调用。
处理：prompt 构建、超时控制、输出解析、重试逻辑。
"""

import subprocess
import tempfile
import os
import re
import json
import time
import sys
from typing import Optional, Dict, Tuple
from datetime import datetime


PROFILE_MAP = {
    "orchestrator": "qidian-orchestrator",
    "world-builder": "qidian-world-builder",
    "arc-planner": "qidian-arc-planner",
    "character-designer": "qidian-character-designer",
    "draft-writer": "qidian-draft-writer",
    "editor": "qidian-editor",
    "reviewer": "qidian-reviewer",
    "memory-manager": "qidian-memory-manager",
}

TIMEOUTS = {
    "orchestrator": 120,
    "world-builder": 480,         # 完整世界观生成慢
    "arc-planner": 480,           # ARC 规划输出长
    "character-designer": 480,    # 角色阵容详细，实测 260s+
    "draft-writer": 600,          # 写正文最慢
    "editor": 300,
    "reviewer": 180,
    "memory-manager": 60,
}


def run_agent(agent_type: str, prompt: str, context: str = "",
              timeout: int = None, max_retries: int = 2) -> Tuple[str, str, bool]:
    """
    调用 Hermes Agent Profile。

    参数:
        agent_type: Agent 类型（orchestrator, draft-writer 等）
        prompt: 任务提示词（不含上下文）
        context: 上下文信息（MongoDB 数据等，拼在 prompt 前面）
        timeout: 超时秒数，默认按 agent 类型自动选择
        max_retries: 最大重试次数

    返回:
        (stdout, stderr, success)
    """
    profile = PROFILE_MAP.get(agent_type)
    if not profile:
        return "", f"未知 Agent 类型: {agent_type}", False

    if timeout is None:
        timeout = TIMEOUTS.get(agent_type, 180)

    full_prompt = f"{context}\n\n---\n\n{prompt}" if context else prompt

    for attempt in range(max_retries + 1):
        try:
            # 先切换 profile（持久化到 ~/.hermes/config.yaml）
            subprocess.run(
                f"hermes profile use {profile}",
                shell=True, capture_output=True, text=True, timeout=15,
                cwd=os.path.expanduser("~"),
            )

            # 用列表传参，Python subprocess 原生处理特殊字符，无 shell 转义隐患
            result = subprocess.run(
                ["hermes", "-z", full_prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.path.expanduser("~"),
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            # 检查是否产生了有效输出（排除纯初始化信息）
            if _has_meaningful_output(stdout):
                return stdout, stderr, True

            # 重试
            if attempt < max_retries:
                time.sleep(2 ** attempt)  # 指数退避
                sys.stderr.write(f"[重试 {attempt+1}/{max_retries}] {agent_type}: 输出无效, stderr={stderr[:100]}\n")

        except subprocess.TimeoutExpired:
            stderr = f"超时 ({timeout}s)"
            if attempt < max_retries:
                timeout *= 2
                sys.stderr.write(f"[重试 {attempt+1}/{max_retries}] {agent_type} 超时，延长到 {timeout}s\n")
        except Exception as e:
            stderr = str(e)
            if attempt < max_retries:
                sys.stderr.write(f"[重试 {attempt+1}/{max_retries}] {agent_type}: {e}\n")

    return "", stderr, False


def _has_meaningful_output(stdout: str) -> bool:
    """检查输出是否包含有效内容（非纯初始化/空输出）"""
    if not stdout or len(stdout) < 20:
        return False
    noise_patterns = [
        r"^Initializing agent[\.]{0,3}$",
        r"^Goodbye!",
        r"^Session:",
        r"^Duration:",
        r"^Messages:",
    ]
    lines = stdout.strip().split("\n")
    meaningful = [l for l in lines if not any(re.match(p, l.strip()) for p in noise_patterns)]
    return len(meaningful) >= 1 and len("\n".join(meaningful).strip()) >= 20


def build_context_for_agent(project_id: str, agent_type: str) -> str:
    """从 MongoDB 构建 Agent 上下文。draft-writer 获得更丰富的世界观注入。"""
    from memory_service import get_memory
    mem = get_memory()
    project = mem.get_project(project_id)

    genre = project.get('genre', '')
    context_parts = [
        f"【项目信息】\n标题：{project.get('title', '')}\n类型：{genre}\n"
        f"目标字数：{project.get('target_words', 0)}\n当前进度：第 {project.get('current_chapter', 0)} 章 / "
        f"第 {project.get('current_arc', 1)} ARC\n"
    ]

    # 世界观 —— draft-writer 吃大头，其它 Agent 吃摘要
    world = mem.get_world_bible(project_id)
    if world:
        if agent_type == "draft-writer":
            # 注入完整世界观核心内容（修炼规则、世界法则、境界体系）
            raw = world.get('raw_output', '')
            max_chars = 6000
            context_parts.append(f"【世界观设定（务必遵循以下所有规则）】\n{raw[:max_chars]}")
        else:
            context_parts.append(f"【世界观摘要】\n{_dict_to_text(world, 500)}")

    # 角色 —— draft-writer 看全部
    chars = mem.get_characters(project_id)
    if chars:
        if agent_type == "draft-writer":
            char_text = "\n".join([
                f"- {c['name']}（{c.get('role','')}）\n  当前状态: {c.get('current_state','无')}\n"
                f"  能力: {str(c.get('abilities',''))[:100]}"
                for c in chars
            ])
            context_parts.append(f"【角色列表（{len(chars)} 人）】\n{char_text}")
        else:
            char_text = "\n".join([f"- {c['name']}（{c.get('role','')}）: {c.get('current_state','')}"
                                   for c in chars[:5]])
            context_parts.append(f"【角色列表】\n{char_text}")

    # ARC —— draft-writer 看完整规划
    arcs = mem.get_arcs(project_id)
    if arcs:
        if agent_type == "draft-writer" and arcs[0].get('raw_output'):
            arc_raw = arcs[0].get('raw_output', '')
            context_parts.append(f"【本卷 ARC 完整规划】\n{arc_raw[:4000]}")
        else:
            arc_text = "\n".join([f"- ARC{a['arc_id']}: {a['title']} (第{a['start_chapter']}-{a['end_chapter']}章)"
                                  for a in arcs])
            context_parts.append(f"【ARC 规划】\n{arc_text}")

    # 最近章节
    if agent_type == "draft-writer":
        recent = mem.get_recent_chapters(project_id, 3)
        if recent:
            chap_text = "\n".join([f"第{c['chapter']}章: {c.get('summary','')[:200]}"
                                   for c in reversed(recent)])
            context_parts.append(f"【前情提要】\n{chap_text}")

        # 活跃伏笔
        foreshadows = mem.get_active_foreshadows(project_id)
        if foreshadows:
            fs_text = "\n".join([f"- {f['content'][:120]} (埋于第{f['setup_chapter']}章, "
                                 f"计划回收: 第{f.get('planned_payoff','?')}章)"
                                 for f in foreshadows[:10]])
            context_parts.append(f"【待回收伏笔】\n{fs_text}")

        # 大纲
        if world and "outline" in world:
            outline = world["outline"]
            context_parts.append(f"【章节大纲参考】\n{outline[:2000]}")

    return "\n\n".join(context_parts)


def _dict_to_text(d: Dict, max_len: int = 500) -> str:
    """字典转简短文本"""
    text = json.dumps(d, ensure_ascii=False, default=str)
    return text[:max_len] + ("..." if len(text) > max_len else "")


def parse_draft_output(output: str) -> Optional[Dict]:
    """解析 draft-writer 输出，提取章节数据"""
    data = {
        "content": "",
        "chapter_goal": "",
        "growth": "",
        "foreshadow": "",
        "hook": "",
    }

    # 提取【本章目标】
    m = re.search(r'【本章目标】\s*(.+?)(?=\n【|$)', output, re.DOTALL)
    if m:
        data["chapter_goal"] = m.group(1).strip()[:200]

    # 提取【正文】
    m = re.search(r'【正文】\s*(.+?)(?=\n【线索推进|$)', output, re.DOTALL)
    if m:
        data["content"] = m.group(1).strip()

    # 提取【章尾钩子】
    m = re.search(r'【章尾钩子】\s*(.+?)(?=\n【|$)', output, re.DOTALL)
    if m:
        data["hook"] = m.group(1).strip()[:200]

    # 提取【新埋伏笔】
    m = re.search(r'【新埋伏笔】\s*(.+?)(?=\n【|$)', output, re.DOTALL)
    if m:
        data["foreshadow"] = m.group(1).strip()[:500]

    # 提取【线索推进报告】
    m = re.search(r'【线索推进报告】\s*(.+?)(?=\n【角色状态|$)', output, re.DOTALL)
    if m:
        data["growth"] = m.group(1).strip()[:300]

    if not data["content"] or len(data["content"]) < 100:
        return None

    data["word_count"] = len(data["content"].replace(" ", "").replace("\n", ""))
    return data


# ============================================================
# CLI 测试
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python3 agent_runner.py <agent_type> <prompt_file> [context_file]")
        sys.exit(1)

    agent = sys.argv[1]

    with open(sys.argv[2], 'r', encoding='utf-8') as f:
        prompt = f.read()

    context = ""
    if len(sys.argv) > 3:
        with open(sys.argv[3], 'r', encoding='utf-8') as f:
            context = f.read()

    print(f"[调用 Agent: {agent}]")
    stdout, stderr, ok = run_agent(agent, prompt, context)

    if ok:
        print(stdout)
    else:
        print(f"失败: {stderr}", file=sys.stderr)
        sys.exit(1)
