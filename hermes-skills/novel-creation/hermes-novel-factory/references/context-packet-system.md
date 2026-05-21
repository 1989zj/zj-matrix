# Context Packet 恢复系统

> **所属模块**: novel-factory V3 — Orchestrator Core  
> **文档版本**: v1.0  
> **核心目标**: 跨会话恢复创作时，为 Draft Agent 注入精确、完整的创作上下文（≤4000 tokens）

---

## 1. 背景与设计动机

### 1.1 问题

当用户执行 `novel-factory continue` 跨会话恢复创作时，LLM 的上下文窗口已完全丢失。MongoDB 中虽然保存了完整的原始数据（章节正文、角色状态、世界状态等），但 Draft Agent 无法直接利用这些分散的数据——原始数据量巨大（数万 tokens），且缺乏结构化的「当前创作状态」视图。

### 1.2 解决方案

**Context Packet** 是 Orchestrator 在每次 `continue` 前动态组装的一个「创作状态压缩包」。它从 MongoDB 的 4 个集合中提取关键信息，压缩为 ≤4000 tokens 的结构化 JSON，直接注入 Draft Agent 的 system prompt，让 Agent「瞬间找回」之前的创作节奏。

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| **丢失即无** | Packet 中不存在的信息视为已丢失，Draft Agent 不得自行补全 |
| **可逆压缩** | 信息密度优先，摘要而非全文 |
| **紧急排序** | 长期记忆按紧急度排序，优先展示最迫切的未解决项 |
| **幂等组装** | 相同 MongoDB 数据 → 相同 Packet（确定性） |

---

## 2. Context Packet 四层结构

每层从不同 MongoDB 集合抽取数据并压缩。

