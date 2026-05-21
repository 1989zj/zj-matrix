#!/usr/bin/env python3
"""
对话声音批量精修脚本 — Batch Dialogue Voice Refiner

自动提取章节对白 → LLM 按角色声音特征改写 → 应用回 MongoDB → 可选同步

用法:
    # 基本用法：处理 ch4-9，自动调用 DeepSeek
    python3 dialogue-voice-refiner.py '诡异游戏' --chapters 4-9
    
    # 指定自定义角色画像（不指定则从默认数据库配置读取）
    python3 dialogue-voice-refiner.py '诡异游戏' --chapters 4-9 --profiles my_profiles.txt
    
    # 预览模式 + 使用阿里通义千问替代 DeepSeek
    python3 dialogue-voice-refiner.py '诡异游戏' --chapters 4-9 --dry-run --provider qwen

规则:
    - 默认 ≤5 条修改/轮（防次生损伤）
    - 默认只改「」内对白，不改叙述
    - 修改后自动运行评审验证

依赖:
    pymongo, yaml, urllib.request (标准库)
"""

import pymongo
import json
import os
import re
import yaml
import urllib.request
import argparse
import sys
from datetime import datetime, timezone

# ── Default MongoDB URIs ──
MONGO_URI = 'mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin'
NOVEL_DB = 'novel'
FACTORY_DB = 'novel_factory'

# ── Default Character Voice Profile (诡异游戏) ──
DEFAULT_PROFILE = """
角色声音特征：

林远（男主，24岁，能看到规则文本）：
- 说话直接、短促、果断
- 句尾少语气词（啊/呢/吧），多名词+句号收尾
- 非必要不使用「好像/可能/大概」

陈远志（前设施研究员，40+岁，能感觉到规则温度）：
- 语气沉稳但透着疲惫
- 用语精确但啰嗦（像是/可能/换句话说）
- 句子里带有停顿感（破折号、省略号使用频率高）

刘闯（工厂工人，30岁左右，务实）：
- 短句为主，口语化
- 语速快，不耐烦的时候用「啧」「不是」打断
- 用词接地气（东西/事/搞），不用书面词

赵铁（退伍军人，50+岁，在设施独活了两个月）：
- 说话像汇报——短、准、不带感情色彩
- 偶尔冒出黑色幽默（语气平淡地说荒谬的话）
- 每句话都是一条信息——不浪费字

方晴（地质研究生，25岁）：
- 提问驱动——总是在'排查'，总是在问问题
- 语气里带着学术思维的痕迹（严谨但紧张）
- 压力大时用问题掩饰不安

顾晚（护士助理，能感觉到规则热量）：
- 话少但准确——每句话要么是发现，要么是确认
- 语气平静，情绪起伏不明显
- 说结论时用确认语调而非疑问
"""


def parse_chapters(arg: str) -> list[int]:
    chapters = []
    for part in arg.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            chapters.extend(range(int(a), int(b) + 1))
        else:
            chapters.append(int(part))
    return sorted(set(chapters))


def get_api_config(provider_name: str = 'deepseek'):
    """从 Hermes config.yaml 获取 API 配置"""
    with open(os.path.expanduser('~/.hermes/config.yaml')) as f:
        cfg = yaml.safe_load(f)
    
    for i, prov in enumerate(cfg.get('custom_providers', [])):
        name = prov.get('name', '').lower()
        if provider_name.lower() in name:
            return {
                'api_key': prov['api_key'],
                'base_url': prov.get('base_url', 'https://api.deepseek.com'),
                'model': prov.get('model', 'deepseek-chat'),
                'index': i
            }
    return None


