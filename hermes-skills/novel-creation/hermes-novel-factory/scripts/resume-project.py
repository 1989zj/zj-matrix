#!/usr/bin/env python3
"""
resume-project.py — V3 中断恢复入口

作用: continue 时检查项目状态，决定恢复策略，输出 resume context。

调用:
  python3 resume-project.py status <project_id> [chapter]

输出: JSON 格式的恢复上下文，包含:
  - resume_strategy: clean_continue | recover_snapshot | edit_chapter | from_scratch
  - last_completed_chapter: 最后完成的章节
  - pending_chapter: 需要处理的下一章
  - context_packet: 最新的 context packet
  - next_actions: 推荐的下一步动作列表
"""

import json
import sys
import os
import datetime
import subprocess
from pathlib import Path

import pymongo

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"

SCRIPTS_DIR = os.path.expanduser(
    "~/.hermes/skills/content-creation/hermes-novel-factory/scripts"
)


def connect():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client, client["novel_factory"], client["novel"]


def run_script(script: str, *args) -> dict:
    """运行一个 Python 脚本并解析其 JSON 输出"""
    full_path = os.path.join(SCRIPTS_DIR, script)
    cmd = [sys.executable, full_path] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return {"status": "error", "message": result.stderr.strip()}
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"JSON parse error: {e}", "raw": result.stdout}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Script timed out"}
    except FileNotFoundError:
        return {"status": "error", "message": f"Script not found: {full_path}"}


def find_project(project_name: str) -> dict:
    """通过名称或 ID 查找项目"""
    client, nf, novel = connect()
    try:
        # 尝试直接匹配 project_id
        proj = nf["projects"].find_one({"project_id": project_name})
        if proj:
            return proj

        # 尝试 title 匹配
        proj = nf["projects"].find_one({"title": {"$regex": project_name, "$options": "i"}})
        if proj:
            return proj

        # 尝试 name 匹配
        proj = nf["projects"].find_one({"name": {"$regex": project_name, "$options": "i"}})
        if proj:
            return proj

        # 尝试 novel 数据库匹配
        proj = novel["novels"].find_one({"name": {"$regex": project_name, "$options": "i"}})
        if proj:
            # 映射到 novel_factory 的 project
            factory_proj = nf["projects"].find_one({"title": {"$regex": proj.get("name", ""), "$options": "i"}})
            return factory_proj or {"project_id": proj.get("name"), "title": proj.get("title", proj.get("name"))}

        return None
    finally:
        client.close()


def get_last_chapter(project_id: str) -> dict:
    """获取项目最后完成状态"""
    client, nf, novel = connect()
    try:
        # 从 event_log 获取
        last_event = nf["event_log"].find_one(
            {"project_id": project_id, "event_type": {"$in": ["chapter_generated", "editor_completed"]}},
            sort=[("version", pymongo.DESCENDING)]
        )
        if last_event:
            chapter = last_event.get("chapter", 0)
            return {
                "chapter": chapter,
                "source": "event_log",
                "last_action": last_event.get("event_type"),
                "version": last_event.get("version"),
            }

        # 从 chapter_memory 获取
        last_mem = nf["chapter_memory"].find_one(
            {"project_id": project_id},
            sort=[("chapter", pymongo.DESCENDING)]
        )
        if last_mem:
            return {
                "chapter": last_mem.get("chapter", 0),
                "source": "chapter_memory",
                "title": last_mem.get("title"),
            }

        return {"chapter": 0, "source": "none"}
    finally:
        client.close()


def check_snapshot_exists(project_id: str, chapter: int) -> bool:
    """检查指定章节的快照是否存在"""
    client, nf, novel = connect()
    try:
        snapshot = nf["snapshot_store"].find_one(
            {"project_id": project_id, "chapter": chapter}
        )
        return snapshot is not None
    finally:
        client.close()


