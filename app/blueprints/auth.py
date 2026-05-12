import os
import random
import re
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash
from app.db import users_col, sms_codes_col, settings_col

# DYPNS SDK (号码认证服务 - 短信验证码)
from alibabacloud_dypnsapi20170525.client import Client as DypnsapiClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dypnsapi20170525 import models as dypnsapi_models

auth_bp = Blueprint('auth', __name__)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '456321zj')

def get_aliyun_config():
    """读取阿里云配置（优先级：环境变量 > 数据库settings_col）"""
    env_config = {
        'access_key_id': os.environ.get('ALIYUN_SMS_ACCESS_KEY_ID', ''),
        'access_key_secret': os.environ.get('ALIYUN_SMS_ACCESS_KEY_SECRET', ''),
        'sign_name': os.environ.get('ALIYUN_SMS_SIGN_NAME', ''),
        'template_code': os.environ.get('ALIYUN_SMS_TEMPLATE_CODE', ''),
    }
    if all([env_config['access_key_id'], env_config['access_key_secret'],
            env_config['sign_name'], env_config['template_code']]):
        return env_config
    doc = settings_col.find_one({'_id': 'aliyun_sms_config'})
    if doc:
        return {
            'access_key_id': doc.get('access_key_id', ''),
            'access_key_secret': doc.get('access_key_secret', ''),
            'sign_name': doc.get('sign_name', ''),
            'template_code': doc.get('template_code', ''),
        }
    return {}

def create_dypns_client(config_data):
    """初始化 DYPNS 客户端"""
    config = open_api_models.Config(
        access_key_id=config_data['access_key_id'],
        access_key_secret=config_data['access_key_secret']
    )
    config.endpoint = 'dypnsapi.aliyuncs.com'
    return DypnsapiClient(config)

def send_sms_real(phone, code, minutes=5):
    """通过 DYPNS (号码认证服务) 发送验证码短信"""
    config_data = get_aliyun_config()
    if not config_data or not all([config_data.get('access_key_id'),
                                   config_data.get('access_key_secret'),
                                   config_data.get('template_code'),
                                   config_data.get('sign_name')]):
        print("警告：阿里云短信配置不完整，将回退到模拟发送。")
        return send_sms_mock(phone, code, minutes)

    client = create_dypns_client(config_data)
    req = dypnsapi_models.SendSmsVerifyCodeRequest(
        phone_number=phone,
        sign_name=config_data['sign_name'],
        template_code=config_data['template_code'],
        template_param=json.dumps({'code': code, 'min': str(minutes)}),
        code_length=len(code),
        valid_time=minutes,
        return_verify_code=False,
        out_id=f"novel_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(100,999)}",
    )
    try:
        resp = client.send_sms_verify_code(req)
        if resp.body.code == 'OK':
            return True
        else:
            print(f"DYPNS 短信发送失败：[{resp.body.code}] {resp.body.message}")
            return False
    except Exception as e:
        print(f"DYPNS SDK 异常：{str(e)}")
        return False

def send_sms_mock(phone, code, minutes=5):
    """模拟发送短信（调试备用）"""
    print(f"【NovelStudio】验证码 {code} 有效期 {minutes} 分钟")
    return True

@auth_bp.route('/api/auth/send-code', methods=['POST'])
def send_code():
    data = request.get_json()
    phone = data.get('phone', '').strip()
    
    if not re.match(r'^1[3-9]\d{9}$', phone):
        return jsonify({"error": "请输入有效的手机号"}), 400
    
    # 限制发送频率 (1分钟)
    last_send = sms_codes_col.find_one({'phone': phone}, sort=[('createdAt', -1)])
    if last_send and datetime.now() - last_send['createdAt'] < timedelta(minutes=1):
        return jsonify({"error": "请1分钟后再试"}), 429

    code = str(random.randint(100000, 999999))
    expires_at = datetime.now() + timedelta(minutes=5)
    
    sms_codes_col.insert_one({
        'phone': phone,
        'code': code,
        'expiresAt': expires_at,
        'createdAt': datetime.now()
    })
    
    if send_sms_real(phone, code, 5):
        return jsonify({"success": True, "message": "验证码已发送"})
    print(f"【调试】验证码 {code} 发送至 {phone}（DYPNS失败，仅日志）")
    return jsonify({"error": "验证码发送失败，请稍后重试"}), 500

@auth_bp.route('/login/', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        code = request.form.get('code', '').strip()
        role = request.form.get('role', 'customer')

        # 管理员后门
        if phone == 'admin' and code == ADMIN_PASSWORD:
            session.permanent = True
            session['user'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('admin.index'))

        if not phone or not code:
            return render_template('login.html', error='请输入手机号和验证码')

        record = sms_codes_col.find_one({
            'phone': phone,
            'code': code,
            'expiresAt': {'$gte': datetime.now()}
        })
        
        if not record:
            return render_template('login.html', error='验证码无效或已过期')

        sms_codes_col.delete_many({'phone': phone})

        user = users_col.find_one({'phone': phone})
        if not user:
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
