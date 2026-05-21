# DeepSeek API 重试策略（对话声音重塑场景）

> 来源于 ch10-20 精修实战。DeepSeek v4 Flash 在对话声音重塑场景下的间歇性空返回问题及对策。

## 现象

`dialogue-voice-refiner.py` 对某些章节调用 DeepSeek API 时返回空响应：

```
ch12: 1 change suggested, WARNING: LLM response parse failed (API returned empty)
ch14: API error
ch15: API error
ch19: API error
```

但同样的章节内容、同样的 prompt，**等 10-30 秒后重试就能成功**。

## 根因推测

- **隐性速率限制**：连续调用 3+ 章后，DeepSeek API 静默丢弃部分请求（不返回错误，返回空 body）
- **请求体大小**：章节字数越多（>3000 字）越容易超时或返回空
- **与模型无关**：deepseek-v4-flash 和 deepseek-chat 都有此现象

## 重试策略

### 策略 A：手动分批（推荐）

```bash
# 最多 5 章一批，批次间 sleep 5-10 秒
python3 dialogue-voice-refiner.py '书名' --chapters 10-12
sleep 10
python3 dialogue-voice-refiner.py '书名' --chapters 13-15
sleep 10
python3 dialogue-voice-refiner.py '书名' --chapters 16-20
```

### 策略 B：独立 retry 脚本（对失败章节）

```bash
python3 scripts/retry-failed-chapters.py '书名' --chapters 12,14,15,19
```

### 策略 C：恒等退避（编程模式）

```python
for attempt in range(3):
    try:
        resp = call_llm(prompt, api)
        if resp:
            return resp
    except:
        pass
    time.sleep((attempt + 1) * 10)
```

## 验证步骤

每次 apply 后必须验证修改已生效：

```python
import pymongo
c = pymongo.MongoClient('mongodb://...')
ch = c['novel']['chapters'].find_one({'novelName':'书名','chapterNumber':10})
print('记下了' in ch['content'])  # 应为 False
print('记住了' in ch['content'])  # 应为 True  
```

如果旧文本仍在、新文本未出现 → patch 未应用，需用 retry 脚本重新 apply。
