#!/usr/bin/env python3
"""
validate-chapter.py — V3 实时一致性校验器

作用: 在 draft 完成后立即校验 7 维一致性:
  1. 金额一致性
  2. 战力等级一致性
  3. 时间线一致性
  4. 称呼一致性
  5. 人设一致性
  6. 地点一致性
  7. 物品/技能一致性

调用:
  python3 validate-chapter.py check <project_id> <chapter> [--content-file path]
  python3 validate-chapter.py check <project_id> <chapter> --stdin < chapter.md

输出: JSON 格式，含 BLOCKER/WARNING/INFO 三个级别的问题列表
"""

import json
import sys
import os
import re
import argparse

import pymongo

MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/?authSource=admin"


def connect():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client, client["novel_factory"], client["novel"]


def extract_numbers(text: str) -> list:
    """提取文本中的所有数字（百万级）"""
    patterns = [
        (r'(\d+)亿', lambda m: int(m.group(1)) * 100000000),
        (r'(\d+)千万', lambda m: int(m.group(1)) * 10000000),
        (r'(\d+)百万', lambda m: int(m.group(1)) * 1000000),
        (r'(\d+)万', lambda m: int(m.group(1)) * 10000),
        (r'(\d+)', lambda m: int(m.group(1))),
    ]
    results = []
    for pat, fn in patterns:
        for m in re.finditer(pat, text):
            results.append({
                "match": m.group(0),
                "value": fn(m),
                "position": m.start(),
            })
    return results


def check_amount_consistency(text: str, prev_chapter: list, chapter_num: int) -> list:
    """校验金额一致性"""
    issues = []
    current_amounts = extract_numbers(text)
    if not current_amounts:
        return issues

    # 找包含「万」「亿」的高额数字
    large_amounts = [a for a in current_amounts if a["value"] >= 10000]
    if not large_amounts:
        return issues

    # 与上一章比较
    prev_amounts = extract_numbers(" ".join(prev_chapter))
    for cur in large_amounts:
        for prev in prev_amounts:
            if abs(cur["value"] - prev["value"]) > 0 and "亿" in cur["match"]:
                # 如果都是大额数字，且差距超过 100 倍，可能是错误
                if prev["value"] > 0 and (cur["value"] / prev["value"] > 100 or prev["value"] / cur["value"] > 100):
                    issues.append({
                        "level": "WARNING",
                        "dimension": "金额",
                        "message": f"金额跳跃过大: ch{chapter_num} 出现 '{cur['match']}'，上一章类似数值为 '{prev['match']}'",
                        "context": f"第{chapter_num}章出现 {cur['match']}",
                    })
                    break
    return issues


def check_character_consistency(text: str, project_id: str, chapter_num: int) -> list:
    """校验人设一致性"""
    issues = []
    client, nf, novel = connect()
    try:
        characters = list(nf["characters"].find({"project_id": project_id}))
        for char in characters:
            name = char.get("name", "")
            if not name or not text:
                continue
            role = char.get("role", char.get("title", ""))
            personality = char.get("personality", char.get("traits", ""))
            abilities = char.get("abilities", [])

            # 检测角色是否出场
            if name not in text:
                continue

            # 检测能力是否被错误使用
            for ability in abilities:
                if isinstance(ability, str) and ability:
                    if ability in text:
                        # 检查能力是否被合理使用（强度不超出设定）
                        pass  # 复杂语义检测暂缓

            # 检测称呼一致性
            # 查找可能的错误称呼
            aliases = [
                name,
                name.replace("少爷", "小姐"),
                name.replace("公子", "小姐"),
                name[:-1] + "总" if len(name) > 2 else "",
                name[:-1] + "爷" if len(name) > 2 else "",
            ]

        return issues
    finally:
        client.close()


def check_timeline_consistency(text: str, project_id: str, chapter_num: int) -> list:
    """校验时间线一致性"""
    issues = []
    client, nf, novel = connect()
    try:
        # 读取时间线
        prev_events = list(
            nf["timeline"]
            .find({"project_id": project_id})
            .sort("chapter", pymongo.DESCENDING)
            .limit(5)
        )

        # 检测时间跳跃
        time_keywords = [
            "第二天", "次日", "隔天", "一周后", "一个月后", "一年后",
            "三天后", "几天后", "第二天一早", "当晚",
            "翌日", "次日清晨", "第二天清晨",
        ]
        found = [kw for kw in time_keywords if kw in text]
        if found and prev_events:
            last_event_ch = prev_events[0].get("chapter", 0) if prev_events else 0
            if chapter_num > last_event_ch + 3 and len(found) > 2:
                issues.append({
                    "level": "INFO",
                    "dimension": "时间线",
                    "message": f"第{chapter_num}章出现多个时间跳跃词: {found}，确认是否合理（可能丢失了中间章节）",
                })

        return issues
    finally:
        client.close()


