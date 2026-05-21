import os
from pymongo import ASCENDING
from app.db import db, novels_col, chapters_col, settings_col

def _format_world_settings(world):
    """将 MongoDB 的 world_bible 转为模板需要的 world_settings 数组格式"""
    if not world:
        return []
    sections = []

    # 力量体系 (novel_factory stores it as an array)
    if 'power_system' in world and world['power_system']:
        ps_list = world['power_system']
        if isinstance(ps_list, list) and len(ps_list) > 0:
            ps = ps_list[0] # Take the first one for now
            items = []
            if ps.get('name'):
                items.append({'label': '体系名称', 'value': ps['name']})
            if ps.get('levels'):
                items.append({'label': '等级划分', 'value': ps['levels']})
            if ps.get('source'):
                items.append({'label': '能量来源', 'value': ps['source']})
            if ps.get('note'):
                items.append({'label': '补充设定', 'value': ps['note']})
            sections.append({'title': '力量体系', 'content': items})

    # 势力分布 (novel_factory stores it as an array of objects {name, desc})
    if 'factions' in world:
        items = []
        if isinstance(world['factions'], list):
            items = [{'label': f.get('name', ''), 'value': f.get('desc', '')} for f in world['factions']]
        elif isinstance(world['factions'], dict):
            items = [{'label': name, 'value': desc} for name, desc in world['factions'].items()]
        
        if items:
            sections.append({'title': '势力分布', 'content': items})

    # 威胁层级 / 禁忌规则
    if 'forbidden_rules' in world:
        content = world['forbidden_rules']
        if content:
            items = [{'label': f'规则 {i+1}', 'value': v} for i, v in enumerate(content)]
            sections.append({'title': '禁忌与规则', 'content': items})

    return sections


def get_novel_meta(project_id):
    doc = novels_col.find_one({'project_id': project_id}, {'_id': 0})
    if doc:
        # Load world bible
        world_doc = db['world_bible'].find_one({'project_id': project_id})
        if world_doc:
            doc['world'] = world_doc
            doc['world_settings'] = _format_world_settings(world_doc)
        
        # Load characters
        doc['characters'] = list(db['characters'].find({'project_id': project_id}, {'_id': 0}))
        for char in doc['characters']:
            # Compatibility fields
            char['desc'] = char.get('memory_summary') or char.get('role') or ''
            char['traits'] = char.get('personality') or []
            if 'abilities' in char and char['abilities']:
                char['ability'] = char['abilities'][0]
        
        # Load timeline
        doc['timeline'] = list(db['timeline'].find({'project_id': project_id}, {'_id': 0}).sort('chapter', 1))
        
        # Compatibility fields for templates
        doc['name'] = doc['project_id']
        doc['stats'] = {
            'words': doc.get('total_words', 0),
            'chapters': doc.get('total_chapters', 0)
        }
    return doc

def slug_to_name(slug):
    doc = novels_col.find_one({'slug': slug}, {'project_id': 1, '_id': 0})
    return doc['project_id'] if doc else None

def get_novel_stats(project_id):
    """从MongoDB获取小说统计数据 (novel_factory 结构)"""
    chapters = list(chapters_col.find(
        {"project_id": project_id},
        {'_id': 0, 'content': 0}
    ).sort("chapter", ASCENDING))

    total_words = sum(c.get('word_count', 0) for c in chapters)

    chapter_data = [
        {
            'title': c.get('title', ''),
            'num': c.get('chapter', 0),
            'content': c.get('content', ''),
            'words': c.get('word_count', 0),
            'filename': c.get('filename', ''), # Legacy field
            'path': c.get('filename', '')      # Legacy field
        }
        for c in chapters
    ]

    return {
        'count': len(chapter_data),
        'words': total_words,
        'chapters': chapter_data
    }

def get_chapter_content(project_id, chapter_number):
    """获取单章完整内容 (novel_factory 结构)"""
    doc = chapters_col.find_one(
        {"project_id": project_id, "chapter": chapter_number},
        {'_id': 0}
    )
    if not doc:
        return None
    return {
        'title': doc.get('title', ''),
        'num': doc.get('chapter', 0),
        'content': doc.get('content', ''),
        'words': doc.get('word_count', 0),
        'filename': doc.get('filename', ''),
        'chapterEndNotes': doc.get('chapter_end_notes', ''),
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