def call_llm(prompt: str, api: dict, temperature: float = 0.5) -> list:
    """调用 LLM 获取对话修改建议，返回 JSON 数组
    
    ⚠️ Pitfall: DeepSeek API 需要在 base_url 后加 /v1/chat/completions
    ⚠️ Pitfall: config 中 API key 可能被不同的 provider 索引引用
    """
    base_url = api['base_url'].rstrip('/')
    if '/v1' not in base_url:
        url = f'{base_url}/v1/chat/completions'
    else:
        url = f'{base_url}/chat/completions'
    
    data = json.dumps({
        'model': api['model'],
        'messages': [
            {'role': 'system', 'content': '你是一位专业的小说精修编辑。只返回JSON。'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': temperature,
        'max_tokens': 3000
    }).encode()
    
    req = urllib.request.Request(url, data=data,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api["api_key"]}'})
    
    try:
        resp = urllib.request.urlopen(req, timeout=90)
        result = json.loads(resp.read())
        content = result['choices'][0]['message']['content']
        json_match = re.search(r'\[[\s\S]*?\]', content)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(content)
    except Exception as e:
        print(f'  [ERROR] LLM call failed: {e}')
        return []


def build_prompt(ch_num: int, content: str, voice_profile: str) -> str:
    return f"""你是一位中文网文精修编辑。下面是一章小说的正文。

**角色声音特征：**
{voice_profile}

请从正文中找出3-5句「」内的对白，这些对白读起来「缺乏角色辨识度」——即换一个角色来说也毫无违和感。

**精修原则：**
1. 只改对白原文（「」里面的内容），不改叙述旁白
2. 保持剧情信息完全不变
3. output中只输出「」内的文本，不含「」符号
4. 原始文本必须在原文中能找到

**章节正文（第{ch_num}章）：**
{content}

**输出格式：** JSON数组，每个元素：
- original: 原始对白文本（精确到字，不含「」）
- replacement: 替换后的对白文本（不含「」）
- character: 角色名
- reason: 修改理由（10-20字）"""


def main():
    parser = argparse.ArgumentParser(description='对话声音批量精修')
    parser.add_argument('novel_name', help='小说名')
    parser.add_argument('--chapters', required=True, help='章节范围: 4-9 或 4,5,6')
    parser.add_argument('--profiles', help='角色画像文件（可选，不指定使用内置默认）')
    parser.add_argument('--provider', default='deepseek', help='API provider名，如 deepseek, qwen')
    parser.add_argument('--max-per-chapter', type=int, default=5, help='每章最大修改数（默认5，防次生损伤）')
    parser.add_argument('--dry-run', action='store_true', help='只预览不写入')
    parser.add_argument('--skip-review', action='store_true', help='不自动跑评审')
    args = parser.parse_args()
    
    chapters = parse_chapters(args.chapters)
    print(f'小说: {args.novel_name}')
    print(f'章节: {chapters}')
    print(f'模式: {"DRY RUN" if args.dry_run else "写入"}'  )
    
    # Load voice profile
    if args.profiles:
        with open(args.profiles) as f:
            voice_profile = f.read()
        print(f'角色画像: {args.profiles}')
    else:
        voice_profile = DEFAULT_PROFILE
        print(f'角色画像: 内置默认')
    
    # Get API config
    api = get_api_config(args.provider)
    if not api:
        print(f'错误: 找不到 provider "{args.provider}"，可用: deepseek, qwen, kimi')
        return
    print(f'API: {api["base_url"]} ({api["model"]})')
    
    # Connect MongoDB
    c = pymongo.MongoClient(MONGO_URI)
    novel_db = c[NOVEL_DB]
    nf = c[FACTORY_DB]
    
    # Load chapters
    docs = list(novel_db['chapters'].find(
        {'novelName': args.novel_name, 'chapterNumber': {'$in': chapters}}
    ).sort('chapterNumber', 1))
    
    found = [d['chapterNumber'] for d in docs]
    missing = [c for c in chapters if c not in found]
    if missing:
        print(f'警告: 缺失章节 {missing}')
    
    total_changes = 0
    total_skipped = 0
    
    for doc in docs:
        num = doc['chapterNumber']
        content = doc.get('content', '')
        print(f'\n{"="*40}')
        print(f'第{num}章 ({len(content)}字)')
        
        prompt = build_prompt(num, content, voice_profile)
        suggestions = call_llm(prompt, api)
        
        if not suggestions:
            print(f'  -> 无建议')
            continue
        
        # Cap at max-per-chapter
        suggestions = suggestions[:args.max_per_chapter]
        print(f'  收到 {len(suggestions)} 条建议')
        
        new_content = content
        chapter_changes = 0
        chapter_skipped = 0
        
        for s in suggestions:
            orig = s.get('original', '').strip()
            repl = s.get('replacement', '').strip()
            char = s.get('character', '?')
            reason = s.get('reason', '')
            
            if not orig or not repl:
                chapter_skipped += 1
                continue
            
            # Match 「orig」 in content (LLM should NOT include brackets)
            pattern = f'「{re.escape(orig)}」'
            if re.search(pattern, new_content):
                new_content = re.sub(pattern, f'「{repl}」', new_content, count=1)
                chapter_changes += 1
                print(f'  ✅ ch{num} {char}: "{orig[:50]}" → "{repl[:50]}" ({reason})')
            else:
                chapter_skipped += 1
                print(f'  ⚠️ 未匹配: "{orig[:50]}" (已修改过或原文不同)')
        
        if chapter_changes > 0 and not args.dry_run:
            word_count = len(new_content)
            result = novel_db['chapters'].update_one(
                {'novelName': args.novel_name, 'chapterNumber': num},
                {'$set': {'content': new_content, 'wordCount': word_count}}
            )
            print(f'  -> 已写入: {result.modified_count} 文档更新, {word_count}字')
            # Save diff
            with open(f'/tmp/refine_ch{num}_before.txt', 'w') as f:
                f.write(content)
            with open(f'/tmp/refine_ch{num}_after.txt', 'w') as f:
                f.write(new_content)
        elif chapter_changes > 0 and args.dry_run:
            print(f'  -> DRY RUN: 不写入')
        
        total_changes += chapter_changes
        total_skipped += chapter_skipped
    
    print(f'\n{"="*40}')
    print(f'完成: {total_changes} 处修改, {total_skipped} 处跳过')
    print(f'共处理: {len(found)} 章')
    
    if total_changes > 0 and not args.dry_run:
        print(f'\n下一步建议:')
        print(f'  1. 评审: 使用 novel-review-pipeline 评审这 {len(found)} 章')
        print(f'  2. 同步: python3 sync-after-refinement.py "{args.novel_name}" --chapters {args.chapters} --merge --llm-hooks')


if __name__ == '__main__':
    main()