def determine_strategy(project_id: str, last_ch: int) -> dict:
    """决定恢复策略"""
    strategies = []
    has_snapshot = check_snapshot_exists(project_id, last_ch) if last_ch > 0 else False

    if last_ch == 0:
        strategies.append("from_scratch")
        strategies.append("reason: 项目没有已完成章节，需要从头开始")
    elif has_snapshot:
        strategies.append("recover_snapshot")
        strategies.append(f"reason: 存在第{last_ch}章的快照，可以从快照恢复后继续写第{last_ch + 1}章")
    else:
        # 检查能否用 chapter_memory 重建
        client, nf, novel = connect()
        try:
            recent_mems = list(
                nf["chapter_memory"]
                .find({"project_id": project_id})
                .sort("chapter", pymongo.DESCENDING)
                .limit(5)
            )
            if recent_mems:
                strategies.append("build_from_memory")
                strategies.append(f"reason: 无快照但有 {len(recent_mems)} 章内存，通过 context packet 重建状态")
            else:
                strategies.append("from_scratch")
                strategies.append("reason: 没有任何可用数据，从头开始")
        finally:
            client.close()

    return {
        "primary": strategies[0] if strategies else "from_scratch",
        "reason": strategies[1] if len(strategies) > 1 else "",
    }


def determine_project_running_status(project_id: str) -> dict:
    """检测项目是否正在被 novel-factory 处理"""
    # 检查是否有正在运行的 hermes 进程
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=5,
        )
        running_count = result.stdout.count(f"project_id={project_id}")
        if running_count > 0:
            return {"running": True, "processes": running_count}
    except:
        pass
    return {"running": False, "processes": 0}


def cmd_status(project_name: str, chapter: int = None):
    """主状态恢复函数"""
    # Step 1: Find project
    project = find_project(project_name)
    if not project:
        return {"status": "error", "message": f"找不到项目: {project_name}"}

    project_id = project.get("project_id", project.get("name", project_name))
    title = project.get("title", project.get("name", project_name))

    # Step 2: Get last completed chapter
    last_info = get_last_chapter(project_id)
    last_chapter = last_info.get("chapter", 0)

    # Step 3: Determine next chapter to write
    next_chapter = last_chapter + 1
    if chapter:
        # 用户指定了章节
        next_chapter = chapter
        # 如果指定章节比已完成的还小，可能是编辑模式
        if chapter <= last_chapter:
            pass  # 编辑模式，稍后判断

    # Step 4: Get context packet
    ctx_cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "build-context-packet.py"), project_id]
    if chapter:
        ctx_cmd.append(str(chapter))

    context_packet = None
    try:
        ctx_result = subprocess.run(ctx_cmd, capture_output=True, text=True, timeout=30)
        if ctx_result.returncode == 0:
            context_packet = json.loads(ctx_result.stdout)
            if "error" in context_packet:
                context_packet = None
    except:
        pass

    # Step 5: Determine strategy
    strategy = determine_strategy(project_id, last_chapter)

    # Step 6: Check if running
    running_status = determine_project_running_status(project_id)

    # Step 7: Build resume state
    resume_state = {
        "status": "ok",
        "project": {
            "id": project_id,
            "title": title,
            "genre": project.get("genre", "未知"),
            "total_chapters_expected": project.get("total_chapters", 0),
            "words_planned": project.get("total_words", 0),
        },
        "progress": {
            "last_completed_chapter": last_chapter,
            "next_chapter_to_write": next_chapter,
            "source_of_last": last_info.get("source", "unknown"),
            "total_chapters_in_db": None,
        },
        "strategy": strategy,
        "running_status": running_status,
        "context_packet": context_packet,
        "next_steps": [
            "1. 运行 snapshot-manager.py load 恢复快照",
            f"2. 使用 context_packet 中的 must_remember + active_arcs 引导 draft",
            f"3. 写第 {next_chapter} 章",
            f"4. 运行 validate-chapter.py 校验",
            f"5. 运行 snapshot-manager.py save 保存快照",
            f"6. 运行 event-log-writer.py log 记录",
        ],
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }

    # 补充数据库中的总章节数
    client, nf, novel = connect()
    try:
        total = nf["chapter_memory"].count_documents({"project_id": project_id})
        resume_state["progress"]["total_chapters_in_db"] = total
    finally:
        client.close()

    return resume_state


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  python3 resume-project.py status <project_name_or_id> [chapter]")
        print("")
        print("示例:")
        print("  python3 resume-project.py status '诡异游戏'")
        print("  python3 resume-project.py status proj_gui-yi-you-xi_d3acfcdd")
        print("  python3 resume-project.py status '诡异游戏' 52")
        sys.exit(1)

    cmd = sys.argv[1]
    project_name = sys.argv[2]
    chapter = int(sys.argv[3]) if len(sys.argv) > 3 else None

    if cmd == "status":
        result = cmd_status(project_name, chapter)
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