```
┌──────────────────────────────────────────────────────────┐
│                   Context Packet                          │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Layer 1     │  │  Layer 2     │  │  Layer 3       │  │
│  │  世界状态快照 │  │  角色状态矩阵 │  │  近期记忆压缩  │  │
│  └──────────────┘  └──────────────┘  └────────────────┘  │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Layer 4    长期记忆提取（伏笔·冲突·承诺）          │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 2.1 Layer 1 — 世界状态快照

**数据来源**: `world_states` 集合  
**压缩策略**: 仅取最新版本 + delta 摘要

| 字段 | 类型 | 说明 |
|------|------|------|
| `world_id` | string | 作品标识 |
| `era_name` | string | 当前时代名称 |
| `season` | string | 当前季节/时间阶段 |
| `summary` | string | 单行世界概况（≤60 chars） |
| `economy` | object | 经济指数：`{level: string, trend: "↑"|"↓"|"→", detail: string}` |
| `public_opinion` | object | 舆论状态：`{mood: string, key_issue: string}` |
| `power_map` | array | 各方势力当前影响力：`[{faction: string, influence: 1-10, trend: "↑"|"↓"|"→"}]` |
| `special_conditions` | array | 特殊状态（天灾、战争、节日等） |
| `timestamp` | int | 世界快照生成时间戳 |

**Token 预算**: ≤600 tokens

### 2.2 Layer 2 — 角色状态矩阵

**数据来源**: `characters` 集合  
**压缩策略**: 仅活跃角色（`status="active"`），关系图摘要而非全量邻接矩阵

| 字段 | 类型 | 说明 |
|------|------|------|
| `characters` | array | 每个活跃角色的压缩状态 |
| `├─ id` | string | 角色 ID |
| `├─ name` | string | 角色名 |
| `├─ role` | string | 角色定位（protagonist/antagonist/side/mentor/etc） |
| `├─ current_state` | object | 当前五维状态：`{emotion, combat_power, trust_level, wealth, influence}`，每维 1-10 |
| `└─ tags` | array | 当前标签（"受伤"、"隐姓埋名"、"被通缉"等） |
| `relationships` | array | 角色关系摘要（仅 Top-10 关键关系） |
| `├─ from` | string | 源角色名 |
| `├─ to` | string | 目标角色名 |
| `├─ type` | string | 关系类型（allies/rivals/lovers/family/enemies） |
| `└─ strength` | int | 关系强度 1-10 |
| `timestamp` | int | 状态矩阵生成时间戳 |

**Token 预算**: ≤1200 tokens

### 2.3 Layer 3 — 近期记忆压缩

**数据来源**: `chapters` 集合  
**压缩策略**: 最近 10 章，每章一句话摘要 + 关键事件列表 + 活跃钩子

| 字段 | 类型 | 说明 |
|------|------|------|
| `recent_chapters` | array | 最近 10 章的压缩摘要 |
| `├─ chapter_num` | int | 章节号 |
| `├─ title` | string | 章节标题 |
| `├─ one_line_summary` | string | 一句话章节摘要（≤100 chars） |
| `├─ key_events` | array | 本章关键事件列表（≤4 条） |
| `└─ cliffhanger` | string | 本章结尾钩子（若有） |
| `active_hooks` | array | 当前所有未解决的故事钩子 |
| `├─ hook_id` | string | 钩子标识 |
| `├─ description` | string | 钩子描述 |
| `├─ created_at` | int | 创建章节号 |
| `└─ urgency` | int | 紧迫度 1-10（越高越需要尽快回收） |

**Token 预算**: ≤1400 tokens

### 2.4 Layer 4 — 长期记忆提取

**数据来源**: `foreshadowing` + `plot_arcs` 集合  
**压缩策略**: 未回收伏笔按紧急度排序 + 未解决冲突 + 对读者的承诺（Chekhov's Gun 原则）

| 字段 | 类型 | 说明 |
|------|------|------|
| `unresolved_foreshadowing` | array | 未回收的伏笔，按紧急度降序 |
| `├─ id` | string | 伏笔 ID |
| `├─ description` | string | 伏笔内容 |
| `├─ planted_at` | int | 埋下伏笔的章节号 |
| `├─ urgency` | int | 紧急度 1-10 |
| `└─ type` | string | 伏笔类型（item/event/character/secret） |
| `unresolved_conflicts` | array | 未解决的主要冲突 |
| `├─ conflict_id` | string | 冲突 ID |
| `├─ parties` | array | 冲突方 |
| `├─ description` | string | 冲突描述 |
| `└─ escalation_level` | int | 升级程度 1-10 |
| `reader_promises` | array | 对读者的未兑现承诺 |
| `├─ promise_id` | string | 承诺 ID |
| `├─ description` | string | 承诺内容（"暗示主角会与宿敌对决"等） |
| `└─ fulfillment_window` | string | 预期兑现窗口（imminent/near/far） |

**Token 预算**: ≤800 tokens

---

## 3. 完整 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ContextPacket",
  "type": "object",
  "required": ["packet_meta", "world_snapshot", "character_matrix", "recent_memory", "long_term_memory"],
  "properties": {
    "packet_meta": {
      "type": "object",
      "description": "Packet 元信息",
      "required": ["version", "generated_at", "project_id", "current_chapter", "total_tokens"],
      "properties": {
        "version": { "type": "string", "enum": ["3.0"] },
        "generated_at": { "type": "integer", "description": "Unix 时间戳" },
        "project_id": { "type": "string" },
        "current_chapter": { "type": "integer", "minimum": 1 },
        "total_tokens": { "type": "integer", "description": "Packet 总 token 数（≤4000）" }
      }
    },

    "world_snapshot": {
      "type": "object",
      "description": "Layer 1: 世界状态快照",
      "required": ["world_id", "era_name", "summary"],
      "properties": {
        "world_id": { "type": "string" },
        "era_name": { "type": "string" },
        "season": { "type": "string" },
        "summary": { "type": "string", "maxLength": 60 },
        "economy": {
          "type": "object",
          "properties": {
            "level": { "type": "string" },
            "trend": { "type": "string", "enum": ["↑", "↓", "→"] },
            "detail": { "type": "string" }
          },
          "required": ["level", "trend"]
        },
        "public_opinion": {
          "type": "object",
          "properties": {
            "mood": { "type": "string" },
            "key_issue": { "type": "string" }
          }
        },
        "power_map": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "faction": { "type": "string" },
              "influence": { "type": "integer", "minimum": 1, "maximum": 10 },
              "trend": { "type": "string", "enum": ["↑", "↓", "→"] }
            },
            "required": ["faction", "influence"]
          }
        },
        "special_conditions": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },

    "character_matrix": {
      "type": "object",
      "description": "Layer 2: 角色状态矩阵",
      "required": ["characters"],
      "properties": {
        "characters": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["id", "name", "role", "current_state"],
            "properties": {
              "id": { "type": "string" },
              "name": { "type": "string" },
              "role": { "type": "string", "enum": ["protagonist", "antagonist", "side", "mentor", "love_interest", "neutral"] },
              "current_state": {
                "type": "object",
                "properties": {
                  "emotion": { "type": "integer", "minimum": 1, "maximum": 10 },
                  "combat_power": { "type": "integer", "minimum": 1, "maximum": 10 },
                  "trust_level": { "type": "integer", "minimum": 1, "maximum": 10 },
                  "wealth": { "type": "integer", "minimum": 1, "maximum": 10 },
                  "influence": { "type": "integer", "minimum": 1, "maximum": 10 }
                }
              },
              "tags": {
                "type": "array",
                "items": { "type": "string" }
              }
            }
          }
        },
        "relationships": {
          "type": "array",
          "maxItems": 10,
          "items": {
            "type": "object",
            "required": ["from", "to", "type", "strength"],
            "properties": {
              "from": { "type": "string" },
              "to": { "type": "string" },
              "type": { "type": "string", "enum": ["allies", "rivals", "lovers", "family", "enemies", "mentor_student", "neutral"] },
              "strength": { "type": "integer", "minimum": 1, "maximum": 10 }
            }
          }
        }
      }
    },

    "recent_memory": {
      "type": "object",
      "description": "Layer 3: 近期记忆压缩",
      "required": ["recent_chapters"],
      "properties": {
        "recent_chapters": {
          "type": "array",
          "maxItems": 10,
          "items": {
            "type": "object",
            "required": ["chapter_num", "one_line_summary"],
            "properties": {
              "chapter_num": { "type": "integer" },
              "title": { "type": "string" },
              "one_line_summary": { "type": "string", "maxLength": 100 },
              "key_events": {
                "type": "array",
                "maxItems": 4,
                "items": { "type": "string" }
              },
              "cliffhanger": { "type": "string" }
            }
          }
        },
        "active_hooks": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["hook_id", "description", "urgency"],
            "properties": {
              "hook_id": { "type": "string" },
              "description": { "type": "string" },
              "created_at": { "type": "integer" },
              "urgency": { "type": "integer", "minimum": 1, "maximum": 10 }
            }
          }
        }
      }
    },

    "long_term_memory": {
      "type": "object",
      "description": "Layer 4: 长期记忆提取",
      "properties": {
        "unresolved_foreshadowing": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["id", "description", "urgency", "type"],
            "properties": {
              "id": { "type": "string" },
              "description": { "type": "string" },
              "planted_at": { "type": "integer" },
              "urgency": { "type": "integer", "minimum": 1, "maximum": 10 },
              "type": { "type": "string", "enum": ["item", "event", "character", "secret", "prophecy"] }
            }
          }
        },
        "unresolved_conflicts": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["conflict_id", "parties", "description"],
            "properties": {
              "conflict_id": { "type": "string" },
              "parties": {
                "type": "array",
                "items": { "type": "string" }
              },
              "description": { "type": "string" },
              "escalation_level": { "type": "integer", "minimum": 1, "maximum": 10 }
            }
          }
        },
        "reader_promises": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["promise_id", "description"],
            "properties": {
              "promise_id": { "type": "string" },
              "description": { "type": "string" },
              "fulfillment_window": { "type": "string", "enum": ["imminent", "near", "far"] }
            }
          }
        }
      }
    }
  }
}
```

