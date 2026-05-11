import os
from flask import Blueprint, render_template, abort, send_from_directory, request
from app.decorators import admin_required, login_required
from app.db import novels_col, chapters_col
from app.services import get_novel_meta, slug_to_name, get_novel_stats, get_chapter_content

novel_bp = Blueprint('novel', __name__)

@novel_bp.route('/')
@admin_required
def index():
    novels = []
    for doc in novels_col.find({}, {'_id': 0}):
        name = doc['name']
        ch_count = chapters_col.count_documents({"novelName": name})
        if ch_count == 0:
            continue
        stats = get_novel_stats(name)
        doc['stats']['words'] = stats['words']
        doc['stats']['chapters'] = stats['count']
        novels.append({
            'name': name,
            'meta': doc,
            'slug': doc['slug']
        })
    return render_template('index.html', novels=novels)

@novel_bp.route('/api/upload-chapter', methods=['POST'])
@login_required
def upload_chapter():
    data = request.get_json()
    if not data or 'novelName' not in data or 'chapterNumber' not in data or 'content' not in data:
        return {"error": "missing fields"}, 400
    novel_name = data['novelName']
    chapter_num = int(data['chapterNumber'])
    content = data['content']
    title = data.get('title', '')
    filename = data.get('filename', '')
    chapter_end_notes = data.get('chapterEndNotes', '')
    version = data.get('version', 'v1')
    word_count = data.get('wordCount', len(content.replace(' ', '').replace('\n', '')))

    # ── 自动分离章尾说明 ──
    if not chapter_end_notes:
        markers = ['【本章钩子', '【本章爽点', '【本章节奏', '【情绪浓度', '【本章字数',
                   '【本章悬念', '【本章看点', '【本章信息', '【本章伏笔', '【本章高潮',
                   '【本章坑', '【本章金句', '【本章总结']
        lines = content.split('\n')
        sep_lines = []
        for i in range(len(lines) - 1, -1, -1):
            stripped = lines[i].strip()
            is_marker = any(stripped.startswith(m) for m in markers)
            is_empty = stripped == ''
            is_sep = stripped.startswith('---')
            if is_marker or is_empty or is_sep:
                sep_lines.insert(0, lines[i])
            else:
                break
        if sep_lines and any(stripped.startswith(m) for m in markers
                              for stripped in [s.strip() for s in sep_lines]):
            chapter_end_notes = '\n'.join(sep_lines).strip()
            content = '\n'.join(lines[:len(lines) - len(sep_lines)]).strip()
    chapters_col.delete_many({"novelName": novel_name, "chapterNumber": chapter_num})
    doc = {
        "novelName": novel_name,
        "chapterNumber": chapter_num,
        "title": title,
        "filename": filename,
        "content": content,
        "chapterEndNotes": chapter_end_notes,
        "version": version,
        "wordCount": word_count
    }
    chapters_col.insert_one(doc)
    return {"success": True, "chapter": chapter_num, "words": word_count}


@novel_bp.route('/novel/<slug>/')
@admin_required
def novel_detail(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    stats = get_novel_stats(name)
    meta['stats']['words'] = stats['words']
    meta['stats']['chapters'] = stats['count']
    return render_template('novel.html', novel_name=name, meta=meta, slug=slug)

@novel_bp.route('/novel/<slug>/chapters/')
@admin_required
def chapter_list(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    stats = get_novel_stats(name)
    return render_template('chapters.html', novel_name=name, meta=meta,
                           chapters=stats['chapters'], slug=slug)

@novel_bp.route('/novel/<slug>/chapter/<int:num>/')
@admin_required
def chapter_read(slug, num):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)

    stats = get_novel_stats(name)
    target = get_chapter_content(name, num)
    if not target:
        abort(404)

    chapter_data_list = stats['chapters']
    idx = next(i for i, c in enumerate(chapter_data_list) if c['num'] == num)
    prev_ch = chapter_data_list[idx - 1] if idx > 0 else None
    next_ch = chapter_data_list[idx + 1] if idx < len(chapter_data_list) - 1 else None

    return render_template('chapter.html', novel_name=name, meta=meta,
                          chapter=target, prev=prev_ch, next=next_ch, slug=slug)

@novel_bp.route('/novel/<slug>/chapter/<int:num>/edit/')
@admin_required
def chapter_edit(slug, num):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    chapter = get_chapter_content(name, num)
    # If chapter doesn't exist, we can create a blank one or handle error
    if not chapter:
        chapter = {'num': num, 'title': f'第{num}章', 'content': ''}
    
    return render_template('chapter_edit.html', slug=slug, meta=meta, chapter=chapter)

@novel_bp.route('/novel/<slug>/characters/')
@admin_required
def characters(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    return render_template('characters.html', novel_name=name, meta=meta, slug=slug)

@novel_bp.route('/novel/<slug>/world/')
@admin_required
def world_settings(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    return render_template('world.html', novel_name=name, meta=meta, slug=slug)

@novel_bp.route('/novel/<slug>/timeline/')
@admin_required
def timeline(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    return render_template('timeline.html', novel_name=name, meta=meta, slug=slug)

@novel_bp.route('/downloads/')
@admin_required
def download_index():
    files = []
    # Note: /root/NovelStudio might not exist on the current OS or environment.
    # We should probably make this configurable.
    base_path = '/root/NovelStudio'
    if os.path.exists(base_path):
        for f in os.listdir(base_path):
            if (f.endswith('.md') or f.endswith('.tar.gz')) and os.path.isfile(os.path.join(base_path, f)):
                size = os.path.getsize(os.path.join(base_path, f))
                files.append({'name': f, 'size': size})
    files.sort(key=lambda x: x['name'])
    return render_template('downloads.html', files=files)

@novel_bp.route('/download/<filename>')
@admin_required
def download_file(filename):
    return send_from_directory('/root/NovelStudio', filename, as_attachment=True)
