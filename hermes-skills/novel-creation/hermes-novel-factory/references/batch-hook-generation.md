# 批量章末钩子生成指南

## 场景

V1→V2 迁移后，`chapter_memory` 的 `hook` 字段存在但值为空字符串 `""`。
需要根据每章的 `summary` 内容批量生成差异化钩子。

## 核心约束

- 每钩 30-60 字中文，不能太短（无吸引力）也不能太长（剧透）
- 相邻 3 章的钩子不能模式雷同（如连续使用"到底…"句式）
- 悬疑/恐怖类型以疑问句为主，动作型以悬念剪辑为主
- 每章钩子必须基于该章的 `summary` 内容，不能凭空捏造
- 135 章用 1 个 delegate_task 完成（max_concurrent_children=3 只影响并行，单任务内批量处理没问题）

## 推荐流程

1. 从 MongoDB 读取该项目的所有 `chapter_memory`，按 `chapter` 排序
2. 将数据（chapter_number + summary）打包成一个 batch 传给 delegate_task
3. delegate_task 内的 prompt 结构：

```
你是一个番茄小说章末钩子设计师。任务是为一本悬疑恐怖小说的每一章生成章末钩子。

每钩要求：
- 30-60 字中文
- 以疑问句或悬念句结尾
- 相邻 3 章的钩子不能模式重复
- 基于该章的 summary 内容生成

小说类型：悬疑恐怖
下文是 135 章的 summary。请为每一章输出钩子。

返回格式：纯 JSON 数组，每个元素 {"chapter": N, "hook": "钩子文本"}
```

4. 拿到返回结果后，遍历 JSON 数组，逐条 `db["chapter_memory"].update_one({"project_id": pid, "chapter": ch}, {"$set": {"hook": hook}})` 写入 MongoDB

## Pitfalls

- **相邻章重复检测**：模型可能连续输出 "xxx到底是…" 模式。写好 prompt 约束后，抽检第 1-3 章、67-69 章、133-135 章三组相邻钩子
- **字数检查**：大于 80 字的钩子需要截断重写
- **类型适配**：悬疑恐怖是疑问句为主；都市/恋爱是情感悬念为主；系统升级是爽点预告为主