---

## 4. 完整 Packet 示例

```json
{
  "packet_meta": {
    "version": "3.0",
    "generated_at": 1716000000,
    "project_id": "proj_steampunk_revolution",
    "current_chapter": 24,
    "total_tokens": 3850
  },

  "world_snapshot": {
    "world_id": "w_steampunk_01",
    "era_name": "蒸汽革命时代",
    "season": "深秋",
    "summary": "帝国统治松动，地下革命组织崛起",
    "economy": {
      "level": "通货紧缩",
      "trend": "↓",
      "detail": "北部矿区罢工导致能源短缺"
    },
    "public_opinion": {
      "mood": "不安与愤怒",
      "key_issue": "帝国第37号《机械管制法》"
    },
    "power_map": [
      { "faction": "帝国议会", "influence": 6, "trend": "↓" },
      { "faction": "机械教会", "influence": 8, "trend": "↑" },
      { "faction": "地下革命军", "influence": 5, "trend": "↑" },
      { "faction": "商人公会", "influence": 7, "trend": "→" }
    ],
    "special_conditions": ["北部矿区戒严", "秋收祭典筹备中"]
  },

  "character_matrix": {
    "characters": [
      {
        "id": "char_001",
        "name": "艾琳娜·沃克",
        "role": "protagonist",
        "current_state": {
          "emotion": 3,
          "combat_power": 7,
          "trust_level": 4,
          "wealth": 3,
          "influence": 5
        },
        "tags": ["通缉中", "机械义肢受损", "寻找妹妹"]
      },
      {
        "id": "char_002",
        "name": "塞德里克·黑格",
        "role": "antagonist",
        "current_state": {
          "emotion": 8,
          "combat_power": 9,
          "trust_level": 2,
          "wealth": 9,
          "influence": 8
        },
        "tags": ["帝国密探总长", "知晓艾琳娜行踪"]
      },
      {
        "id": "char_003",
        "name": "芬恩·雷耶斯",
        "role": "side",
        "current_state": {
          "emotion": 6,
          "combat_power": 5,
          "trust_level": 7,
          "wealth": 4,
          "influence": 3
        },
        "tags": ["受伤卧床", "掌握矿区密道地图"]
      }
    ],
    "relationships": [
      { "from": "艾琳娜·沃克", "to": "塞德里克·黑格", "type": "enemies", "strength": 9 },
      { "from": "艾琳娜·沃克", "to": "芬恩·雷耶斯", "type": "allies", "strength": 7 },
      { "from": "塞德里克·黑格", "to": "芬恩·雷耶斯", "type": "rivals", "strength": 4 }
    ]
  },

  "recent_memory": {
    "recent_chapters": [
      {
        "chapter_num": 15,
        "title": "机械心脏",
        "one_line_summary": "艾琳娜在黑市获得受损的机械义肢核心",
        "key_events": ["与军火商接头", "遭遇密探追捕"],
        "cliffhanger": "义肢核心中藏着神秘的地图坐标"
      },
      {
        "chapter_num": 16,
        "title": "地下灯火",
        "one_line_summary": "芬恩将艾琳娜带入革命军秘密据点",
        "key_events": ["革命军审查艾琳娜", "得知妹妹被捕的消息"],
        "cliffhanger": "革命军内部出现叛徒"
      },
      {
        "chapter_num": 23,
        "title": "铁幕对峙",
        "one_line_summary": "艾琳娜潜入帝国档案馆寻找妹妹关押地点",
        "key_events": ["利用芬恩的地图潜入", "与塞德里克擦肩而过", "发现机械教会的秘密文件"],
        "cliffhanger": "塞德里克在档案馆出口设下伏兵"
      },
      {
        "chapter_num": 24,
        "title": "逃出生天",
        "one_line_summary": "艾琳娜突破重围逃出档案馆",
        "key_events": ["炸毁维修通道", "救出两名政治犯"],
        "cliffhanger": "政治犯中有一人正是叛徒"
      }
    ],
    "active_hooks": [
      { "hook_id": "hk_005", "description": "革命军叛徒身份未明", "created_at": 16, "urgency": 9 },
      { "hook_id": "hk_007", "description": "机械教会秘密文件内容待解读", "created_at": 23, "urgency": 7 },
      { "hook_id": "hk_003", "description": "艾琳娜妹妹关押地点已知但未营救", "created_at": 10, "urgency": 8 },
      { "hook_id": "hk_004", "description": "塞德里克已知艾琳娜行踪", "created_at": 14, "urgency": 6 }
    ]
  },

  "long_term_memory": {
    "unresolved_foreshadowing": [
      {
        "id": "fsh_001",
        "description": "艾琳娜父亲留下的怀表中藏着机械教会的钥匙",
        "planted_at": 3,
        "urgency": 8,
        "type": "item"
      },
      {
        "id": "fsh_002",
        "description": "芬恩曾提到'北方的机械龙'还活着",
        "planted_at": 8,
        "urgency": 5,
        "type": "event"
      },
      {
        "id": "fsh_003",
        "description": "塞德里克在密谈中提及'那个协议'即将到期",
        "planted_at": 20,
        "urgency": 9,
        "type": "secret"
      }
    ],
    "unresolved_conflicts": [
      {
        "conflict_id": "cnf_001",
        "parties": ["艾琳娜·沃克", "塞德里克·黑格"],
        "description": "塞德里克对艾琳娜的追捕已持续数月",
        "escalation_level": 8
      },
      {
        "conflict_id": "cnf_002",
        "parties": ["革命军", "帝国议会"],
        "description": "革命军计划袭击北部矿区监狱",
        "escalation_level": 6
      },
      {
        "conflict_id": "cnf_003",
        "parties": ["机械教会", "商人公会"],
        "description": "教会试图垄断新型机械核心技术",
        "escalation_level": 4
      }
    ],
    "reader_promises": [
      {
        "promise_id": "prm_001",
        "description": "暗示艾琳娜将与塞德里克在矿区进行最终对决",
        "fulfillment_window": "near"
      },
      {
        "promise_id": "prm_002",
        "description": "怀表钥匙将揭示机械教会起源的秘密",
        "fulfillment_window": "far"
      },
      {
        "promise_id": "prm_003",
        "description": "叛徒身份揭晓将触发革命军内部清洗",
        "fulfillment_window": "imminent"
      }
    ]
  }
}
```

