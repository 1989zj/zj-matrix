#!/usr/bin/env python3
"""
build-context-packet.py — V3 Context Packet 组装系统

作用: continue 前自动恢复完整上下文，保证 draft agent 不遗忘设定。
调用: python3 build-context-packet.py <project_id> [chapter]
输出: JSON 格式的 Context Packet，直接注入 draft agent 的 prompt。

设计原则:
- 只读 MongoDB，不写任何数据
- 输出是「压缩摘要」而非完整数据（完整数据由 MongoDB 承载）
- 所有字段都有值，不出现 None/null 导致 agent 迷惑
"""

import json
import sys
import datetime
from typing import Optional

import pymongo

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"
RECENT_CHAPTERS_COUNT = 10
MAX_SUMMARY_LENGTH = 200  # 每条摘要的最大字数


def connect():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client, client["novel_factory"], client["novel"]


def build_context_packet(project_id: str, chapter: Optional[int] = None) -> dict:
    """
    组装 Context Packet。

    Args:
        project_id: 项目 ID（如 proj_gui-yi-you-xi_d3acfcdd）
        chapter: 当前章节号。如果为 None，自动获取最新章节。

    Returns:
        完整的 Context Packet dict
    """
    client, nf, novel = connect()
    try:
        # ---- Step 1: Load project info ----
        project = nf["projects"].find_one({"project_id": project_id})
        if not project:
            # 尝试用 proj_ 前缀查找
            project = nf["projects"].find_one({"project_id": {"$regex": project_id}})
            if not project:
                # 尝试用标题查找
                project = nf["projects"].find_one({"title": {"$regex": project_id, "$options": "i"}})
                if not project:
                    return {"error": f"Project not found: {project_id}"}

        project_title = project.get("title") or project.get("name", "Unknown")
        actual_project_id = project["project_id"]

        # ---- Step 2: Determine current chapter ----
        if chapter is None:
            latest_chapter = nf["chapter_memory"].find_one(
                {"project_id": actual_project_id},
                sort=[("chapter", pymongo.DESCENDING)]
            )
            chapter = latest_chapter["chapter"] if latest_chapter else 0

        # ---- Step 3: Load active ARC plans ----
        active_arcs = list(
            nf["arc_plans"]
            .find({"project_id": actual_project_id, "level": "phase"})
            .sort("start_chapter", pymongo.ASCENDING)
        )
        current_arc = None
        for arc in active_arcs:
            start = arc.get("start_chapter", 0)
            end = arc.get("end_chapter", 999999)
            if start <= chapter <= end:
                current_arc = arc
                break
        # fallback: 找最近的未锁定 arc
        if not current_arc:
            current_arc = nf["arc_plans"].find_one(
                {"project_id": actual_project_id, "status": "active"},
                sort=[("start_chapter", pymongo.ASCENDING)]
            )
        # fallback: 从 V2 arcs collection 读
        if not current_arc:
            v2_arc = nf["arcs"].find_one(
                {"project_id": actual_project_id},
                sort=[("arc_id", pymongo.ASCENDING)]
            )
            if v2_arc:
                current_arc = {
                    "arc_id": v2_arc.get("arc_id", "ARC-001"),
                    "name": v2_arc.get("name", v2_arc.get("title", "Main Arc")),
                    "core_conflict": v2_arc.get("core_conflict", ""),
                    "characters_involved": v2_arc.get("characters_involved", []),
                }

        # ---- Step 4: Load recent chapters summary ----
        recent_chapters = list(
            nf["chapter_memory"]
            .find({"project_id": actual_project_id})
            .sort("chapter", pymongo.DESCENDING)
            .limit(RECENT_CHAPTERS_COUNT)
        )
        recent_chapters.reverse()  # chrono order

        recent_summary = []
        for ch in recent_chapters:
            summary_text = ch.get("summary", "")
            if len(summary_text) > MAX_SUMMARY_LENGTH:
                summary_text = summary_text[:MAX_SUMMARY_LENGTH] + "..."
            recent_summary.append({
                "chapter": ch.get("chapter"),
                "title": ch.get("title", f"第{ch.get('chapter','?')}章"),
                "summary": summary_text,
                "hook": ch.get("hook", ""),
                "characters_present": ch.get("characters_present", []),
                "word_count": ch.get("word_count", 0),
            })

        # ---- Step 5: Load active characters ----
        all_characters = list(
            nf["characters"]
            .find({"project_id": actual_project_id})
            .sort("name", pymongo.ASCENDING)
        )
        active_characters = []
        for char in all_characters:
            # 检测角色最近是否活跃
            last_appearance = char.get("last_appearance", 0)
            if last_appearance and chapter - last_appearance <= RECENT_CHAPTERS_COUNT * 2:
                active_characters.append({
                    "name": char.get("name", "Unknown"),
                    "role": char.get("role", char.get("title", "角色")),
                    "personality": char.get("personality", char.get("traits", "")),
                    "goals": char.get("goals", []),
                    "abilities": char.get("abilities", []),
                    "last_appearance": last_appearance,
                })

        # ---- Step 6: Load character states (V3) ----
        character_states = {}
        for char_summary in recent_summary:
            for char_name in char_summary.get("characters_present", []):
                latest_state = nf["character_states"].find_one(
                    {"project_id": actual_project_id, "character": char_name},
                    sort=[("chapter", pymongo.DESCENDING)]
                )
                if latest_state:
                    character_states[char_name] = {
                        "emotion": latest_state.get("emotion", "neutral"),
                        "wealth": latest_state.get("wealth", 0),
                        "combat_level": latest_state.get("combat_level", 1),
                        "health": latest_state.get("health", "normal"),
                        "location": latest_state.get("location", "unknown"),
                    }

        # ---- Step 7: Load world state (V3) ----
        latest_world = nf["world_state"].find_one(
            {"project_id": actual_project_id},
            sort=[("chapter", pymongo.DESCENDING)]
        )
        if latest_world:
            world_state = {
                "economy": latest_world.get("economy", {"level": "stable"}),
                "public_opinion": latest_world.get("public_opinion", {}),
                "power_balance": latest_world.get("power_balance", {}),
                "active_crises": latest_world.get("active_crises", []),
            }
        else:
            world_state = {
                "economy": {"level": "unknown"},
                "public_opinion": {},
                "power_balance": {},
                "active_crises": [],
            }

        # ---- Step 8: Load unresolved foreshadow queue ----
        pending_foreshadows = list(
            nf["foreshadow_queue"]
            .find({"project_id": actual_project_id, "resolved": False})
            .sort("expected_callback_chapter", pymongo.ASCENDING)
        )
        # 也兼容 V2 foreshadow
        v2_pending = list(
            nf["foreshadow"]
            .find({"project_id": actual_project_id, "status": {"$ne": "resolved"}})
            .sort("chapter", pymongo.ASCENDING)
        )
        foreshadow_queue = []
        for fs in pending_foreshadows:
            urg = fs.get("urgency", "medium")
            foreshadow_queue.append({
                "id": fs.get("foreshadow_id"),
                "description": fs.get("description", ""),
                "setup_chapter": fs.get("setup_chapter"),
                "expected_callback": fs.get("expected_callback_chapter"),
                "urgency": urg,
                "arc_id": fs.get("arc_id"),
            })
        # merge V2
        seen_ids = {f["id"] for f in foreshadow_queue}
        for fs in v2_pending:
            fid = fs.get("foreshadow_id", fs.get("_id", ""))
            if str(fid) not in seen_ids:
                foreshadow_queue.append({
                    "id": str(fid),
                    "description": fs.get("description", ""),
                    "setup_chapter": fs.get("chapter", 0),
                    "expected_callback": None,
                    "urgency": "medium",
                    "arc_id": fs.get("arc_id"),
                })

        # ---- Step 9: Build must-remember list ----
        must_remember = []
        # 世界规则
        wb = nf["world_bible"].find_one({"project_id": actual_project_id})
        if wb:
            rules = wb.get("rules", wb.get("world_rules", []))
            if isinstance(rules, list):
                formatted = []
                for r in rules[:3]:
                    if isinstance(r, dict):
                        formatted.append(r.get("rule", r.get("name", str(r)[:60])))
                    elif isinstance(r, str):
                        formatted.append(r)
                if formatted:
                    must_remember.append(f"世界核心规则: {'; '.join(formatted)}")
            elif isinstance(rules, str) and rules:
                must_remember.append(f"世界规则: {rules[:200]}")

        # 核心角色定位
        for char in all_characters[:5]:
            name = char.get("name", "")
            role = char.get("role", char.get("title", ""))
            if name and role:
                must_remember.append(f"{name} — {role}")

        # ARC 核心冲突
        if current_arc and current_arc.get("core_conflict"):
            must_remember.append(f"当前ARC核心冲突: {current_arc['core_conflict']}")

        # ---- Step 10: Build forbidden list ----
        forbidden = [
            "不要在正文中新增世界规则（必须走 lore）",
            "不要修改角色核心设定（必须走 character）",
            "不要跳过时间线（必须按章节顺序写入）",
            "不要无故升级战力（必须走 power-control）",
            "不要在同一章内跳跃多人 POV（保持主线 POV）",
        ]

        # ---- Step 11: Assemble packet ----
        packet = {
            "project": {
                "id": actual_project_id,
                "title": project_title,
                "total_chapters": project.get("total_chapters", chapter),
                "total_words": project.get("total_words", 0),
                "genre": project.get("genre", "未知"),
                "current_chapter": chapter,
            },
            "current_arc": {
                "name": current_arc.get("name", "Main Story") if current_arc else "Main Story",
                "arc_id": current_arc.get("arc_id", "ARC-001") if current_arc else "ARC-001",
                "core_conflict": current_arc.get("core_conflict", "") if current_arc else "",
                "start_chapter": current_arc.get("start_chapter", 1) if current_arc else 1,
                "end_chapter": current_arc.get("end_chapter", 999) if current_arc else 999,
            },
            "recent_summary": recent_summary,
            "active_characters": active_characters,
            "character_states": character_states,
            "world_state": world_state,
            "foreshadow_queue": foreshadow_queue[:20],  # 最多 20 条最紧急的
            "must_remember": must_remember[:15],
            "forbidden": forbidden,
            "build_stats": {
                "total_characters": len(all_characters),
                "active_characters": len(active_characters),
                "pending_foreshadows": len(foreshadow_queue),
                "recent_chapters": len(recent_chapters),
                "built_at": datetime.datetime.utcnow().isoformat(),
            },
        }

        return packet
    finally:
        client.close()


def main():
    if len(sys.argv) < 2:
        print("用法: python3 build-context-packet.py <project_id> [chapter]")
        print("示例: python3 build-context-packet.py '诡异游戏：我的规则别人看不见'")
        print("示例: python3 build-context-packet.py proj_gui-yi-you-xi_d3acfcdd 52")
        sys.exit(1)

    project_id = sys.argv[1]
    chapter = int(sys.argv[2]) if len(sys.argv) > 2 else None

    packet = build_context_packet(project_id, chapter)
    print(json.dumps(packet, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
