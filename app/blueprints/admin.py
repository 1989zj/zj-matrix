from datetime import datetime
from flask import Blueprint, render_template, request, abort, url_for, redirect, jsonify
from bson.objectid import ObjectId
from pymongo import DESCENDING
from app.decorators import admin_required
from app.db import orders_col
from app.constants import ORDER_STATUSES, ORDER_TYPES
from app.services import get_order_prices, save_order_prices

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@admin_required
def index():
    # Admin root redirects to admin orders for now
    return redirect(url_for('admin.admin_orders'))

@admin_bp.route('/orders/')
@admin_required
def admin_orders():
    all_orders = list(orders_col.find({}).sort('createdAt', DESCENDING))
    for o in all_orders:
        o['_id'] = str(o['_id'])
        o['statusLabel'] = ORDER_STATUSES.get(o['status'], o['status'])
    return render_template('admin_orders.html', orders=all_orders,
                           ORDER_STATUSES=ORDER_STATUSES)

@admin_bp.route('/orders/<oid>/')
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

@admin_bp.route('/settings/')
@admin_required
def admin_settings():
    return render_template('admin_settings.html',
                          order_types=ORDER_TYPES,
                          prices=get_order_prices())

# API routes for admin
@admin_bp.route('/api/settings/prices', methods=['PUT'])
@admin_required
def api_update_prices():
    data = request.get_json()
    if not data or 'prices' not in data:
        return jsonify({"error": "missing field: prices"}), 400
    prices = data['prices']
    # 只允许保存已定义的订单类型
    cleaned = {k: int(v) for k, v in prices.items() if k in ORDER_TYPES}
    save_order_prices(cleaned)
    return jsonify({"success": True, "prices": cleaned})