---

## 5. 恢复流程（Step-by-step）

### 5.1 流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Context Packet 恢复流程                              │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐          │
│  │ 1. 世界状态   │───→│ 2. 最近记忆  │───→│ 3. 长期记忆      │          │
│  │    恢复       │    │    压缩      │    │    提取          │          │
│  └──────────────┘    └──────────────┘    └──────────────────┘          │
│         │                   │                     │                     │
│         ▼                   ▼                     ▼                     │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │              4. 组装 Context Packet                      │          │
│  │  world_snapshot + character_matrix + recent_memory       │          │
│  │  + long_term_memory + packet_meta                       │          │
│  └──────────────────────────────────────────────────────────┘          │
│         │                                                              │
│         ▼                                                              │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │              5. Token 预算审核                           │          │
│  │  ≤ 4000 tokens? ──是──→ 6. 注入 Draft Agent prompt      │          │
│  │       │                    │                             │          │
│  │      否                    │                             │          │
│  │       ▼                    │                             │          │
│  │  递归修剪最次要信息        │                             │          │
│  └────────────────────────────┘                             │          │
│         │                                                   │          │
│         ▼                                                   ▼          │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │  6. 注入 Draft Agent Prompt                              │          │
│  │  「以下是当前的 Context Packet，请基于此状态续写第 N 章」    │          │
│  └──────────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 详细步骤

