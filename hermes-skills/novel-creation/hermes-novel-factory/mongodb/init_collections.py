#!/usr/bin/env python3
"""Phase 1: 创建 V3 新增的 7 个 MongoDB collection + 索引"""
import pymongo
import sys

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"

client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client["novel_factory"]

# ============================================================
# V3 新增 collections
# ============================================================
V3_COLLECTIONS = {
    "character_states": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["project_id", "character", "chapter", "updated_at"],
                "properties": {
                    "project_id": {"bsonType": "string", "description": "项目ID"},
                    "character": {"bsonType": "string", "description": "角色名"},
                    "chapter": {"bsonType": "int", "description": "状态对应的章节号"},
                    "emotion": {"bsonType": "string", "description": "当前情绪"},
                    "wealth": {"bsonType": ["int", "double"], "description": "财富值"},
                    "combat_level": {"bsonType": "int", "description": "战力等级"},
                    "health": {"bsonType": "string", "description": "健康状态"},
                    "location": {"bsonType": "string", "description": "当前位置"},
                    "relationships": {
                        "bsonType": "object",
                        "description": "角色关系 {target: trust_level}",
                    },
                    "memory": {
                        "bsonType": "array",
                        "items": {"bsonType": "string"},
                        "description": "近期记忆线索",
                    },
                    "updated_at": {"bsonType": "date", "description": "更新时间"},
                },
            }
        }
    },
    "world_state": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["project_id", "chapter", "updated_at"],
                "properties": {
                    "project_id": {"bsonType": "string"},
                    "chapter": {"bsonType": "int"},
                    "economy": {
                        "bsonType": "object",
                        "description": "经济状态 {level, trend, description}",
                        "properties": {
                            "level": {"bsonType": "string"},
                            "trend": {"bsonType": "string"},
                        },
                    },
                    "public_opinion": {
                        "bsonType": "object",
                        "description": "舆论状态 {toward_mc, key_events}",
                    },
                    "power_balance": {
                        "bsonType": "object",
                        "description": "势力平衡 {factions, dominance}",
                    },
                    "city_control": {
                        "bsonType": "object",
                        "description": "城市控制状态",
                    },
                    "active_crises": {
                        "bsonType": "array",
                        "items": {"bsonType": "string"},
                        "description": "进行中的危机/威胁",
                    },
                    "updated_at": {"bsonType": "date"},
                },
            }
        }
    },
    "foreshadow_queue": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["project_id", "foreshadow_id", "description", "setup_chapter"],
                "properties": {
                    "project_id": {"bsonType": "string"},
                    "foreshadow_id": {"bsonType": "string", "description": "唯一ID FS_001"},
                    "description": {"bsonType": "string", "description": "伏笔内容"},
                    "setup_chapter": {"bsonType": "int", "description": "埋设章节"},
                    "expected_callback_chapter": {
                        "bsonType": ["int", "null"],
                        "description": "预计回收章节",
                    },
                    "deadline_type": {
                        "bsonType": "string",
                        "enum": ["soft", "hard"],
                        "description": "deadline类型",
                    },
                    "resolved": {"bsonType": "bool"},
                    "resolved_chapter": {"bsonType": ["int", "null"]},
                    "urgency": {
                        "bsonType": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "arc_id": {"bsonType": ["string", "null"]},
                    "created_at": {"bsonType": "date"},
                    "updated_at": {"bsonType": "date"},
                },
            }
        }
    },
    "event_log": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["project_id", "event_type", "chapter", "timestamp"],
                "properties": {
                    "project_id": {"bsonType": "string"},
                    "event_type": {
                        "bsonType": "string",
                        "enum": [
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
                            "resume_session",
                            "error",
                        ],
                    },
                    "chapter": {"bsonType": "int"},
                    "data": {"bsonType": "object", "description": "事件附加数据"},
                    "version": {"bsonType": "int", "description": "事件版本号（递增）"},
                    "timestamp": {"bsonType": "date"},
                },
            }
        }
    },
    "snapshot_store": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["project_id", "chapter", "snapshot", "generated_at"],
                "properties": {
                    "project_id": {"bsonType": "string"},
                    "chapter": {"bsonType": "int"},
                    "snapshot": {
                        "bsonType": "object",
                        "description": "完整状态快照",
                    },
                    "version": {"bsonType": "int"},
                    "generated_at": {"bsonType": "date"},
                },
            }
        }
    },
    "arc_plans": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["project_id", "arc_id", "name", "level"],
                "properties": {
                    "project_id": {"bsonType": "string"},
                    "arc_id": {"bsonType": "string"},
                    "name": {"bsonType": "string"},
                    "level": {
                        "bsonType": "string",
                        "enum": ["world", "phase", "beat", "chapter"],
                    },
                    "parent_arc": {"bsonType": ["string", "null"]},
                    "start_chapter": {"bsonType": "int"},
                    "end_chapter": {"bsonType": "int"},
                    "core_conflict": {"bsonType": "string"},
                    "target_emotion": {"bsonType": "string"},
                    "key_scenes": {
                        "bsonType": "array",
                        "items": {"bsonType": "string"},
                    },
                    "status": {
                        "bsonType": "string",
                        "enum": ["planned", "active", "completed", "paused"],
                    },
                    "created_at": {"bsonType": "date"},
                    "updated_at": {"bsonType": "date"},
                },
            }
        }
    },
    "anti_fatigue": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["project_id", "chapter", "generated_at"],
                "properties": {
                    "project_id": {"bsonType": "string"},
                    "chapter": {"bsonType": "int"},
                    "fatigue_level": {
                        "bsonType": "string",
                        "enum": ["green", "yellow", "red"],
                    },
                    "scores": {
                        "bsonType": "object",
                        "description": "各维度疲劳分数 {dialogue, plot, emotion, ...}",
                    },
                    "alerts": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "object",
                            "properties": {
                                "type": {"bsonType": "string"},
                                "message": {"bsonType": "string"},
                                "suggestion": {"bsonType": "string"},
                            },
                        },
                    },
                    "generated_at": {"bsonType": "date"},
                },
            }
        }
    },
}

