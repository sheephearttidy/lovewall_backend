# -*- coding: utf-8 -*-
"""蓝图注册"""


def register_blueprints(app):
    from routes.auth import bp as auth_bp
    from routes.wall import bp as wall_bp
    from routes.notifications import bp as notifications_bp
    from routes.users import bp as users_bp
    from routes.admin import bp as admin_bp
    from routes.settings import bp as settings_bp

    for bp in (auth_bp, wall_bp, notifications_bp, users_bp, admin_bp, settings_bp):
        app.register_blueprint(bp)