#### Step 1 — 世界状态恢复

```
输入:   project_id, current_chapter
查询:  world_states 集合 → 取最新一条（created_at 最大）
       characters 集合 → 取所有 status="active" 的角色
输出:  world_snapshot object + 活跃角色原始列表
```

**操作说明**:
1. Orchestrator 从 MongoDB 查询 `world_states` 中与 `project_id` 匹配的最新文档
2. 若不存在，生成一个默认世界状态（`era_name="Unknown"`, `summary="世界初始化"`）
3. 查询 `characters` 集合，提取所有 `status="active"` 的角色
4. 对每个角色，读取 `current_state`（情绪/战力/信任/财富/影响力）和 `tags`

#### Step 2 — 最近记忆压缩

```
输入:   project_id, current_chapter, N=10
查询:  chapters 集合 → 最近 N 章（按 chapter_num 降序）
输出:  recent_chapters array + active_hooks array
```

**操作说明**:
1. 查询 `chapters` 集合，取 `chapter_num` 从 `max(1, current_chapter - N)` 到 `current_chapter` 的文档
2. 对每章，调用 LLM 压缩函数 `compress_chapter(chapter_doc) → {one_line_summary, key_events, cliffhanger}`
   - **注意**: 如果章节数少于 N 章，返回实际数量即可
3. 收集所有章节中标记的 `hook`，合并为 `active_hooks` 列表，按 `urgency` 降序
4. 去重：相同 `hook_id` 只保留最新版本

#### Step 3 — 长期记忆提取

```
输入:   project_id, current_chapter
查询:  foreshadowing 集合 → is_resolved=false, planted_at ≤ current_chapter
       plot_arcs 集合 → status="active"
输出:  unresolved_foreshadowing array + unresolved_conflicts array + reader_promises array
```

**操作说明**:
1. 查询 `foreshadowing` 集合：`{project_id, is_resolved: false, planted_at: {$lte: current_chapter}}`
   - 按 `urgency` 降序排列，最多取 15 条
2. 查询 `plot_arcs` 集合：`{project_id, status: "active"}`
   - 提取未解决的冲突（`unresolved_conflicts`）
   - 提取对读者的未兑现承诺（`reader_promises`）
3. 若任何数组为空，使用空数组 `[]` 占位

#### Step 4 — 组装 Context Packet

```
输入:  Step 1-3 的输出
输出:  JSON-serialized Context Packet
```

**操作说明**:
1. 构造 `packet_meta` 元信息
2. 将四层结构填入对应字段
3. 调用 `estimate_tokens(packet) → int`
4. 若 `total_tokens > 4000`，进入 Step 5（修剪）
5. 若 `≤ 4000`，进入 Step 6（注入）

#### Step 5 — Token 预算修剪（递归降级）

当 Packet 超过 4000 tokens 时，按以下优先级从低到高丢弃信息：

| 优先级 | 内容 | 修剪策略 |
|--------|------|----------|
| 1 (最低) | `reader_promises` 中 `fulfillment_window="far"` | 整条移除 |
| 2 | `power_map` 中 `influence ≤ 3` 的势力 | 移除 |
| 3 | `relationships` 中 `strength ≤ 3` 的关系 | 移除 |
| 4 | `active_hooks` 中 `urgency ≤ 3` 的钩子 | 移除 |
| 5 | `unresolved_foreshadowing` 中 `urgency ≤ 3` | 移除 |
| 6 | 章节摘要从 10 章逐步减少到 5 章 | 截断 |
| 7 (最高) | `recent_chapters` 中每章 `key_events` 从 4 条减到 2 条 | 截断 |

**算法**: 按优先级依次修剪，每次修剪后重新计算 token 数，直至 ≤ 4000。

