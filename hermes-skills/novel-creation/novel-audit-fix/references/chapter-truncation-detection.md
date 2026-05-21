# Chapter Truncation Detection

某些章节可能在初始生成/导入过程中被截断（末尾缺句），在 MongoDB 中的 `content` 字段不完整。

## 截断特征

1. **末尾以破折号结尾** — content 最后几个字是 `——` 或 `——` 后面无内容
2. **末尾以省略号结尾** — `……` 或 `...` 后接空行或文件结束
3. **末尾是未完的半句话** — 最后一句明显是句首而非句尾（如「第四张。上面只有一行字——」）
4. **末尾没有句号** — 中文小说正文段落通常以句号/问号/感叹号/引号收尾，若最后一段无标点结尾需警惕

## 检测脚本

```python
from pymongo import MongoClient

def find_truncated_chapters(novel_name, db):
    """扫描所有章节，找末尾截断的候选"""
    truncated = []
    for ch in db.chapters.find({'novelName': novel_name}).sort('chapterNumber', 1):
        content = ch.get('content', '')
        end = content[-30:] if len(content) >= 30 else content
        
        reasons = []
        if '——' in end and not content.endswith('」'):
            reasons.append('以破折号结尾')
        if end.rstrip().endswith('...') or end.rstrip().endswith('……'):
            reasons.append('以省略号结尾')
        if content and content[-1] not in '。！？」）】\n':
            # 最后一段不以标点结尾（排除代码/格式字符）
            last_line = content.strip().split('\n')[-1]
            if last_line and last_line[-1] not in '。！？」）】\n～':
                reasons.append(f'末尾无收束标点: "...{last_line[-20:]}"')
        
        if reasons:
            truncated.append({
                'chapter': ch['chapterNumber'],
                'wordCount': ch.get('wordCount', 0),
                'reasons': reasons,
                'tail': end[-50:] if len(end) >= 50 else end
            })
    return truncated

# 使用
client = MongoClient('mongodb://user:pass@host:port/novel?authSource=admin')
db = client['novel']
results = find_truncated_chapters('诡异游戏：我的规则别人看不见', db)
for r in results:
    print(f"ch{r['chapter']} ({r['wordCount']}字): {'; '.join(r['reasons'])}")
    print(f"  末尾: {r['tail']}")
```

## 修复流程

发现截断后需人工确认原意，不可自动补写：

1. 检查项目目录有无原始 `.md` 文件（`chapters/` 或 `output/`）
2. 检查 Git 历史有无被删除的原始版本
3. 检查 chapter_memory 的 summary/hook 是否暗示了结尾
4. 查看下一章开头——时间跳跃或场景切换暗示原章结尾应如何收束
5. 如上述均找不到，手动询问作者补充

## 已知案例

| 章节 | 字数 | 末尾 | 状态 |
|------|------|------|------|
| ch02 | 3141 | 「第四张。上面只有一行字——」 | ❌ 缺句, 待补 |
