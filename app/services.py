import os
from pymongo import ASCENDING
from app.db import novels_col, chapters_col, settings_col
from app.constants import ORDER_TYPES

def _format_world_settings(world):
    """将 MongoDB 的 world dict 转为模板需要的 world_settings 数组格式"""
    if not world:
        return []
    sections = []

    # 力量体系
    if 'power_system' in world:
        ps = world['power_system']
        lines = []
        if ps.get('name'):
            lines.append(f"体系名称：{ps['name']}")
        if ps.get('levels'):
            lines.append(f"等级划分：{ps['levels']}")
        if ps.get('source'):
            lines.append(f"能量来源：{ps['source']}")
        if ps.get('note'):
            lines.append(f"补充设定：{ps['note']}")
        sections.append({'title': '力量体系', 'content': '<br>'.join(lines)})

    # 时间线
    if 'timeline' in world:
        items = []
        for k, v in sorted(world['timeline'].items()):
            label = k.replace('_', ' → ')
            items.append(f"<b>{label}</b>：{v}")
        sections.append({'title': '故事时间线', 'content': items})

    # 势力分布
    if 'factions' in world:
        items = [f"<b>{name}</b>：{desc}" for name, desc in world['factions'].items()]
        sections.append({'title': '势力分布', 'content': items})

    # 威胁层级
    if 'threats' in world:
        sections.append({'title': '威胁与结局', 'content': world['threats']})

    return sections


def get_novel_meta(name):
    doc = novels_col.find_one({'name': name}, {'_id': 0})
    if doc and 'world' in doc:
        doc['world_settings'] = _format_world_settings(doc['world'])
    return doc

def slug_to_name(slug):
    doc = novels_col.find_one({'slug': slug}, {'name': 1, '_id': 0})
    return doc['name'] if doc else None

def get_novel_stats(novel_name):
    """从MongoDB获取小说统计数据"""
    chapters = list(chapters_col.find(
        {"novelName": novel_name},
        {'_id': 0, 'content': 0}
    ).sort("chapterNumber", ASCENDING))

    total_words = sum(c.get('wordCount', 0) for c in chapters)

    chapter_data = [
        {
            'title': c.get('title', ''),
            'num': c.get('chapterNumber', 0),
            'content': c.get('content', ''),
            'words': c.get('wordCount', 0),
            'filename': c.get('filename', ''),
            'path': c.get('filename', '')
        }
        for c in chapters
    ]

    return {
        'count': len(chapter_data),
        'words': total_words,
        'chapters': chapter_data
    }

def get_chapter_content(novel_name, chapter_number):
    """获取单章完整内容"""
    doc = chapters_col.find_one(
        {"novelName": novel_name, "chapterNumber": chapter_number},
        {'_id': 0}
    )
    if not doc:
        return None
    return {
        'title': doc.get('title', ''),
        'num': doc.get('chapterNumber', 0),
        'content': doc.get('content', ''),
        'words': doc.get('wordCount', 0),
        'filename': doc.get('filename', ''),
        'path': doc.get('filename', ''),
        'chapterEndNotes': doc.get('chapterEndNotes', ''),
        'version': doc.get('version', 'v1'),
        'versions': doc.get('versions', [])
    }

def get_order_prices():
    """从settings获取定价，没有则用默认值"""
    doc = settings_col.find_one({'_id': 'order_prices'})
    if doc and 'prices' in doc:
        return doc['prices']
    return dict(ORDER_TYPES)

def save_order_prices(prices):
    """保存定价到settings"""
    settings_col.update_one(
        {'_id': 'order_prices'},
        {'$set': {'prices': prices}},
        upsert=True
    )