#### Step 6 — 注入 Draft Agent Prompt

```python
draft_system_prompt = f"""你是一位专业小说续写作者。

以下是当前的创作上下文（Context Packet）：

```json
{json.dumps(context_packet, ensure_ascii=False, indent=2)}
```

请基于以上状态续写第 {current_chapter + 1} 章。
要求：
1. 严格遵循 Context Packet 中的世界状态、角色状态和未解决伏笔
2. 优先处理 urgency ≥ 7 的活跃钩子和伏笔
3. 保持角色性格一致性（参考 current_state）
4. 每章结尾可设置新的钩子（cliffhanger）
5. 输出格式：章标题 + 正文"""
```

---

## 6. Python 伪代码实现

### 6.1 核心组装函数

```python
"""context_packet.py — Context Packet 组装引擎"""

import json
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

# ---- 数据模型 ----

class PacketMeta(BaseModel):
    version: str = "3.0"
    generated_at: int
    project_id: str
    current_chapter: int
    total_tokens: int = 0

class WorldSnapshot(BaseModel):
    world_id: str
    era_name: str
    season: str = ""
    summary: str = ""
    economy: Optional[dict] = None
    public_opinion: Optional[dict] = None
    power_map: list = []
    special_conditions: list = []

class CharacterState(BaseModel):
    id: str
    name: str
    role: str
    current_state: dict
    tags: list = []

class CharacterMatrix(BaseModel):
    characters: list[CharacterState] = []
    relationships: list = []

class RecentMemory(BaseModel):
    recent_chapters: list = []
    active_hooks: list = []

class LongTermMemory(BaseModel):
    unresolved_foreshadowing: list = []
    unresolved_conflicts: list = []
    reader_promises: list = []

class ContextPacket(BaseModel):
    packet_meta: PacketMeta
    world_snapshot: WorldSnapshot
    character_matrix: CharacterMatrix
    recent_memory: RecentMemory
    long_term_memory: LongTermMemory


# ---- Token 估算 ----

def estimate_tokens(obj: dict) -> int:
    """粗略估算 JSON 序列化后的 token 数（~4 chars/token）"""
    raw = json.dumps(obj, ensure_ascii=False, default=str)
    return len(raw) // 4


# ---- 递归修剪 ----

PRUNE_RULES = [
    ("long_term_memory.reader_promises", lambda p: p.get("fulfillment_window") == "far"),
    ("world_snapshot.power_map", lambda p: p.get("influence", 0) <= 3),
    ("character_matrix.relationships", lambda r: r.get("strength", 0) <= 3),
    ("recent_memory.active_hooks", lambda h: h.get("urgency", 0) <= 3),
    ("long_term_memory.unresolved_foreshadowing", lambda f: f.get("urgency", 0) <= 3),
]

def prune_packet(packet: dict) -> dict:
    """递归修剪至 ≤4000 tokens"""
    if estimate_tokens(packet) <= 4000:
        return packet

    for path, condition in PRUNE_RULES:
        if estimate_tokens(packet) <= 4000:
            break
        keys = path.split(".")
        target = packet
        for k in keys:
            if isinstance(target, dict):
                target = target.get(k, {})
            else:
                break
        if isinstance(target, list):
            packet_copy = json.loads(json.dumps(packet))
            target_ref = packet_copy
            for k in keys:
                if isinstance(target_ref, dict):
                    target_ref = target_ref[k]
            target_ref[:] = [item for item in target_ref if not condition(item)]

    # Fallback: 缩减章节数
    if estimate_tokens(packet) > 4000:
        chapters = packet["recent_memory"]["recent_chapters"]
        while len(chapters) > 5 and estimate_tokens(packet) > 4000:
            chapters.pop(0)  # 删除最旧的章节

    # Final Fallback: 缩减每章 key_events
    if estimate_tokens(packet) > 4000:
        for ch in packet["recent_memory"]["recent_chapters"]:
            if len(ch.get("key_events", [])) > 2:
                ch["key_events"] = ch["key_events"][:2]

    packet["packet_meta"]["total_tokens"] = estimate_tokens(packet)
    return packet


# ---- 组装主函数 ----

async def build_context_packet(
    db,
    project_id: str,
    current_chapter: int,
) -> ContextPacket:
    """主入口：从 MongoDB 组装 Context Packet"""

    # 1. 世界状态快照
    world_doc = await db.world_states.find_one(
        {"project_id": project_id},
        sort=[("created_at", -1)]
    )
    world_snapshot = WorldSnapshot(
        world_id=world_doc.get("world_id", project_id),
        era_name=world_doc.get("era_name", "Unknown"),
        season=world_doc.get("season", ""),
        summary=world_doc.get("summary", ""),
        economy=world_doc.get("economy"),
        public_opinion=world_doc.get("public_opinion"),
        power_map=world_doc.get("power_map", []),
        special_conditions=world_doc.get("special_conditions", []),
    )

    # 2. 角色状态矩阵
    char_cursor = db.characters.find({
        "project_id": project_id,
        "status": "active"
    })
    characters = []
    async for char in char_cursor:
        characters.append(CharacterState(
            id=str(char["_id"]),
            name=char["name"],
            role=char.get("role", "side"),
            current_state=char.get("current_state", {}),
            tags=char.get("tags", []),
        ))

    relationships = []
    rel_cursor = db.relationships.find({"project_id": project_id})
    async for rel in rel_cursor:
        relationships.append({
            "from": rel["from"],
            "to": rel["to"],
            "type": rel.get("type", "neutral"),
            "strength": rel.get("strength", 5),
        })
    # 限制关系数量
    relationships = sorted(relationships, key=lambda r: r["strength"], reverse=True)[:10]

    # 3. 近期记忆压缩
    start = max(1, current_chapter - 10 + 1)
    chapter_cursor = db.chapters.find({
        "project_id": project_id,
        "chapter_num": {"$gte": start, "$lte": current_chapter}
    }).sort("chapter_num", 1)

    recent_chapters = []
    active_hooks = []
    async for ch in chapter_cursor:
        compressed = await _compress_chapter(ch)
        recent_chapters.append(compressed)
        for hook in ch.get("hooks", []):
            if hook.get("resolved", False) is False:
                active_hooks.append(hook)

    # 去重 + 排序钩子
    seen_hooks = set()
    unique_hooks = []
    for h in sorted(active_hooks, key=lambda x: x.get("urgency", 0), reverse=True):
        if h.get("hook_id") not in seen_hooks:
            seen_hooks.add(h.get("hook_id"))
            unique_hooks.append(h)

    # 4. 长期记忆提取
    foreshadowing_cursor = db.foreshadowing.find({
        "project_id": project_id,
        "is_resolved": False,
        "planted_at": {"$lte": current_chapter}
    }).sort("urgency", -1).limit(15)

    unresolved_foreshadowing = []
    async for f in foreshadowing_cursor:
        unresolved_foreshadowing.append({
            "id": str(f["_id"]),
            "description": f["description"],
            "planted_at": f.get("planted_at"),
            "urgency": f.get("urgency", 5),
            "type": f.get("type", "event"),
        })

    plot_doc = await db.plot_arcs.find_one({
        "project_id": project_id,
        "status": "active"
    })

    unresolved_conflicts = plot_doc.get("unresolved_conflicts", []) if plot_doc else []
    reader_promises = plot_doc.get("reader_promises", []) if plot_doc else []

    # 5. 组装 Packet
    packet = ContextPacket(
        packet_meta=PacketMeta(
            generated_at=int(datetime.utcnow().timestamp()),
            project_id=project_id,
            current_chapter=current_chapter,
        ),
        world_snapshot=world_snapshot,
        character_matrix=CharacterMatrix(
            characters=characters,
            relationships=relationships,
        ),
        recent_memory=RecentMemory(
            recent_chapters=recent_chapters,
            active_hooks=unique_hooks[:10],  # 最多 10 个钩子
        ),
        long_term_memory=LongTermMemory(
            unresolved_foreshadowing=unresolved_foreshadowing,
            unresolved_conflicts=unresolved_conflicts,
            reader_promises=reader_promises,
        ),
    )

    packet_dict = packet.model_dump()
    packet_dict = prune_packet(packet_dict)

    return packet_dict


async def _compress_chapter(chapter_doc: dict) -> dict:
    """将章节数据压缩为摘要格式"""
    # 实际实现中可调用 LLM 进行摘要
    # 此处为简化版本，直接提取已有字段
    return {
        "chapter_num": chapter_doc["chapter_num"],
        "title": chapter_doc.get("title", ""),
        "one_line_summary": chapter_doc.get("summary", ""),
        "key_events": chapter_doc.get("key_events", [])[:4],
        "cliffhanger": chapter_doc.get("cliffhanger", ""),
    }


# ---- Orchestrator 入口 ----

async def handle_continue_command(db, project_id: str, current_chapter: int) -> str:
    """`novel-factory continue` 命令的完整处理流程"""
    packet = await build_context_packet(db, project_id, current_chapter)

    # 注入 Draft Agent
    draft_prompt = f"""你是一位专业小说续写作者。

以下是当前的创作上下文（Context Packet）：

```json
{json.dumps(packet, ensure_ascii=False, indent=2)}
```

请基于以上状态续写第 {current_chapter + 1} 章。
要求：
1. 严格遵循 Context Packet 中的世界状态、角色状态和未解决伏笔
2. 优先处理 urgency ≥ 7 的活跃钩子和伏笔
3. 保持角色性格一致性（参考 current_state）
4. 每章结尾可设置新的钩子（cliffhanger）
5. 输出格式：章标题 + 正文"""

    return draft_prompt
```

