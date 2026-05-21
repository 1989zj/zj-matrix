#!/usr/bin/env python3
"""
snapshot-manager.py — V3 状态快照系统

作用: 每章结束后保存完整状态快照，支持 continue 时从任意点恢复。
调用:
  python3 snapshot-manager.py save <project_id> <chapter>    # 保存当前快照
  python3 snapshot-manager.py load <project_id> [chapter]    # 恢复快照
  python3 snapshot-manager.py list <project_id>              # 列出所有快照

设计原则:
- 快照是「恢复点」而非「备份」—— 只存关键状态，不存全文
- 每 100 event 自动触发一次全量快照（event-log-writer 负责告警）
- 支持两种存储: MongoDB snapshot_store collection + 本地 JSON 文件
"""

import json
import sys
import os
import datetime
from pathlib import Path

import pymongo

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"
STORAGE_DIR = os.path.expanduser("~/.hermes/skills/content-creation/hermes-novel-factory/storage/snapshots")


def connect():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client, client["novel_factory"]


def collect_current_state(db, project_id: str, chapter: int) -> dict:
    """从所有 collection 收集当前状态并组装为 snapshot"""
    snapshot = {
        "project_id": project_id,
        "chapter": chapter,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "world_state": {},
        "character_states": {},
        "active_arcs": [],
        "foreshadow_queue": [],
        "timeline": [],
        "project_meta": {},
    }

    # World state
    ws = db["world_state"].find_one(
        {"project_id": project_id},
        sort=[("chapter", pymongo.DESCENDING)]
    )
    if ws:
        snapshot["world_state"] = {
            "economy": ws.get("economy"),
            "public_opinion": ws.get("public_opinion"),
            "power_balance": ws.get("power_balance"),
            "city_control": ws.get("city_control"),
            "active_crises": ws.get("active_crises", []),
        }

    # Character states
    char_states = list(
        db["character_states"]
        .find({"project_id": project_id})
        .sort("chapter", pymongo.DESCENDING)
    )
    seen = set()
    for cs in char_states:
        name = cs.get("character")
        if name and name not in seen:
            seen.add(name)
            snapshot["character_states"][name] = {
                "emotion": cs.get("emotion", "neutral"),
                "wealth": cs.get("wealth", 0),
                "combat_level": cs.get("combat_level", 1),
                "health": cs.get("health", "normal"),
                "location": cs.get("location", "unknown"),
            }

    # Active arcs
    active_arcs = list(
        db["arc_plans"]
        .find({"project_id": project_id, "status": "active"})
        .sort("start_chapter", pymongo.ASCENDING)
    )
    if not active_arcs:
        active_arcs = list(
            db["arc_plans"]
            .find({"project_id": project_id})
            .sort("start_chapter", pymongo.ASCENDING)
            .limit(1)
        )
    for arc in active_arcs:
        snapshot["active_arcs"].append({
            "arc_id": arc.get("arc_id"),
            "name": arc.get("name"),
            "level": arc.get("level"),
            "core_conflict": arc.get("core_conflict", ""),
            "start_chapter": arc.get("start_chapter"),
            "end_chapter": arc.get("end_chapter"),
            "status": arc.get("status", "active"),
        })

    # Foreshadow queue (unresolved + high urgency)
    pending = list(
        db["foreshadow_queue"]
        .find({"project_id": project_id, "resolved": False})
        .sort("urgency", pymongo.ASCENDING)
        .limit(30)
    )
    for fs in pending:
        snapshot["foreshadow_queue"].append({
            "id": fs.get("foreshadow_id"),
            "description": fs.get("description", ""),
            "setup_chapter": fs.get("setup_chapter", 0),
            "expected_callback": fs.get("expected_callback_chapter"),
            "urgency": fs.get("urgency", "medium"),
        })

    # Recent timeline events
    timeline_events = list(
        db["timeline"]
        .find({"project_id": project_id})
        .sort("chapter", pymongo.DESCENDING)
        .limit(10)
    )
    for ev in reversed(timeline_events):
        snapshot["timeline"].append({
            "chapter": ev.get("chapter"),
            "event": ev.get("event", ev.get("description", "")),
            "importance": ev.get("importance", 1),
        })

    # Project meta
    project = db["projects"].find_one({"project_id": project_id})
    if project:
        snapshot["project_meta"] = {
            "title": project.get("title", project.get("name", "")),
            "total_chapters": project.get("total_chapters", chapter),
            "total_words": project.get("total_words", 0),
            "current_arc": project.get("current_arc", ""),
        }

    return snapshot


