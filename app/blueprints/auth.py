import os
import random
import re
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash
from app.db import users_col, sms_codes_col, settings_col

# Alibaba Cloud SDK
from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
from alibabacloud_tea_util import models as util_models

auth_bp = Blueprint('auth', __name__)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '456321zj')

def get_aliyun_config():
    """读取阿里云配置（AccessKey/签名/模板已硬编码，其他可从数据库覆盖）"""
    doc = settings_col.find_one({'_id': 'aliyun_sms_config'})
    # 基础配置：使用提供的信息
    config = {
    }

    # 如果数据库中有配置，则允许覆盖（保留灵活性）
    if doc:
        if doc.get('sign_name'):
            config['sign_name'] = doc.get('sign_name')
        if doc.get('template_code'):
            config['template_code'] = doc.get('template_code')

    return config

def create_client(config_data):
    """初始化阿里云客户端"""
    config = open_api_models.Config(
        access_key_id=config_data['access_key_id'],
        access_key_secret=config_data['access_key_secret']
    )
    config.endpoint = f'dysmsapi.aliyuncs.com'
    return Dysmsapi20170525Client(config)

def send_sms_real(phone, code, minutes):
    """通过阿里云发送真实短信"""
    config_data = get_aliyun_config()

    if not config_data or not all([config_data.get('access_key_id'),
                                   config_data.get('access_key_secret'),
                                   config_data.get('template_code')]):
        print("警告：数据库中阿里云短信配置不完整，将回退到模拟发送。")
        return send_sms_mock(phone, code, minutes)

    client = create_client(config_data)

    # 精确匹配要求的 TemplateParam 结构：{"code":"xxxxxx","min":"x"}
    template_params = {
        'code': code,
        'min': str(minutes)
    }

    # SDK 属性说明:
    # phone_numbers 对应 PhoneNumbers
    # sign_name 对应 SignName
    # template_code 对应 TemplateCode
    # template_param 对应 TemplateParam
    send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
        phone_numbers=phone,
        sign_name=config_data['sign_name'],
        template_code=config_data['template_code'],
        template_param=json.dumps(template_params)
    )
    try:
        response = client.send_sms_with_options(send_sms_request, util_models.RuntimeOptions())
        if response.body.code == 'OK':
            return True
        else:
            print(f"阿里云短信发送失败：[{response.body.code}] {response.body.message}")
            return False
    except Exception as e:
        print(f"阿里云 SDK 异常：{str(e)}")
        return False

def send_sms_mock(phone, code, minutes):
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
