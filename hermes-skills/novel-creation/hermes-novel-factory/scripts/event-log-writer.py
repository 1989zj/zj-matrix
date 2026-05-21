#!/usr/bin/env python3
"""
event-log-writer.py — V3 事件溯源日志系统

作用: 所有 novel_factory 写操作的权威记录，支持 rollback/replay/debug。
调用:
  python3 event-log-writer.py log <project_id> <event_type> <chapter> [--data '{"key":"val"}']
  python3 event-log-writer.py list <project_id> [--limit 50]
  python3 event-log-writer.py replay <project_id> [--from 1] [--to 100]

设计原则:
- append-only: 一旦写入不可修改
- 版本号递增: 每个 project 独立计数
- 轻量级: 不存储完整内容，只存事件类型和关键元数据
"""

import json
import sys
import datetime
import argparse

import pymongo

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"

VALID_EVENTS = {
    "chapter_started",
    "chapter_generated",
    "chapter_validated",
    "editor_completed",
    "world_updated",
    "character_states_updated",
    "foreshadow_created",
    "foreshadow_resolved",
    "snapshot_saved",
    "arc_completed",
    "project_created",
    "project_refreshed",
    "resume_session",
    "error",
}


def connect():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client, client["novel_factory"]


def get_next_version(client, project_id: str) -> int:
    """用 find_one_and_update 原子递增版本号"""
    db = client["novel_factory"]
    counter = db["event_counters"].find_one_and_update(
        {"project_id": project_id},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=pymongo.ReturnDocument.AFTER,
    )
    return counter["seq"]


def log_event(project_id: str, event_type: str, chapter: int, data: dict = None):
    """
    记录一个事件到 event_log collection。

    Args:
        project_id: 项目 ID
        event_type: 事件类型（必须为 VALID_EVENTS 之一）
        chapter: 相关章节号
        data: 附加数据（可选）

    Returns:
        dict with status and event_id
    """
    if event_type not in VALID_EVENTS:
        return {"status": "error", "message": f"Invalid event type: {event_type}. Valid: {', '.join(VALID_EVENTS)}"}

    client, db = connect()
    try:
        version = get_next_version(client, project_id)
        now = datetime.datetime.utcnow()

        doc = {
            "project_id": project_id,
            "event_type": event_type,
            "chapter": chapter,
            "version": version,
            "timestamp": now,
            "data": data or {},
        }

        result = db["event_log"].insert_one(doc)
        
        # 每 100 个事件触发 snapshot 提醒
        if version % 100 == 0:
            db["snapshot_store"].update_one(
                {"project_id": project_id},
                {"$set": {
                    "snapshot_pending": True, 
                    "events_since_snapshot": version,
                }},
                upsert=True,
            )

        return {
            "status": "ok",
            "event_id": str(result.inserted_id),
            "version": version,
            "event_type": event_type,
            "chapter": chapter,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        client.close()


def list_events(project_id: str, limit: int = 50, event_type: str = None):
    """列出项目的事件历史"""
    client, db = connect()
    try:
        query = {"project_id": project_id}
        if event_type:
            query["event_type"] = event_type

        events = list(
            db["event_log"]
            .find(query)
            .sort("version", pymongo.DESCENDING)
            .limit(limit)
        )

        results = []
        for e in events:
            results.append({
                "version": e.get("version"),
                "event_type": e.get("event_type"),
                "chapter": e.get("chapter"),
                "timestamp": e.get("timestamp").isoformat() if e.get("timestamp") else None,
                "data_summary": {k: v for k, v in e.get("data", {}).items() if k != "content"}
                if e.get("data") else {},
            })

        return {"status": "ok", "project_id": project_id, "events": results, "total": len(results)}
    finally:
        client.close()


def replay_events(project_id: str, start_version: int = 1, end_version: int = None):
    """重放事件序列（用于 debug / 状态重建）"""
    client, db = connect()
    try:
        query = {
            "project_id": project_id,
            "version": {"$gte": start_version},
        }
        if end_version:
            query["version"]["$lte"] = end_version

        events = list(
            db["event_log"]
            .find(query)
            .sort("version", pymongo.ASCENDING)
        )

        # 按事件类型分组统计
        summary = {}
        for e in events:
            et = e.get("event_type", "unknown")
            summary[et] = summary.get(et, 0) + 1

        return {
            "status": "ok",
            "project_id": project_id,
            "version_range": f"{start_version}–{end_version or 'latest'}",
            "total_events": len(events),
            "summary": summary,
            "events": [
                {
                    "version": e.get("version"),
                    "event_type": e.get("event_type"),
                    "chapter": e.get("chapter"),
                    "timestamp": e.get("timestamp").isoformat() if e.get("timestamp") else None,
                }
                for e in events[:200]  # cap output
            ],
        }
    finally:
        client.close()


def get_project_version(project_id: str) -> int:
    """获取项目当前事件版本号"""
    client, db = connect()
    try:
        counter = db["event_counters"].find_one({"project_id": project_id})
        return counter["seq"] if counter else 0
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description="V3 Event Log System")
    sub = parser.add_subparsers(dest="command", required=True)

    # log
    log_p = sub.add_parser("log", help="Write an event")
    log_p.add_argument("project_id", help="Project ID")
    log_p.add_argument("event_type", choices=list(VALID_EVENTS), help="Event type")
    log_p.add_argument("chapter", type=int, help="Chapter number")
    log_p.add_argument("--data", type=str, default="{}", help="JSON data string")
    log_p.add_argument("--stdin", action="store_true", help="Read data from stdin")

    # list
    list_p = sub.add_parser("list", help="List events")
    list_p.add_argument("project_id", help="Project ID")
    list_p.add_argument("--limit", type=int, default=50)
    list_p.add_argument("--type", dest="event_type", help="Filter by event type")

    # replay
    replay_p = sub.add_parser("replay", help="Replay events")
    replay_p.add_argument("project_id", help="Project ID")
    replay_p.add_argument("--from", dest="from_ver", type=int, default=1)
    replay_p.add_argument("--to", dest="to_ver", type=int, default=None)

    # version
    ver_p = sub.add_parser("version", help="Get current event version")
    ver_p.add_argument("project_id", help="Project ID")

    args = parser.parse_args()

    if args.command == "log":
        data = {}
        if args.stdin:
            raw = sys.stdin.read()
            if raw.strip():
                data = json.loads(raw)
        else:
            data = json.loads(args.data)
        result = log_event(args.project_id, args.event_type, args.chapter, data)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "list":
        result = list_events(args.project_id, args.limit, args.event_type)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif args.command == "replay":
        result = replay_events(args.project_id, args.from_ver, args.to_ver)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif args.command == "version":
        v = get_project_version(args.project_id)
        print(json.dumps({"project_id": args.project_id, "version": v}, indent=2))


if __name__ == "__main__":
    main()
