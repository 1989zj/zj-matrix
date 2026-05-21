#!/usr/bin/env python3
"""
retry-refine.py — 对话声音精修重试脚本
用于 dialogue-voice-refiner.py 对某章 API 调用失败时的重试。

用法:
    python3 retry-refine.py <小说名> --chapters 12,14,15
    python3 retry-refine.py '诡异游戏：我的规则别人看不见' --chapters 19

特点:
    - 更轻量的 prompt，减少 API 超时
    - 对每一章执行重试（3 秒间隔）
    - 直接写入 MongoDB
"""

import json, urllib.request, pymongo, yaml, os, re, sys, time

MONGO_URI = 'mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/novel?authSource=admin'

NOVEL_NAME = None
CHAPTERS = []

def parse_args():
    global NOVEL_NAME, CHAPTERS
    if len(sys.argv) < 2:
        print("用法: python3 retry-refine.py <小说名> --chapters 12,14,15")
        sys.exit(1)
    NOVEL_NAME = sys.argv[1]
    for i, arg in enumerate(sys.argv):
        if arg == '--chapters' and i + 1 < len(sys.argv):
            for part in sys.argv[i+1].split(','):
                part = part.strip()
                if '-' in part:
                    a, b = part.split('-', 1)
                    CHAPTERS.extend(range(int(a), int(b)+1))
                else:
                    CHAPTERS.append(int(part))
    CHAPTERS = sorted(set(CHAPTERS))
    if not CHAPTERS:
        print("❌ 请指定 --chapters")
        sys.exit(1)


def get_api(provider_name='deepseek'):
    with open(os.path.expanduser('~/.hermes/config.yaml')) as f:
        cfg = yaml.safe_load(f)
    for prov in cfg.get('custom_providers', []):
        if provider_name.lower() in prov.get('name','').lower():
            return {
                'api_key': prov['api_key'],
                'base_url': prov.get('base_url', 'https://api.deepseek.com'),
                'model': prov.get('model', 'deepseek-chat')
            }
    return None


def call_llm(prompt, api):
    url = api['base_url'].rstrip('/') + '/v1/chat/completions'
    data = json.dumps({
        'model': api['model'],
        'messages': [
            {'role': 'system', 'content': '你是一位专业的小说精修编辑。只返回JSON数组。'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.5,
        'max_tokens': 3000
    }).encode()
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + api['api_key']
    })
    try:
        resp = urllib.request.urlopen(req, timeout=90)
        result = json.loads(resp.read())
        content = result['choices'][0]['message']['content']
        # 尝试从 markdown 代码块提取 JSON
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            return json.loads(json_match.group(1))
        # 尝试直接提取数组
        json_match = re.search(r'\[[\s\S]*?\]', content)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(content)
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return []


def main():
    parse_args()
    api = get_api('deepseek')
    if not api:
        print("❌ 找不到 DeepSeek API 配置")
        sys.exit(1)

    c = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    db = c['novel']

    total_applied = 0
    for ch_num in CHAPTERS:
        doc = db['chapters'].find_one({'novelName': NOVEL_NAME, 'chapterNumber': ch_num})
        if not doc:
            print(f"  ❌ ch{ch_num}: 未找到")
            continue

        content = doc['content']
        print(f"  ch{ch_num}: {len(content)}字 ... ", end='')

        time.sleep(3)  # 节流

        prompt = f'''角色声音：
- 林远：直接短促果断，从不拖泥带水
- 顾晚：话少、准确、结论先行
- 周文：学术严谨、提问驱动
- 刘闯：短句、口语化、接地气
- 赵铁：短准汇报风
- 方晴：提问型对话，爱追问
- 老钱：沉稳啰嗦，爱总结

从下面正文中找出 3-5 句「」内缺乏角色辨识度的对白进行修改。
只改「」内内容，不改叙述旁白。保持剧情信息不变。
原始文本必须在原文中能找到。

正文（第{ch_num}章）：
{content}

输出 JSON 数组，每个元素：
- original: 原始对白文本（精确到字，不含「」）
- replacement: 替换后的对白文本（不含「」）
- character: 角色名
- reason: 修改理由（10-20 字）'''

        suggestions = call_llm(prompt, api)
        if not suggestions:
            print("0 处修改 (无建议)")
            continue

        new_content = content
        count = 0
        for s in suggestions:
            orig = s.get('original', '').strip()
            repl = s.get('replacement', '').strip()
            char = s.get('character', '?')
            if not orig or not repl:
                continue
            # 精确替换「原始」
            pat = '\u300c' + re.escape(orig) + '\u300d'
            if re.search(pat, new_content):
                new_content = re.sub(pat, '\u300c' + repl + '\u300d', new_content, count=1)
                count += 1
                print(f"    {char}: 「{orig[:25]}」→「{repl[:25]}」")

        if count > 0:
            wc = len(new_content)
            db['chapters'].update_one(
                {'novelName': NOVEL_NAME, 'chapterNumber': ch_num},
                {'$set': {'content': new_content, 'wordCount': wc}}
            )
            total_applied += count
            print(f"  -> ✅ {count}处修改 ({wc}字)")
        else:
            print(f"  -> 0 处修改 (匹配失败)")

    print(f"\n总计: {total_applied} 处修改")
    c.close()


if __name__ == '__main__':
    main()
