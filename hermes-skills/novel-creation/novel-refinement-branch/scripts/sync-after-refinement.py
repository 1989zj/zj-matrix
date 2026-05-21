#!/usr/bin/env python3
"""
精修合并同步脚本 — 在 refinement patch 应用后执行。

用法:
    python3 sync-after-refinement.py <小说名> --chapters 1,2,3
    python3 sync-after-refinement.py <小说名> --chapters 1-3 --merge
    python3 sync-after-refinement.py <小说名> --chapters 1-3 --merge --llm-hooks

参数:
    --chapters    要同步的章节 (逗号分隔或连字符范围)
    --pid         项目ID (可选，自动从 projects 集合获取)
    --merge       标记为已合并 (设置 status=merged + 写 refinement_log)
    --llm-hooks   使用 LLM 生成章末钩子（比启发式截取更好，详见下文）
    --dry-run     只预览，不写入

LLM 钩子说明:
    启发式 extract_hook() 从尾200字截取最后一句话，结果可能过短（实测 ch2 仅9字, ch3 仅8字）。
    --llm-hooks 模式用 DeepSeek v4 Flash 为每章生成 30-80 字的悬念式钩子，
    效果显著提升（54字/46字 vs 9字/8字），但需要 API 调用，每章 ~2 秒。

功能:
    1. 从 novel.chapters 读取最新内容
    2. 更新 novel_factory.chapter_memory (summary + hook + last_refined)
    3. 修正 wordCount 字段
    4. --merge 时标记 status=merged + 写入 refinement_log
"""
import pymongo
import argparse
import os
import yaml
from datetime import datetime, timezone

MONGO_URI = 'mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin'


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


def extract_summary_heuristic(content: str, max_len: int = 150) -> str:
    return content[:max_len].strip() + ('...' if len(content) > max_len else '')


def extract_hook_heuristic(content: str, max_len: int = 100) -> str:
    tail = content[-200:].strip()
    for sep in ['\n\n', '\n', '。', '！', '？']:
        parts = tail.split(sep)
        if len(parts) > 1:
            candidate = parts[-1].strip()
            if 5 < len(candidate) <= max_len:
                return candidate
    return tail[:max_len] + ('...' if len(tail) > max_len else '')


def extract_hook_llm(content: str, ch_num: int, client=None) -> str:
    """用 LLM 生成章末钩子，比启发式截取更简洁有力。"""
    tail = content[-600:]
    try:
        resp = client.chat.completions.create(
            model='deepseek-v4-flash',
            messages=[
                {'role': 'system', 'content': '你是一名专业的中国网络小说编辑，擅长提炼章末钩子。输出只有钩子内容，不要解释不要引号。'},
                {'role': 'user', 'content': f'这是第{ch_num}章的结尾内容，请提炼一句章末钩子（30-80字，保留悬念，不剧透后续，无限流·规则怪谈风格）：\n\n{tail}'}
            ],
            temperature=0.7,
            max_tokens=200
        )
        hook = resp.choices[0].message.content.strip().strip('"\u201c\u201d\u300c\u300d')
        if 10 <= len(hook) <= 120:
            return hook
    except Exception as e:
        print(f'  LLM hook 生成失败 (ch{ch_num}): {e}')
    return extract_hook_heuristic(content)


def get_llm_client():
    """从 Hermes 配置初始化 LLM 客户端"""
    with open(os.path.expanduser('~/.hermes/config.yaml')) as f:
        cfg = yaml.safe_load(f)
    api_key = None
    base_url = None
    for prov in cfg.get('custom_providers', []):
        if 'deepseek' in prov.get('base_url', '').lower():
            api_key = prov['api_key']
            base_url = prov['base_url']
            break
    if not api_key:
        api_key = cfg['model'].get('api_key')
        base_url = cfg['model'].get('base_url', 'https://api.deepseek.com')
    if not api_key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=base_url)


def get_project_id(nf, name: str, chapters: list[int]) -> str | None:
    proj = nf['projects'].find_one({'title': {'$regex': name[:4]}})
    if proj and 'project_id' in proj:
        return proj['project_id']
    cm = nf['chapter_memory'].find_one({'chapter': {'$in': chapters}})
    if cm and 'project_id' in cm:
        return cm['project_id']
    return None