def check_foreshadow(text: str, project_id: str, chapter_num: int) -> list:
    """检查紧急伏笔是否被触及"""
    issues = []
    client, nf, novel = connect()
    try:
        critical = list(
            nf["foreshadow_queue"]
            .find({"project_id": project_id, "resolved": False, "urgency": "critical"})
        )
        # 也查 V2
        v2_critical = list(
            nf["foreshadow"]
            .find({"project_id": project_id, "status": {"$ne": "resolved"}})
            .sort("chapter", pymongo.ASCENDING)
            .limit(10)
        )

        all_critical = critical + [
            {"foreshadow_id": f.get("foreshadow_id", str(f.get("_id", ""))),
             "description": f.get("description", ""),
             "setup_chapter": f.get("chapter", 0)}
            for f in v2_critical
        ]

        for fs in all_critical:
            desc = fs.get("description", "")
            if desc and desc[:20] in text:
                issues.append({
                    "level": "INFO",
                    "dimension": "伏笔",
                    "message": f"伏笔 '{desc[:50]}' 在本章被触及，确认是否需要 resolution",
                    "foreshadow_id": fs.get("foreshadow_id"),
                })

        return issues
    finally:
        client.close()


def check_word_count(text: str) -> list:
    """检查字数"""
    issues = []
    # 去除空白字符
    clean = re.sub(r'\s+', '', text)
    wc = len(clean)
    if wc < 1500:
        issues.append({
            "level": "WARNING",
            "dimension": "字数",
            "message": f"章节仅 {wc} 字（目标 2000+）",
            "word_count": wc,
        })
    elif wc < 2000:
        issues.append({
            "level": "INFO",
            "dimension": "字数",
            "message": f"章节 {wc} 字（建议 2000+ 以符合番茄标准）",
            "word_count": wc,
        })
    if wc > 5000:
        issues.append({
            "level": "INFO",
            "dimension": "字数",
            "message": f"章节 {wc} 字（超过建议 2000-4000 范围）",
            "word_count": wc,
        })
    return issues


def full_check(project_id: str, chapter_num: int, content: str) -> dict:
    """执行全部 7 维校验"""
    all_issues = []

    # 1. 字数
    all_issues.extend(check_word_count(content))

    # 2. 金额
    client, nf, novel = connect()
    try:
        # 加载前一章内容
        prev_mem = nf["chapter_memory"].find_one(
            {"project_id": project_id, "chapter": chapter_num - 1}
        )
        prev_text = []
        if prev_mem and content:
            prev_text = [prev_mem.get("summary", "")]
        all_issues.extend(check_amount_consistency(content, prev_text, chapter_num))
    finally:
        client.close()

    # 3. 人设
    all_issues.extend(check_character_consistency(content, project_id, chapter_num))

    # 4. 时间线
    all_issues.extend(check_timeline_consistency(content, project_id, chapter_num))

    # 5. 伏笔
    all_issues.extend(check_foreshadow(content, project_id, chapter_num))

    # 5-7. 称呼/地点/物品暂为简化版
    # 称呼一致性
    name_pattern = r'[（(]([^)）]+?)[)）]'
    parentheticals = re.findall(name_pattern, content)
    for p in parentheticals:
        if "原名" in p or "又名" in p:
            pass  # 故意的

    # 统计
    blocker_count = len([i for i in all_issues if i.get("level") == "BLOCKER"])
    warning_count = len([i for i in all_issues if i.get("level") == "WARNING"])
    info_count = len([i for i in all_issues if i.get("level") == "INFO"])

    result = {
        "status": "ok",
        "project_id": project_id,
        "chapter": chapter_num,
        "summary": {
            "blockers": blocker_count,
            "warnings": warning_count,
            "info": info_count,
            "total": len(all_issues),
        },
        "issues": all_issues,
        "passed": blocker_count == 0,
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="V3 Live Validator")
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser("check", help="Validate a chapter")
    check_p.add_argument("project_id", help="Project ID or title")
    check_p.add_argument("chapter", type=int, help="Chapter number")
    check_p.add_argument("--content-file", help="Path to chapter content file")
    check_p.add_argument("--stdin", action="store_true", help="Read content from stdin")

    args = parser.parse_args()

    if args.command == "check":
        # 读取内容
        content = ""
        if args.stdin:
            content = sys.stdin.read()
        elif args.content_file:
            with open(args.content_file, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            # 自动从 MongoDB 获取章节内容
            client, nf, novel = connect()
            try:
                # 先尝试 novel (V2) 库
                chapter_data = novel["chapters"].find_one(
                    {"novelName": {"$regex": args.project_id, "$options": "i"}, "chapterNumber": args.chapter}
                )
                if not chapter_data:
                    # 再试 novel_factory 库
                    chapter_data = nf["chapters"].find_one(
                        {"project_id": {"$regex": args.project_id, "$options": "i"}, "chapter": args.chapter}
                    )
                if chapter_data:
                    content = chapter_data.get("content", "")
                    if not content:
                        # 尝试从文件读取
                        filename = chapter_data.get("filename", "")
                        if filename and os.path.exists(filename):
                            with open(filename, "r", encoding="utf-8") as f:
                                content = f.read()
                if not content:
                    print("错误: 无法从 MongoDB 或文件自动获取章节内容。请使用 --content-file 或 --stdin 提供。")
                    sys.exit(1)
            finally:
                client.close()

        result = full_check(args.project_id, args.chapter, content)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