### 6.2 Token 估算辅助工具

```python
def estimate_tokens_deep(text: str) -> int:
    """精确 token 估算（模拟 cl100k_base BPE）"""
    # 简化版：英文 ~4 chars/token, 中文 ~1.5 chars/token
    import re
    asian_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', text))
    other_chars = len(text) - asian_chars
    return int(asian_chars * 1.5 + other_chars / 4) + len(text.split()) // 2
```

---

## 7. MongoDB 集合依赖

| 集合 | 查询条件 | 用途 |
|------|---------|------|
| `world_states` | `project_id`, 最新 `created_at` | Layer 1 世界状态快照 |
| `characters` | `project_id`, `status="active"` | Layer 2 角色状态矩阵 |
| `relationships` | `project_id` | Layer 2 角色关系图 |
| `chapters` | `project_id`, `chapter_num ∈ [curr-9, curr]` | Layer 3 近期记忆 |
| `foreshadowing` | `project_id`, `is_resolved=false`, `planted_at ≤ curr` | Layer 4 未回收伏笔 |
| `plot_arcs` | `project_id`, `status="active"` | Layer 4 冲突与承诺 |

---

## 8. 边界情况与错误处理

| 场景 | 处理方式 |
|------|---------|
| 项目刚创建，无任何章节 | `current_chapter=0`，`recent_chapters=[]`，world_snapshot 使用默认值 |
| 角色全部死亡/消失 | `characters=[]`，Draft Agent 仅依靠世界状态和伏笔写作 |
| 无未回收伏笔 | `unresolved_foreshadowing=[]`，跳过该字段 |
| 章节数少于 10 | 返回实际章节数，不填充空数据 |
| 修剪后仍 >4000 tokens | 硬截断：从最低优先级字段逐步删除到 3500 tokens 为止 |
| 数据库连接失败 | 抛出 `ContextPacketBuildError`，返回给用户友好错误消息 |
| 角色状态字段缺失 | 使用默认值 `5`（中间值），记录警告日志 |