def main():
    parser = argparse.ArgumentParser(description='同步精修后章节到数据库')
    parser.add_argument('novel_name', help='小说名')
    parser.add_argument('--chapters', required=True, help='章节范围: 1,2,3 或 1-5')
    parser.add_argument('--pid', help='项目ID（可选，自动获取）')
    parser.add_argument('--merge', action='store_true', help='标记为已合并')
    parser.add_argument('--llm-hooks', action='store_true', help='用 LLM 生成钩子（而非启发式）')
    parser.add_argument('--dry-run', action='store_true', help='只预览不写入')
    args = parser.parse_args()

    chapters = parse_chapters(args.chapters)
    print(f'小说: {args.novel_name}')
    print(f'章节: ch{chapters[0]}-ch{chapters[-1]} ({len(chapters)} 章)')
    print(f'钩子: {"LLM 生成" if args.llm_hooks else "启发式截取"}')
    print(f'模式: {"DRY RUN" if args.dry_run else "执行"}')
    if args.merge:
        print('标记: 合并 (status=merged + refinement_log)')

    c = pymongo.MongoClient(MONGO_URI)
    novel_db = c['novel']
    nf = c['novel_factory']

    pid = args.pid or get_project_id(nf, args.novel_name, chapters)
    if not pid:
        print('错误: 无法确定 project_id，请用 --pid 指定')
        return
    print(f'项目ID: {pid}')

    chapters_data = {}
    for ch in novel_db['chapters'].find(
        {'novelName': args.novel_name, 'chapterNumber': {'$in': chapters}}
    ).sort('chapterNumber', 1):
        chapters_data[ch['chapterNumber']] = ch

    found = list(chapters_data.keys())
    missing = [c for c in chapters if c not in found]
    print(f'找到 {len(found)} 章, 缺失 {len(missing) if missing else 0} 章')
    if missing:
        print(f'缺失章节: ch{missing}')

    llm_client = None
    if args.llm_hooks:
        llm_client = get_llm_client()
        if not llm_client:
            print('警告: 无法初始化 LLM 客户端，回退到启发式钩子')

    now = datetime.now(timezone.utc)
    stats = {'summary_updated': 0, 'wc_fixed': 0, 'words_total': 0}

    for ch_num in found:
        ch = chapters_data[ch_num]
        content = ch.get('content', '')
        if not content:
            continue

        current_wc = len(content)
        stored_wc = ch.get('wordCount', 0)
        has_wc_drift = current_wc != stored_wc

        new_summary = extract_summary_heuristic(content)
        if args.llm_hooks and llm_client:
            new_hook = extract_hook_llm(content, ch_num, llm_client)
        else:
            new_hook = extract_hook_heuristic(content)

        update = {
            'summary': new_summary,
            'hook': new_hook,
            'last_refined': now,
        }
        if args.merge:
            update['status'] = 'merged'
            update['merged_at'] = now

        if not args.dry_run:
            nf['chapter_memory'].update_one(
                {'project_id': pid, 'chapter': ch_num},
                {'$set': update}
            )
            if has_wc_drift:
                novel_db['chapters'].update_one(
                    {'_id': ch['_id']},
                    {'$set': {'wordCount': current_wc}}
                )

        drift_info = f' [wc: {stored_wc} -> {current_wc}]' if has_wc_drift else ''
        hook_label = new_hook[:50] + '...' if len(new_hook) > 50 else new_hook
        print(f'  ch{ch_num}: {current_wc}字, summary={len(new_summary)}字, hook={len(new_hook)}字 "{hook_label}"{drift_info}')
        stats['words_total'] += current_wc
        stats['summary_updated'] += 1
        if has_wc_drift:
            stats['wc_fixed'] += 1

    if args.merge and not args.dry_run:
        if 'refinement_log' not in nf.list_collection_names():
            nf.create_collection('refinement_log')
        nf['refinement_log'].insert_one({
            'project_id': pid,
            'chapters': found,
            'action': 'merge',
            'merged_at': now,
            'details': f'合并同步: ch{found[0]}-ch{found[-1]} ({len(found)}章, {stats["words_total"]}字)'
        })
        print(f'  -> refinement_log 写入')

    print(f'\n完成: {stats["summary_updated"]} 章同步, {stats["wc_fixed"]} 处字数修正, 合计 {stats["words_total"]} 字')
    if args.llm_hooks:
        print('  钩子由 LLM 生成，质量优于启发式截取。如某章钩子过短，可单独用 LLM 重试。')


if __name__ == '__main__':
    main()
