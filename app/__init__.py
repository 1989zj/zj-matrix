import os
import secrets
from datetime import timedelta
from flask import Flask, session, request
from app.blueprints.auth import auth_bp
from app.blueprints.admin import admin_bp
from app.blueprints.customer import customer_bp
from app.blueprints.novel import novel_bp

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
    app.permanent_session_lifetime = timedelta(days=7)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(novel_bp)

    # Context Processor
    @app.context_processor
    def inject_global_vars():
        from app.db import novels_col
        res = {
            'current_user': session.get('user', None),
            'current_role': session.get('role', None),
            'has_ai_access': session.get('role') == 'admin' or session.get('has_ai_access', False)
        }
        if session.get('role') == 'admin':
            # 只加载基础信息用于切换
            novels = list(novels_col.find({}, {'name': 1, 'slug': 1, 'title': 1}))
            for n in novels:
                n['title'] = n.get('title', n['name'])
            res['all_novels'] = novels
        return res

    return app