def save_snapshot_mongodb(db, project_id: str, chapter: int, snapshot: dict):
    """保存快照到 MongoDB snapshot_store collection"""
    doc = {
        "project_id": project_id,
        "chapter": chapter,
        "snapshot": snapshot,
        "version": chapter,  # 用章节号做版本号
        "generated_at": datetime.datetime.utcnow(),
    }
    result = db["snapshot_store"].replace_one(
        {"project_id": project_id, "chapter": chapter},
        doc,
        upsert=True,
    )
    return result.upserted_id or result.modified_count


def save_snapshot_local(project_id: str, chapter: int, snapshot: dict):
    """保存快照到本地 JSON 文件"""
    storage_dir = Path(STORAGE_DIR)
    storage_dir.mkdir(parents=True, exist_ok=True)
    # sanitize project_id for filename
    safe_name = project_id.replace("/", "_").replace(":", "_")[:60]
    filename = storage_dir / f"snapshot_{safe_name}_ch{chapter:04d}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)
    return str(filename)


def cmd_save(project_id: str, chapter: int):
    """保存快照（MongoDB + 本地双重）"""
    client, db = connect()
    try:
        print(f"收集状态: project={project_id}, chapter={chapter}")
        snapshot = collect_current_state(db, project_id, chapter)

        # MongoDB
        mb_id = save_snapshot_mongodb(db, project_id, chapter, snapshot)
        # Local
        local_path = save_snapshot_local(project_id, chapter, snapshot)

        print(f"✅ MongoDB snapshot saved (chapter={chapter})")
        print(f"✅ Local snapshot saved: {local_path}")

        return {
            "status": "ok",
            "chapter": chapter,
            "mongodb_saved": True,
            "local_path": local_path,
        }
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        client.close()


def cmd_load(project_id: str, chapter: int = None):
    """从最新（或指定章节）恢复快照"""
    client, db = connect()
    try:
        query = {"project_id": project_id}
        sort = [("chapter", pymongo.DESCENDING)]

        if chapter:
            # 找最近的 <= 目标章节的快照
            query["chapter"] = {"$lte": chapter}
            sort = [("chapter", pymongo.DESCENDING)]

        doc = db["snapshot_store"].find_one(query, sort=sort)
        if not doc:
            return {"status": "error", "message": f"No snapshot found for {project_id}"}

        snapshot = doc.get("snapshot", {})
        if not snapshot:
            return {"status": "error", "message": "Snapshot data is empty"}

        result = {
            "status": "ok",
            "project_id": project_id,
            "snapshot_chapter": doc["chapter"],
            "snapshot": {
                "world_state": snapshot.get("world_state", {}),
                "character_states": snapshot.get("character_states", {}),
                "active_arcs": snapshot.get("active_arcs", []),
                "foreshadow_queue": snapshot.get("foreshadow_queue", []),
                "timeline": snapshot.get("timeline", []),
                "project_meta": snapshot.get("project_meta", {}),
            },
            "source": "mongodb",
        }

        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        client.close()


def cmd_list(project_id: str):
    """列出项目的所有快照"""
    client, db = connect()
    try:
        snapshots = list(
            db["snapshot_store"]
            .find({"project_id": project_id})
            .sort("chapter", pymongo.DESCENDING)
            .limit(50)
        )
        results = []
        for s in snapshots:
            results.append({
                "chapter": s.get("chapter"),
                "version": s.get("version"),
                "generated_at": s.get("generated_at").isoformat() if s.get("generated_at") else None,
                "snapshot_size": len(json.dumps(s.get("snapshot", {}), default=str)),
            })
        return {"status": "ok", "snapshots": results, "total": len(results)}
    finally:
        client.close()


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  python3 snapshot-manager.py save <project_id> <chapter>")
        print("  python3 snapshot-manager.py load <project_id> [chapter]")
        print("  python3 snapshot-manager.py list <project_id>")
        sys.exit(1)

    cmd = sys.argv[1]
    project_id = sys.argv[2]

    if cmd == "save":
        if len(sys.argv) < 4:
            print("错误: save 需要 chapter 参数")
            sys.exit(1)
        chapter = int(sys.argv[3])
        result = cmd_save(project_id, chapter)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif cmd == "load":
        chapter = int(sys.argv[3]) if len(sys.argv) > 3 else None
        result = cmd_load(project_id, chapter)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif cmd == "list":
        result = cmd_list(project_id)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
