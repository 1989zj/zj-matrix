#!/usr/bin/env python3
"""NovelStudio Web - 小说阅读管理系统 (MongoDB 后端) + 订单平台 + 多租户"""
import os
import re
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, abort, redirect, url_for, send_from_directory, request, session
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '456321zj')
PRICE_PER_CHAPTER = 15  # ¥/章
# 设置 session 过期
app.permanent_session_lifetime = timedelta(days=7)

# ── MongoDB 连接 ──
MONGO_URI = "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/"
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
db = client['novel']
novels_col = db['novels']
chapters_col = db['chapters']
reports_col = db['reports']
orders_col = db['orders']
settings_col = db['settings']

# ── 订单状态流转 ──
ORDER_STATUSES = {
    'pending': '待处理',
    'confirmed': '已确认',
    'writing': '写作中',
    'review': '审核中',
    'revision': '修改中',
    'completed': '已完成',
    'cancelled': '已取消'
}

# ── 订单类型与定价 ──
ORDER_TYPES = {
    '全本新小说': 15,
    '小说续写': 12,
    '小说改写': 8,
    '小说优化': 5,
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

# ── 认证装饰器 ──
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session or 'role' not in session:
            return redirect(url_for('login_page', next=request.path))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session or 'role' not in session:
            return redirect(url_for('login_page', next=request.path))
        if session.get('role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated

# ── 上下文注入（所有模板可用）──
@app.context_processor
def inject_user():
    return {
        'current_user': session.get('user', None),
        'current_role': session.get('role', None)
    }

# ── 实时从MongoDB读取元数据 ──
def get_novel_meta(name):
    return novels_col.find_one({'name': name}, {'_id': 0})

def slug_to_name(slug):
    doc = novels_col.find_one({'slug': slug}, {'name': 1, '_id': 0})
    return doc['name'] if doc else None


def chinese_to_int(s):
    digits = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
              '六': 6, '七': 7, '八': 8, '九': 9}
    if '十' in s:
        parts = s.split('十')
        tens = digits.get(parts[0], 1) if parts[0] else 1
        ones = digits.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    return digits.get(s, 0)


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


# ── API: 上传章节 ──
@app.route('/api/upload-chapter', methods=['POST'])
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


# ── 路由: 登录/登出 ──
@app.route('/login/', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        role = request.form.get('role', 'customer')
        admin_pw = request.form.get('admin_password', '')

        if not name:
            return render_template('login.html', error='请输入姓名')

        if role == 'admin':
            if admin_pw != ADMIN_PASSWORD:
                return render_template('login.html', error='管理员密码错误')

        session.permanent = True
        session['user'] = name
        session['role'] = role

        next_url = request.args.get('next') or \
                   request.form.get('next') or ''
        if not next_url or next_url == '/':
            # 客户默认去下单页，管理员去首页
            next_url = '/orders/' if role == 'customer' else '/'
        return redirect(next_url)

    return render_template('login.html', next=request.args.get('next', ''))


@app.route('/logout/')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# ═══════════════════════════════════════════════
# 订单路由
# ═══════════════════════════════════════════════

@app.route('/orders/')
@login_required
def order_page():
    user = session['user']
    role = session['role']
    if role == 'admin':
        all_orders = list(orders_col.find({}).sort('createdAt', DESCENDING))
    else:
        all_orders = list(orders_col.find({'customerName': user}).sort('createdAt', DESCENDING))
    for o in all_orders:
        o['_id'] = str(o['_id'])
        o['statusLabel'] = ORDER_STATUSES.get(o['status'], o['status'])
    return render_template('orders.html', orders=all_orders)


@app.route('/dashboard/')
@login_required
def dashboard():
    user = session['user']
    role = session['role']
    if role == 'admin':
        all_orders = list(orders_col.find({}).sort('createdAt', DESCENDING))
    else:
        all_orders = list(orders_col.find({'customerName': user}).sort('createdAt', DESCENDING))
    for o in all_orders:
        o['_id'] = str(o['_id'])
        o['statusLabel'] = ORDER_STATUSES.get(o['status'], o['status'])
    stats = {
        'total': len(all_orders),
        'pending': sum(1 for o in all_orders if o['status'] == 'pending'),
        'writing': sum(1 for o in all_orders if o['status'] in ('writing', 'confirmed')),
        'completed': sum(1 for o in all_orders if o['status'] == 'completed'),
        'totalWords': sum(o.get('deliveredWords', 0) for o in all_orders),
        'totalChapters': sum(o.get('deliveredChapters', 0) for o in all_orders)
    }
    return render_template('dashboard.html', orders=all_orders, stats=stats,
                           ORDER_STATUSES=ORDER_STATUSES)


# ── API: 创建订单 ──
@app.route('/api/orders', methods=['POST'])
@login_required
def api_create_order():
    data = request.get_json()
    if not data:
        return {"error": "no data"}, 400
    if 'projectName' not in data or not data['projectName'].strip():
        return {"error": "missing field: projectName"}, 400
    if 'contact' not in data or not data['contact'].strip():
        return {"error": "missing field: contact"}, 400
    now = datetime.now()
    order_type = data.get('orderType', '全本新小说')
    if order_type not in ORDER_TYPES:
        order_type = '全本新小说'
    prices = get_order_prices()
    type_price = prices.get(order_type, 15)
    chapters = int(data.get('chapters', 60))
    target_words = int(data.get('targetWords', 100000))
    cost = chapters * type_price
    order = {
        'customerName': session['user'],
        'projectName': data['projectName'].strip(),
        'contact': data['contact'].strip(),
        'cost': cost,
        'orderType': order_type,
        'genre': data.get('genre', '玄幻').strip(),
        'detail': data.get('detail', '').strip(),
        'targetWords': int(data.get('targetWords', 100000)),
        'chapters': int(data.get('chapters', 60)),
        'style': data.get('style', '').strip(),
        'reference': data.get('reference', '').strip(),
        'status': 'pending',
        'progress': 0,
        'deliveredWords': 0,
        'deliveredChapters': 0,
        'notes': '',
        'deliverable': '',
        'createdAt': now,
        'updatedAt': now
    }
    result = orders_col.insert_one(order)
    return {"success": True, "id": str(result.inserted_id)}


# ── API: 更新订单状态/进度 ──
@app.route('/api/orders/<oid>', methods=['PUT'])
@login_required
def api_update_order(oid):
    try:
        obj_id = ObjectId(oid)
    except:
        return {"error": "invalid id"}, 400

    order = orders_col.find_one({'_id': obj_id})
    if not order:
        return {"error": "not found"}, 404

    # 非管理员只能更新自己的订单
    if session['role'] != 'admin' and order.get('customerName') != session['user']:
        return {"error": "forbidden"}, 403

    data = request.get_json()
    updates = {}
    if 'status' in data and data['status'] in ORDER_STATUSES:
        updates['status'] = data['status']
    if 'progress' in data:
        updates['progress'] = max(0, min(100, int(data['progress'])))
    if 'deliveredWords' in data:
        updates['deliveredWords'] = int(data['deliveredWords'])
    if 'deliveredChapters' in data:
        updates['deliveredChapters'] = int(data['deliveredChapters'])
    if 'notes' in data:
        updates['notes'] = data['notes'].strip()
    if 'deliverable' in data:
        updates['deliverable'] = data['deliverable'].strip()

    if updates:
        updates['updatedAt'] = datetime.now()
        orders_col.update_one({'_id': obj_id}, {'$set': updates})

    return {"success": True}


# ── API: 定价管理 ──
@app.route('/api/settings/prices', methods=['GET'])
@login_required
def api_get_prices():
    return {"prices": get_order_prices()}

@app.route('/api/settings/prices', methods=['PUT'])
@admin_required
def api_update_prices():
    data = request.get_json()
    if not data or 'prices' not in data:
        return {"error": "missing field: prices"}, 400
    prices = data['prices']
    # 只允许保存已定义的订单类型
    cleaned = {k: int(v) for k, v in prices.items() if k in ORDER_TYPES}
    save_order_prices(cleaned)
    return {"success": True, "prices": cleaned}


# ── 路由: 管理后台 ──
@app.route('/admin/orders/')
@admin_required
def admin_orders():
    all_orders = list(orders_col.find({}).sort('createdAt', DESCENDING))
    for o in all_orders:
        o['_id'] = str(o['_id'])
        o['statusLabel'] = ORDER_STATUSES.get(o['status'], o['status'])
    return render_template('admin_orders.html', orders=all_orders,
                           ORDER_STATUSES=ORDER_STATUSES)


@app.route('/admin/orders/<oid>/')
@admin_required
def admin_order_detail(oid):
    try:
        obj_id = ObjectId(oid)
    except:
        abort(404)
    order = orders_col.find_one({'_id': obj_id})
    if not order:
        abort(404)
    order['_id'] = str(order['_id'])
    order['statusLabel'] = ORDER_STATUSES.get(order['status'], order['status'])
    return render_template('admin_order_detail.html', order=order,
                           ORDER_STATUSES=ORDER_STATUSES)


# ── 路由: 管理设置 ──
@app.route('/admin/settings/')
@admin_required
def admin_settings():
    return render_template('admin_settings.html',
                          order_types=ORDER_TYPES,
                          prices=get_order_prices())


# ── 原有路由 ──
@app.route('/')
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


@app.route('/novel/<slug>/')
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


@app.route('/novel/<slug>/chapters/')
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


@app.route('/novel/<slug>/chapter/<int:num>/')
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


@app.route('/novel/<slug>/characters/')
@admin_required
def characters(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    return render_template('characters.html', novel_name=name, meta=meta, slug=slug)


@app.route('/novel/<slug>/world/')
@admin_required
def world_settings(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    return render_template('world.html', novel_name=name, meta=meta, slug=slug)


@app.route('/novel/<slug>/timeline/')
@admin_required
def timeline(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    return render_template('timeline.html', novel_name=name, meta=meta, slug=slug)


@app.route('/downloads/')
@admin_required
def download_index():
    files = []
    for f in os.listdir('/root/NovelStudio'):
        if (f.endswith('.md') or f.endswith('.tar.gz')) and os.path.isfile(os.path.join('/root/NovelStudio', f)):
            size = os.path.getsize(os.path.join('/root/NovelStudio', f))
            files.append({'name': f, 'size': size})
    files.sort(key=lambda x: x['name'])
    return render_template('downloads.html', files=files)


@app.route('/download/<filename>')
@admin_required
def download_file(filename):
    return send_from_directory('/root/NovelStudio', filename, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
