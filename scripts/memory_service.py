#!/usr/bin/env python3
"""
起点小说工厂 · MongoDB 数据服务层
所有 Agent 的持久化读写都经过此模块。
禁止 Agent 直接在 prompt 里操作 MongoDB。
"""

import uuid
import datetime
from typing import Optional, Dict, List, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/"
DB_NAME = "novel_qidian"


class MemoryService:
    """MongoDB 数据访问层。单例模式，全局复用连接。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        self.db = self.client[DB_NAME]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """创建必要索引（幂等，已存在则跳过）"""
        try:
            self.db.projects.create_index("project_id", unique=True)
        except Exception:
            pass
        try:
            self.db.characters.create_index([("project_id", 1), ("character_id", 1)])
        except Exception:
            pass
        try:
            self.db.arcs.create_index([("project_id", 1), ("arc_id", 1)])
        except Exception:
            pass
        try:
            self.db.timeline.create_index([("project_id", 1), ("chapter", 1)])
        except Exception:
            pass
        try:
            self.db.foreshadows.create_index([("project_id", 1), ("status", 1)])
        except Exception:
            pass
        try:
            self.db.chapters.create_index([("project_id", 1), ("chapter", 1)])
        except Exception:
            pass
        try:
            self.db.kanban_cards.create_index([("project_id", 1), ("status", 1)])
        except Exception:
            pass
        try:
            self.db.kanban_cards.create_index([("project_id", 1), ("priority", DESCENDING)])
        except Exception:
            pass
        try:
            self.db.agent_logs.create_index([("project_id", 1), ("created_at", DESCENDING)])
        except Exception:
            pass

    # ============================================================
    # 项目
    # ============================================================
    def create_project(self, title: str, genre: str, target_words: int = 5_000_000) -> str:
        project_id = str(uuid.uuid4())[:8]
        now = datetime.datetime.utcnow().isoformat()
        self.db.projects.insert_one({
            "project_id": project_id,
            "title": title,
            "genre": genre,
            "platform": "起点中文网",
            "target_words": target_words,
            "current_words": 0,
            "current_arc": 1,
            "current_chapter": 0,
            "status": "planning",
            "created_at": now,
            "updated_at": now,
        })
        return project_id

    def get_project(self, project_id: str) -> Optional[Dict]:
        return self.db.projects.find_one({"project_id": project_id})

    def update_project(self, project_id: str, data: Dict):
        data["updated_at"] = datetime.datetime.utcnow().isoformat()
        self.db.projects.update_one({"project_id": project_id}, {"$set": data})

    # ============================================================
    # 世界观
    # ============================================================
    def get_world_bible(self, project_id: str) -> Optional[Dict]:
        return self.db.world_bible.find_one({"project_id": project_id})

    def upsert_world_bible(self, project_id: str, data: Dict):
        self.db.world_bible.update_one(
            {"project_id": project_id}, {"$set": data}, upsert=True
        )

    # ============================================================
    # 角色
    # ============================================================
    def create_character(self, project_id: str, data: Dict) -> str:
        cid = str(uuid.uuid4())[:8]
        data["project_id"] = project_id
        data["character_id"] = cid
        data["created_at"] = datetime.datetime.utcnow().isoformat()
        self.db.characters.insert_one(data)
        return cid

    def get_characters(self, project_id: str) -> List[Dict]:
        return list(self.db.characters.find({"project_id": project_id}, {"_id": 0}))

    def get_character(self, project_id: str, character_id: str) -> Optional[Dict]:
        return self.db.characters.find_one(
            {"project_id": project_id, "character_id": character_id}, {"_id": 0}
        )

    def update_character(self, project_id: str, character_id: str, data: Dict):
        self.db.characters.update_one(
            {"project_id": project_id, "character_id": character_id}, {"$set": data}
        )

    # ============================================================
    # ARC
    # ============================================================
    def create_arc(self, project_id: str, data: Dict) -> str:
        aid = str(uuid.uuid4())[:8]
        data["project_id"] = project_id
        data["arc_id"] = aid
        data["created_at"] = datetime.datetime.utcnow().isoformat()
        self.db.arcs.insert_one(data)
        return aid

    def get_arcs(self, project_id: str) -> List[Dict]:
        return list(self.db.arcs.find({"project_id": project_id}, {"_id": 0}))

    def get_arc(self, project_id: str, arc_id: str) -> Optional[Dict]:
        return self.db.arcs.find_one(
            {"project_id": project_id, "arc_id": arc_id}, {"_id": 0}
        )

    # ============================================================
    # 章节
    # ============================================================
    def create_chapter(self, project_id: str, data: Dict) -> str:
        data["project_id"] = project_id
        data["created_at"] = datetime.datetime.utcnow().isoformat()
        self.db.chapters.insert_one(data)
        return str(data.get("chapter", ""))

    def get_chapter(self, project_id: str, chapter: int) -> Optional[Dict]:
        return self.db.chapters.find_one(
            {"project_id": project_id, "chapter": chapter}, {"_id": 0}
        )

    def get_recent_chapters(self, project_id: str, limit: int = 5) -> List[Dict]:
        return list(
            self.db.chapters.find({"project_id": project_id}, {"_id": 0})
            .sort("chapter", DESCENDING)
            .limit(limit)
        )

    def get_chapter_count(self, project_id: str) -> int:
        return self.db.chapters.count_documents({"project_id": project_id})

    # ============================================================
    # 伏笔
    # ============================================================
    def create_foreshadow(self, project_id: str, data: Dict) -> str:
        fid = str(uuid.uuid4())[:8]
        data["project_id"] = project_id
        data["foreshadow_id"] = fid
        data["status"] = "active"
        data["created_at"] = datetime.datetime.utcnow().isoformat()
        self.db.foreshadows.insert_one(data)
        return fid

    def get_active_foreshadows(self, project_id: str) -> List[Dict]:
        return list(
            self.db.foreshadows.find(
                {"project_id": project_id, "status": "active"}, {"_id": 0}
            )
        )

    def resolve_foreshadow(self, project_id: str, foreshadow_id: str, payoff_chapter: int):
        self.db.foreshadows.update_one(
            {"project_id": project_id, "foreshadow_id": foreshadow_id},
            {"$set": {"status": "resolved", "payoff_chapter": payoff_chapter}},
        )

    # ============================================================
    # 时间线
    # ============================================================
    def add_timeline_event(self, project_id: str, chapter: int, event: str,
                           affected: List[str] = None, world_changes: List[str] = None):
        self.db.timeline.insert_one({
            "project_id": project_id,
            "chapter": chapter,
            "event": event,
            "date": datetime.datetime.utcnow().isoformat(),
            "affected_characters": affected or [],
            "world_changes": world_changes or [],
        })

    # ============================================================
    # 势力
    # ============================================================
    def create_faction(self, project_id: str, data: Dict) -> str:
        fid = str(uuid.uuid4())[:8]
        data["project_id"] = project_id
        data["faction_id"] = fid
        self.db.factions.insert_one(data)
        return fid

    def get_factions(self, project_id: str) -> List[Dict]:
        return list(self.db.factions.find({"project_id": project_id}, {"_id": 0}))

    # ============================================================
    # 修炼体系
    # ============================================================
    def upsert_cultivation_system(self, project_id: str, data: Dict):
        self.db.cultivation_system.update_one(
            {"project_id": project_id}, {"$set": data}, upsert=True
        )

    def get_cultivation_system(self, project_id: str) -> Optional[Dict]:
        return self.db.cultivation_system.find_one({"project_id": project_id}, {"_id": 0})

    # ============================================================
    # Kanban 看板卡片
    # ============================================================
    def create_kanban_card(self, project_id: str, card_type: str, priority: int = 3,
                           input_data: Dict = None, dependencies: List[str] = None) -> str:
        cid = f"card_{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.utcnow().isoformat()
        self.db.kanban_cards.insert_one({
            "project_id": project_id,
            "card_id": cid,
            "card_type": card_type,
            "status": "pending",
            "priority": priority,
            "agent_type": self._card_to_agent(card_type),
            "input_summary": str(input_data)[:200] if input_data else "",
            "input_data": input_data or {},
            "output_data": {},
            "dependencies": dependencies or [],
            "retry_count": 0,
            "max_retries": 3,
            "created_at": now,
        })
        return cid

    def get_next_pending_card(self, project_id: str) -> Optional[Dict]:
        """取下一张待处理卡片（按优先级降序 + 创建时间升序）"""
        return self.db.kanban_cards.find_one(
            {"project_id": project_id, "status": "pending"},
            sort=[("priority", DESCENDING), ("created_at", ASCENDING)],
        )

    def get_pending_queue(self, project_id: str) -> List[Dict]:
        return list(
            self.db.kanban_cards.find({"project_id": project_id, "status": "pending"}, {"_id": 0})
            .sort([("priority", DESCENDING), ("created_at", ASCENDING)])
        )

    def update_card_status(self, project_id: str, card_id: str, status: str,
                           output_data: Dict = None, error_msg: str = None):
        update = {"status": status}
        if status == "in_progress":
            update["assigned_at"] = datetime.datetime.utcnow().isoformat()
        if status in ("completed", "rejected", "blocked"):
            update["completed_at"] = datetime.datetime.utcnow().isoformat()
        if output_data:
            update["output_data"] = output_data
        if error_msg:
            update["error_msg"] = error_msg
        self.db.kanban_cards.update_one(
            {"project_id": project_id, "card_id": card_id}, {"$set": update}
        )

    def get_card(self, project_id: str, card_id: str) -> Optional[Dict]:
        return self.db.kanban_cards.find_one(
            {"project_id": project_id, "card_id": card_id}, {"_id": 0}
        )

    def get_cards_by_status(self, project_id: str, status: str) -> List[Dict]:
        return list(
            self.db.kanban_cards.find(
                {"project_id": project_id, "status": status}, {"_id": 0}
            )
        )

    def get_kanban_stats(self, project_id: str) -> Dict:
        """看板统计"""
        pipeline = [
            {"$match": {"project_id": project_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        result = {}
        for item in self.db.kanban_cards.aggregate(pipeline):
            result[item["_id"]] = item["count"]
        return result

    # ============================================================
    # Agent 日志
    # ============================================================
    def log_agent_run(self, project_id: str, agent_type: str, card_id: str,
                      status: str, output_summary: str = "", error: str = ""):
        self.db.agent_logs.insert_one({
            "project_id": project_id,
            "agent_type": agent_type,
            "card_id": card_id,
            "status": status,
            "output_summary": output_summary[:500],
            "error": error[:500],
            "created_at": datetime.datetime.utcnow().isoformat(),
        })

    # ============================================================
    # 工具方法
    # ============================================================
    def _card_to_agent(self, card_type: str) -> str:
        mapping = {
            "research": "orchestrator",
            "theme_planning": "orchestrator",
            "world_building": "world-builder",
            "character_design": "character-designer",
            "arc_planning": "arc-planner",
            "outline": "arc-planner",
            "draft": "draft-writer",
            "editing": "editor",
            "review": "reviewer",
            "publishing": "orchestrator",
        }
        return mapping.get(card_type, "orchestrator")

    def close(self):
        self.client.close()


# 便捷函数
def get_memory() -> MemoryService:
    return MemoryService()
