import os
import random
import re
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash
from app.db import users_col, sms_codes_col

auth_bp = Blueprint('auth', __name__)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '456321zj')

def send_sms_mock(phone, code):
    """模拟发送短信"""
    print(f"【NovelStudio】您的验证码为：{code}，请在5分钟内完成验证。")
    # 实际开发时在此接入阿里云/腾讯云短信SDK
    return True

@auth_bp.route('/api/auth/send-code', methods=['POST'])
def send_code():
    data = request.get_json()
    phone = data.get('phone', '').strip()
    
    if not re.match(r'^1[3-9]\d{9}$', phone):
        return jsonify({"error": "请输入有效的手机号"}), 400
    
    # 限制发送频率 (可选)
    # last_send = sms_codes_col.find_one({'phone': phone}, sort=[('createdAt', -1)])
    # if last_send and datetime.now() - last_send['createdAt'] < timedelta(minutes=1):
    #     return jsonify({"error": "请稍后再试"}), 429

    code = str(random.randint(100000, 999999))
    expires_at = datetime.now() + timedelta(minutes=5)
    
    sms_codes_col.insert_one({
        'phone': phone,
        'code': code,
        'expiresAt': expires_at,
        'createdAt': datetime.now()
    })
    
    if send_sms_mock(phone, code):
        return jsonify({"success": True, "message": "验证码已发送"})
    return jsonify({"error": "验证码发送失败"}), 500

@auth_bp.route('/login/', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        code = request.form.get('code', '').strip()
        role = request.form.get('role', 'customer')

        # 管理员后门 (保留，或根据需求移除)
        if phone == 'admin' and code == ADMIN_PASSWORD:
            session.permanent = True
            session['user'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('admin.index'))

        if not phone or not code:
            return render_template('login.html', error='请输入手机号和验证码')

        # 校验验证码
        record = sms_codes_col.find_one({
            'phone': phone,
            'code': code,
            'expiresAt': {'$gte': datetime.now()}
        })
        
        if not record:
            return render_template('login.html', error='验证码无效或已过期')

        # 登录成功，删除已使用的验证码
        sms_codes_col.delete_many({'phone': phone})

        # 查找或创建用户
        user = users_col.find_one({'phone': phone})
        if not user:
            # 自动注册
            username = f"用户_{phone[-4:]}"
            user_data = {
                'username': username,
                'phone': phone,
                'role': 'customer',
                'created_at': datetime.now()
            }
            users_col.insert_one(user_data)
            user = user_data

        session.permanent = True
        session['user'] = user['username']
        session['role'] = user['role']
        
        next_url = request.args.get('next') or request.form.get('next') or ''
        if not next_url or next_url == '/':
            next_url = url_for('customer.order_page') if user['role'] == 'customer' else url_for('admin.index')
        return redirect(next_url)

    return render_template('login.html', next=request.args.get('next', ''))

@auth_bp.route('/logout/')
def logout():
    session.clear()
    return redirect(url_for('auth.login_page'))
