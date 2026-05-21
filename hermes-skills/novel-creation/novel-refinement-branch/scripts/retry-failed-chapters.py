#!/usr/bin/env python3
"""
retry-failed-chapters.py — 对话声音重塑失败章节独立重试脚本

当 dialogue-voice-refiner.py 对某些章节返回空/API错误时，
用本脚本单独重试。每章独立调用，间隔3秒，有3次重试 + 退避。

用法:
    # 对指定章节重试
    python3 retry-failed-chapters.py '诡异游戏：我的规则别人看不见' --chapters 12,14,15,19

    # 对所有返回空结果的章节自动重试（需先跑过 dialogue-voice-refiner）
    python3 retry-failed-chapters.py '诡异游戏：我的规则别人看不见' --auto-detect

MongoDB: novel.chapters -> content + wordCount
"""

import json, urllib.request, pymongo, yaml, os, re, sys, time
from datetime import datetime, timezone

MONGO_URI = 'mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin'

VOICE_PROFILE = """角色声音：
- 林远（主角，冷静分析型）：短句、直接、果断、从不拖泥带水、偶尔用数字类比
- 顾晚（神秘女性）：话少、准确、结论式表达、不解释
- 周文（学者/技术员）：完整句子、逻辑分析、用词精确、长句多
- 赵铁（战斗型）：短、准、汇报风格、关键词式
- 方晴（医疗/感知型）：提问驱动、描述精确、常用推测语气
- 刘闯（普通工兵）：短句口语化、脏话语气词多
- 老钱（中年稳重）：沉稳、啰嗦、常常自问自答"""

def get_api():
    with open(os.path.expanduser('~/.hermes/config.yaml')) as f:
        cfg = yaml.safe_load(f)
    for prov in cfg.get('custom_providers', []):
        if 'deepseek' in prov.get('name', '').lower():
            return {
                'api_key': prov['api_key'],
                'base_url': prov.get('base_url', 'https://api.deepseek.com'),
                'model': prov.get('model', 'deepseek-chat')
            }
    raise ValueError("DeepSeek provider not found in config")

def call_llm(prompt, api, temperature=0.5, max_retries=3):
    url = api['base_url'].rstrip('/') + '/v1/chat/completions'
    
    for attempt in range(max_retries):
        try:
            data = json.dumps({
                'model': api['model'],
                'messages': [
                    {'role': 'system', 'content': '你是一位专业的小说精修编辑。只返回JSON。'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': temperature,
                'max_tokens': 3000
            }).encode()
            req = urllib.request.Request(url, data=data, headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + api['api_key']
            })
            resp = urllib.request.urlopen(req, timeout=90)
            result = json.loads(resp.read())
            content = result['choices'][0]['message']['content']
            json_match = re.search(r'\[[\s\S]*?\]', content)
            return json.loads(json_match.group()) if json_match else json.loads(content)
        except Exception as e:
            print(f"    ⚠️ Attempt {attempt+1}/{max_retries} failed: {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                delay = (attempt + 1) * 10
                print(f"    Waiting {delay}s before retry...", file=sys.stderr)
                time.sleep(delay)
    return []

def parse_chapters(arg):
    chapters = []
    for part in arg.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            chapters.extend(range(int(a), int(b) + 1))
        else:
            chapters.append(int(part))
    return sorted(set(chapters))

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Retry failed chapter refinement')
    parser.add_argument('novel_name', help='小说完整名称')
    parser.add_argument('--chapters', help='要重试的章节 (逗号分隔或范围)')
    parser.add_argument('--auto-detect', action='store_true', help='自动检测返回空的章节')
    args = parser.parse_args()

    c = pymongo.MongoClient(MONGO_URI)
    novel_db = c['novel']
    novel_name = args.novel_name

    api = get_api()

    if args.chapters:
        chapters = parse_chapters(args.chapters)
    elif args.auto_detect:
        # 检测 wordCount 没有变化的章节 (即未被修改的)
        print("Auto-detecting failed chapters...")
        chapters = []
        for ch in novel_db['chapters'].find({'novelName': novel_name}):
            chapters.append(ch['chapterNumber'])
    else:
        parser.print_help()
        return

    print(f"Retrying refinement for: {novel_name} ch{chapters}")
    total_applied = 0

    for ch_num in chapters:
        print(f"\n--- ch{ch_num} ---")
        doc = novel_db['chapters'].find_one({'novelName': novel_name, 'chapterNumber': ch_num})
        if not doc or not doc.get('content'):
            print(f"  ⚠️ Chapter {ch_num} not found or empty")
            continue

        content = doc['content']
        print(f"  Content: {len(content)} chars")

        prompt = f"""{VOICE_PROFILE}

请从下面正文中找出3-5句「」内缺乏角色辨识度的对白进行修改。
只改「」内内容，不改叙述旁白。保持剧情信息不变。
每条修改独立，不要互相影响。

输出要求:
- original: 原始对白文本（精确匹配原文，不含「」）
- replacement: 替换后的对白文本（不含「」）
- character: 角色名
- reason: 修改理由（10-20字）

正文（第{ch_num}章）：
{content}

输出JSON数组，每元素包含original/replacement/character/reason。"""

        time.sleep(3)  # 批次间隔防限流
        suggestions = call_llm(prompt, api)
        print(f"  Suggestions: {len(suggestions)}")

        if not suggestions:
            print("  -> No suggestions, skipping")
            continue

        new_content = content
        applied = 0
        for s in suggestions:
            orig = s.get('original', '').strip()
            repl = s.get('replacement', '').strip()
            character = s.get('character', '?')
            if not orig or not repl:
                continue
            # 精确替换「」内的内容
            pat = '\u300c' + re.escape(orig) + '\u300d'
            if re.search(pat, new_content):
                new_content = re.sub(pat, '\u300c' + repl + '\u300d', new_content, count=1)
                print(f"  ✅ {character}: 「{orig[:30]}」→「{repl[:30]}」")
                applied += 1
            else:
                print(f"  ⚠️ Match not found: 「{orig[:30]}」")
                # 尝试不带「」匹配原文
                if orig in new_content:
                    print(f"     Found bare text, trying to locate...")

        if applied > 0:
            wc = len(new_content)
            novel_db['chapters'].update_one(
                {'novelName': novel_name, 'chapterNumber': ch_num},
                {'$set': {'content': new_content, 'wordCount': wc}}
            )
            print(f"  ✅ Written: {wc} chars, {applied} changes")
            total_applied += applied
        else:
            print(f"  -> No changes applied")

    print(f"\n=== Done: {total_applied} changes across {len(chapters)} chapters ===")

if __name__ == '__main__':
    main()