---

## 9. 性能指标与监控

| 指标 | 目标 | 说明 |
|------|------|------|
| **组装延迟** | <500ms | 从接收 `continue` 到 Packet 就绪 |
| **Packet 大小** | ≤4000 tokens | 确保注入后不占用过多上下文窗口 |
| **压缩比** | ≥15:1 | 原始数据 ~60K tokens → Packet ≤4K tokens |
| **命中率** | ≥95% | Draft Agent 在 Packet 中找到足够信息的概率 |
| **错误率** | <1% | Packet 组装失败的比例 |

---

## 10. 与其他系统的接口

### 10.1 上游输入

- **Orchestrator** → 触发 `build_context_packet(db, project_id, current_chapter)`
- **用户命令** → `novel-factory continue` 触发整个流程

### 10.2 下游输出

- **Draft Agent** → 接收格式化的 system prompt（含 Context Packet）
- **MongoDB** → 所有数据源（只读操作，不写入）
- **日志系统** → 记录组装耗时、token 数、修剪情况

---

## 附录 A：版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2025-05-18 | 初始稿 — 四层结构 + JSON Schema + 完整流程 |

## 附录 B：设计决策记录 (ADR)

### ADR-001: 为什么不用全文检索而用结构化 JSON？

**决策**: 使用预定义 schema 的结构化 JSON，而非全文向量检索。

**理由**:
1. 确定性：相同数据产生相同 Packet，便于调试
2. Token 效率：结构化数据天然比自然语言更紧凑
3. 可预测：Draft Agent 知道每个字段的位置和含义
4. 向量检索适合「模糊搜索」场景，Context Packet 需要的是「精确恢复」

### ADR-002: 为什么 Layer 4 不放 Layer 3 前面？

**决策**: 长期记忆放在最后。

**理由**: Draft Agent 的注意力分布是从近到远。Layer 1-3 是即刻需要的「现在是什么状态」，Layer 4 是「别忘了什么」。前置近了再提久远的伏笔，符合人类创作者的认知顺序。

### ADR-003: 为什么修剪策略是递归降级而非一次到位？

**决策**: 优先级递进式修剪。

**理由**: 避免过度修剪。大多数 Normal 场景 Packet 在 2500-3500 tokens 之间，只有极端场景（30+ 活跃角色、满钩子）才需要修剪。按优先级逐步丢弃最低价值信息，保留最大信息量。
