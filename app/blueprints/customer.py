from datetime import datetime
from flask import Blueprint, render_template, request, session, jsonify
from pymongo import DESCENDING
from bson.objectid import ObjectId
from app.decorators import login_required
from app.db import orders_col, users_col, notifications_col
from app.constants import ORDER_STATUSES, ORDER_TYPES
from app.services import get_order_prices

customer_bp = Blueprint('customer', __name__)

@customer_bp.route('/profile/', methods=['GET', 'POST'])
@login_required
def profile():
    user = users_col.find_one({'username': session['user']})
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        # Update user info
        users_col.update_one(
            {'username': session['user']},
            {'$set': {'email': email}}
        )
        return render_template('profile.html', user=user, success='资料已更新')
    return render_template('profile.html', user=user)

@customer_bp.route('/api/notifications')
@login_required
def get_notifications():
    notifs = list(notifications_col.find({'username': session['user']}).sort('createdAt', DESCENDING).limit(10))
    for n in notifs:
        n['_id'] = str(n['_id'])
    return jsonify(notifs)

@customer_bp.route('/orders/')
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

@customer_bp.route('/dashboard/')
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

# API routes for customers
@customer_bp.route('/api/orders', methods=['POST'])
@login_required
def api_create_order():
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400
    if 'projectName' not in data or not data['projectName'].strip():
        return jsonify({"error": "missing field: projectName"}), 400
    if 'contact' not in data or not data['contact'].strip():
        return jsonify({"error": "missing field: contact"}), 400
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
    return jsonify({"success": True, "id": str(result.inserted_id)})

@customer_bp.route('/api/orders/<oid>', methods=['PUT'])
@login_required
def api_update_order(oid):
    try:
        obj_id = ObjectId(oid)
    except:
        return jsonify({"error": "invalid id"}), 400

    order = orders_col.find_one({'_id': obj_id})
    if not order:
        return jsonify({"error": "not found"}), 404

    # 非管理员只能更新自己的订单
    if session['role'] != 'admin' and order.get('customerName') != session['user']:
        return jsonify({"error": "forbidden"}), 403

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
        
        # Create notification
        notifications_col.insert_one({
            'username': order.get('customerName'),
            'title': '订单状态更新',
            'message': f'您的项目 "{order.get("projectName")}" 已更新为 {ORDER_STATUSES.get(updates.get("status"), updates.get("status", "新状态"))}',
            'read': False,
            'createdAt': datetime.now()
        })

    return jsonify({"success": True})