def init_collections():
    existing = set(db.list_collection_names())
    created = 0
    skipped = 0

    for name, spec in V3_COLLECTIONS.items():
        if name in existing:
            print(f"  ⏭️  {name} — already exists")
            skipped += 1
            continue
        try:
            db.create_collection(name, validator=spec.get("validator"))
            print(f"  ✅  {name} — created")
            created += 1
        except Exception as e:
            print(f"  ❌  {name} — failed: {e}")

    print(f"\n结果: {created} created, {skipped} skipped")
    return created

def create_indexes():
    """Create essential indexes for V3 collections"""
    indexes = {
        "character_states": [
            [("project_id", pymongo.ASCENDING), ("character", pymongo.ASCENDING), ("chapter", pymongo.DESCENDING)],
            [("project_id", pymongo.ASCENDING), ("chapter", pymongo.DESCENDING)],
        ],
        "world_state": [
            [("project_id", pymongo.ASCENDING), ("chapter", pymongo.DESCENDING)],
        ],
        "foreshadow_queue": [
            [("project_id", pymongo.ASCENDING), ("resolved", pymongo.ASCENDING), ("expected_callback_chapter", pymongo.ASCENDING)],
            [("project_id", pymongo.ASCENDING), ("urgency", pymongo.ASCENDING)],
        ],
        "event_log": [
            [("project_id", pymongo.ASCENDING), ("version", pymongo.DESCENDING)],
            [("project_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)],
            [("project_id", pymongo.ASCENDING), ("event_type", pymongo.ASCENDING)],
        ],
        "snapshot_store": [
            [("project_id", pymongo.ASCENDING), ("chapter", pymongo.DESCENDING)],
            [("project_id", pymongo.ASCENDING), ("version", pymongo.DESCENDING)],
        ],
        "arc_plans": [
            [("project_id", pymongo.ASCENDING), ("arc_id", pymongo.ASCENDING)],
            [("project_id", pymongo.ASCENDING), ("level", pymongo.ASCENDING), ("start_chapter", pymongo.ASCENDING)],
        ],
        "anti_fatigue": [
            [("project_id", pymongo.ASCENDING), ("chapter", pymongo.DESCENDING)],
        ],
    }

    for col, idx_list in indexes.items():
        try:
            collection = db[col]
            for idx in idx_list:
                name = "_".join(f"{k}_{d}" for k, d in idx)
                collection.create_index(idx, name=name, background=True)
            print(f"  ✅  {col} indexes created")
        except Exception as e:
            print(f"  ❌  {col} indexes failed: {e}")

if __name__ == "__main__":
    print("=== V3 MongoDB Collections Init ===")
    c = init_collections()
    if c > 0 or True:  # always create indexes
        print("\n=== Creating Indexes ===")
        create_indexes()
    print("\nDone.")
