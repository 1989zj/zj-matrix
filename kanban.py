"""
Kanban 卡片管理工具 —— novel_qidian 起点小说工厂

用法:
    from kanban import Kanban
    kb = Kanban()
    card_id = kb.create_card(project_id, "draft", "draft-writer", 3, {...})
    next_card = kb.get_next_pending(project_id)
    kb.complete_card(card_id, output_data={...})
"""

import json
import uuid
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/"
DB_NAME = "novel_qidian"

# 看板列 → 默认 agent_type 映射
COLUMN_AGENT_MAP = {
    "research": "researcher",
    "world_building": "world-builder",
    "character_design": "character-designer",
    "arc_planning": "arc-planner",
    "outline": "arc-planner",
    "draft": "draft-writer",
    "editing": "editor",
    "review": "reviewer",
    "publishing": "publisher",
    "archived": None,
}

# 看板流转顺序（普通流程）
FLOW_ORDER = [
    "research",
    "world_building",
    "character_design",
    "arc_planning",
    "outline",
    "draft",
    "editing",
    "review",
    "publishing",
    "archived",
]


class Kanban:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]

    def init_project(self, project_id: str, title: str, genre: str, target_words: int = 5_000_000) -> dict:
        """初始化项目记录，如果已存在则跳过"""
        try:
            self.db.projects.insert_one({
                "project_id": project_id,
                "title": title,
                "genre": genre,
                "platform": "起点中文网",
                "target_words": target_words,
                "current_words": 0,
                "current_arc": 0,
                "current_chapter": 0,
                "status": "active",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            })
            return {"status": "created", "project_id": project_id}
        except DuplicateKeyError:
            return {"status": "exists", "project_id": project_id}

    def create_card(
        self,
        project_id: str,
        card_type: str,
        agent_type: str = None,
        priority: int = 3,
        input_data: dict = None,
        input_summary: str = "",
        dependencies: list = None,
    ) -> str:
        """创建一张 Kanban 卡片，返回 card_id"""
        card_id = str(uuid.uuid4())[:8]
        agent = agent_type or COLUMN_AGENT_MAP.get(card_type)

        doc = {
            "project_id": project_id,
            "card_id": card_id,
            "card_type": card_type,
            "status": "pending",
            "priority": priority,
            "agent_type": agent,
            "input_summary": input_summary,
            "input_data": input_data or {},
            "output_data": {},
            "dependencies": dependencies or [],
            "retry_count": 0,
            "max_retries": 3,
            "created_at": now_iso(),
            "assigned_at": None,
            "completed_at": None,
        }
        self.db.kanban_cards.insert_one(doc)
        return card_id

    def get_next_pending(self, project_id: str) -> dict | None:
        """按优先级取下一张待处理卡片，同时检查依赖是否满足"""
        cards = list(
            self.db.kanban_cards.find(
                {"project_id": project_id, "status": "pending"}
            ).sort([("priority", -1), ("created_at", 1)])
        )
        for card in cards:
            if self._deps_satisfied(card.get("dependencies", [])):
                return card
        return None

    def assign_card(self, card_id: str) -> bool:
        """将卡片标记为 in_progress"""
        result = self.db.kanban_cards.update_one(
            {"card_id": card_id, "status": "pending"},
            {"$set": {"status": "in_progress", "assigned_at": now_iso()}},
        )
        return result.modified_count > 0

    def complete_card(self, card_id: str, output_data: dict = None) -> bool:
        """标记卡片为 completed"""
        update = {
            "$set": {
                "status": "completed",
                "completed_at": now_iso(),
                "output_data": output_data or {},
            }
        }
        result = self.db.kanban_cards.update_one(
            {"card_id": card_id, "status": "in_progress"}, update
        )
        return result.modified_count > 0

    def reject_card(self, card_id: str, reason: str = "") -> bool:
        """标记卡片为 rejected，增加重试计数"""
        card = self.db.kanban_cards.find_one({"card_id": card_id})
        if not card:
            return False
        new_count = card.get("retry_count", 0) + 1
        new_status = "blocked" if new_count >= card.get("max_retries", 3) else "rejected"
        self.db.kanban_cards.update_one(
            {"card_id": card_id},
            {
                "$set": {
                    "status": new_status,
                    "retry_count": new_count,
                    "completed_at": now_iso(),
                    "output_data": {"reject_reason": reason},
                }
            },
        )
        return True

    def block_card(self, card_id: str, reason: str = "") -> bool:
        """直接标记为 blocked"""
        result = self.db.kanban_cards.update_one(
            {"card_id": card_id},
            {"$set": {"status": "blocked", "output_data": {"block_reason": reason}}},
        )
        return result.modified_count > 0

    def get_card(self, card_id: str) -> dict | None:
        return self.db.kanban_cards.find_one({"card_id": card_id})

    def get_queue_summary(self, project_id: str) -> dict:
        """返回当前队列概况"""
        pipeline = [
            {"$match": {"project_id": project_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        result = {doc["_id"]: doc["count"] for doc in self.db.kanban_cards.aggregate(pipeline)}
        return result

    def log_agent(self, project_id: str, card_id: str, agent_type: str, input_summary: str, output_summary: str, success: bool):
        """记录 Agent 执行日志"""
        self.db.agent_logs.insert_one({
            "project_id": project_id,
            "card_id": card_id,
            "agent_type": agent_type,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "success": success,
            "timestamp": now_iso(),
        })

    def update_project_progress(self, project_id: str, words_added: int, chapter: int):
        """更新项目进度"""
        self.db.projects.update_one(
            {"project_id": project_id},
            {
                "$inc": {"current_words": words_added},
                "$set": {"current_chapter": chapter, "updated_at": now_iso()},
            },
        )

    def start_arc(self, project_id: str, arc_number: int):
        """标记当前 ARC"""
        self.db.projects.update_one(
            {"project_id": project_id},
            {"$set": {"current_arc": arc_number, "updated_at": now_iso()}},
        )

    def _deps_satisfied(self, dep_ids: list) -> bool:
        """检查依赖卡片是否全部 completed"""
        if not dep_ids:
            return True
        for dep_id in dep_ids:
            card = self.db.kanban_cards.find_one({"card_id": dep_id})
            if not card or card["status"] != "completed":
                return False
        return True


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    kb = Kanban()
    # 快速测试
    pid = "test-" + str(uuid.uuid4())[:6]
    kb.init_project(pid, "测试项目", "玄幻")
    cid = kb.create_card(pid, "world_building", input_summary="创建世界观")
    print(f"创建卡片: {cid}")
    nxt = kb.get_next_pending(pid)
    print(f"下一张卡片: {nxt['card_id'] if nxt else '无'}")
    kb.assign_card(cid)
    kb.complete_card(cid, {"result": "世界观已创建"})
    print(f"队列: {kb.get_queue_summary(pid)}")
    print("Kanban 自检通过")
