# MongoDB 小说写作平台数据库 Schema

> 最后更新: 2026-05-14
> 数据库: `novel` (192.168.2.30:27017)
> 认证: `mongo_8F6dTZ:mongo_dxx8nA`

## 连接方式

```python
import pymongo
client = pymongo.MongoClient("mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/")
db = client['novel']
```

## 集合清单（8个）

### 1. novels — 小说元数据

```json
{
  "_id": ObjectId,
  "name": "我的第一部小说",
  "title": "末世：我的污染等级比怪物高",
  "author": "",
  "genre": "末世重生·异能进化·暗黑克苏鲁",
  "slug": "wo-de-wu-ran-deng-ji",
  "stats": {
    "words": 154099,
    "chapters": 60,
    "status": "已完结"
  },
  "synopsis": "重生回末日三天前...",
  "world": {
    "power_system": {"name": "污染等级体系", "levels": "P0→P1→P2~P5→P6~P10", "source": "...", "note": "..."},
    "timeline": {}
  },
  "characters": [
    {"name": "陆川", "title": "主角·执线者·终结者", "ability": "...", "desc": "...", "traits": ["冷静","果断"]}
  ],
  "tags": ["末世","重生","异能进化","暗黑克苏鲁","污染吞噬"],
  "target": "起点中文网",
  "updatedAt": ISODate("2026-05-10T14:23:00.528Z")
}
```

**现有数据**:
| name | title | 字数 | 章节 | 状态 |
|------|-------|------|------|------|
| 我的第一部小说 | 末世：我的污染等级比怪物高 | 154K | 60 | 已完结 |
| 诡异游戏：我的规则别人看不见 | 诡异游戏：我的规则别人看不见 | 280K | 105 | 连载中 |

### 2. chapters — 章节正文

```json
{
  "_id": ObjectId,
  "novelName": "我的第一部小说",
  "chapterNumber": 1,
  "title": "第一章 我活过来了",
  "filename": "",
  "content": "陆川是被冻醒的。\n\n不对——他是被疼醒的...",
  "chapterEndNotes": "",
  "version": "v1",
  "wordCount": 2349
}
```

**现有数据**:
| novelName | 章节数 | 有内容 | 总字数 |
|-----------|--------|--------|--------|
| 我的第一部小说 | 80 | 80 | 275,919 |
| 诡异游戏：我的规则别人看不见 | 135 | 135 | 326,178 |
| 末世：我的污染等级比怪物高 | 2 (含1个test) | 1 | 4,061 |

> **注意**: "末世：我的污染等级比怪物高" 的完整内容实际存储在 "我的第一部小说" 名下。
> 写入新数据时需保持 `novelName` 一致。

### 3. users — 平台用户

```json
{
  "_id": ObjectId,
  "username": "admin",
  "password": "scrypt:32768:8:1$...",
  "role": "admin",
  "email": "admin@example.com"
}
```
角色: admin, customer

### 4. orders — 订单系统

```json
{
  "_id": ObjectId,
  "projectName": "测试订单",
  "customerName": "测试客户",        // 可为空
  "contact": "",
  "genre": "玄幻",
  "detail": "这是一个测试订单",
  "targetWords": 50000,
  "chapters": 30,
  "status": "pending",              // pending / confirmed / canceled
  "progress": 0,
  "deliveredWords": 0,
  "deliveredChapters": 0,
  "notes": "",
  "deliverable": "",
  "createdAt": ISODate,
  "updatedAt": ISODate
}
```

### 5. reports — 分析报告

```json
{
  "_id": ObjectId,
  "novelName": "我的第一部小说",
  "type": "summary",                // summary / report / logic / titles / highlight / review / consistency
  "filename": "第五卷阶段总结.md",
  "content": "# 第五卷·苏醒之树 阶段总结...",
  "createdAt": ISODate
}
```

**现有报告类型**: summary(阶段总结), report(分析), logic(逻辑审核), titles(标题优化), highlight(爽点分析), review(商业评估), consistency(一致性检查)

### 6. settings — 系统设置

```json
{
  "_id": "order_prices",
  "prices": {
    "全本新小说": 18,
    "小说续写": 12,
    "小说改写": 8,
    "小说优化": 5
  }
}
```
价格单位推测为 元/千字。

### 7. notifications — 用户通知

```json
{
  "_id": ObjectId,
  "username": "admin",
  "title": "订单状态更新",
  "message": "您的项目 \"定价测试\" 已更新为 已取消",
  "read": false,
  "createdAt": ISODate
}
```

### 8. sms_codes — 短信验证码（空集合）

## 查询技巧

### 按小说名查所有章节

```python
chapters = db.chapters.find({"novelName": "异能至尊"}).sort("chapterNumber", 1)
```

### 查小说统计数据

```python
novel = db.novels.find_one({"name": "异能至尊"})
print(f"总字数: {novel['stats']['words']}, 章节: {novel['stats']['chapters']}")
```

### 批量插入章节

```python
ops = []
for i, ch in enumerate(chapter_list, 1):
    ops.append(pymongo.UpdateOne(
        {"novelName": novel_name, "chapterNumber": i},
        {"$set": {"title": ch['title'], "content": ch['content'],
                   "wordCount": len(ch['content']), "version": "v1"}},
        upsert=True
    ))
db.chapters.bulk_write(ops)
```

### 更新novel统计

```python
db.novels.update_one(
    {"name": novel_name},
    {"$set": {"stats.words": total_words, "stats.chapters": total_chapters,
               "stats.status": "已完结", "updatedAt": datetime.now()}}
)
```
