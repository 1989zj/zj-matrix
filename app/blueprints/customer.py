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
        
        # Mapping for template compatibility
        o['description'] = o.get('detail', '')
        o['target_words'] = o.get('targetWords', 0)
        o['price'] = o.get('cost', 0)
        
        # Ensure datetime objects for strftime
        for field in ['createdAt', 'updatedAt']:
            val = o.get(field)
            if isinstance(val, str):
                try:
                    o[field] = datetime.fromisoformat(val.replace('Z', '+00:00'))
                except:
                    o[field] = datetime.now() # Fallback
            elif not isinstance(val, datetime):
                o[field] = datetime.now() # Fallback
                
    return render_template('orders.html', orders=all_orders, order_types=get_order_prices())

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
        
        # Ensure datetime objects for strftime
        for field in ['createdAt', 'updatedAt']:
            val = o.get(field)
            if isinstance(val, str):
                try:
                    o[field] = datetime.fromisoformat(val.replace('Z', '+00:00'))
                except:
                    o[field] = datetime.now()
            elif not isinstance(val, datetime):
                o[field] = datetime.now()
                
    stats = {
        'total': len(all_orders),
        'pending': sum(1 for o in all_orders if o['status'] == 'pending'),
        'writing': sum(1 for o in all_orders if o['status'] in ('writing', 'confirmed')),
        'completed': sum(1 for o in all_orders if o['status'] == 'completed'),
        'totalWords': sum(int(o.get('deliveredWords', 0) or 0) for o in all_orders),
        'totalChapters': sum(int(o.get('deliveredChapters', 0) or 0) for o in all_orders)
    }
    return render_template('dashboard.html', orders=all_orders, stats=stats,
                           ORDER_STATUSES=ORDER_STATUSES)

# API and Form routes for customers
@customer_bp.route('/orders/create', methods=['POST'])
@login_required
def create_order():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
        
    if not data:
        return jsonify({"error": "no data"}), 400
        
    project_name = data.get('projectName', '').strip()
    # Support both old/new field names for description/detail
    detail = data.get('detail') or data.get('description', '').strip()
    contact = data.get('contact', '').strip() or session.get('user', '')
    
    if not project_name:
        if request.is_json:
            return jsonify({"error": "missing field: projectName"}), 400
        return redirect(url_for('customer.order_page'))

    now = datetime.now()
    order_type = data.get('orderType', '全本新小说')
    from app.constants import ORDER_TYPES
    if order_type not in ORDER_TYPES:
        order_type = '全本新小说'
        
    prices = get_order_prices()
    type_price = prices.get(order_type, 15)
    chapters = int(data.get('chapters') or 60)
    
    # Support both old/new field names for target words
    target_words_val = data.get('targetWords') or data.get('target_words') or 100000
    target_words = int(target_words_val)
    
    cost = chapters * type_price
    
    order = {
        'customerName': session['user'],
        'projectName': project_name,
        'contact': contact,
        'cost': cost,
        'orderType': order_type,
        'genre': data.get('genre', '玄幻').strip(),
        'detail': detail,
        'targetWords': target_words,
        'chapters': chapters,
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
    
    if request.is_json:
        return jsonify({"success": True, "id": str(result.inserted_id)})
    return redirect(url_for('customer.order_page'))

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
