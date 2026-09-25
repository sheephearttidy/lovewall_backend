# -*- coding: utf-8 -*-
"""Lovewall 表白墙后端 · 应用入口（Flask + SQLite + JWT）
启动：python app.py  （默认 http://0.0.0.0:5000）
初始化种子数据：python seed.py"""
from flask import Flask, g, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

import config
from common import db as database
from common.decorators import load_current_user
from common.responses import fail
from routes import register_blueprints

# HTTPException 状态码 → 中文文案（覆盖可能出现的非 2xx 响应）
_HTTP_CN = {
    400: '请求参数错误', 401: '请先登录', 403: '没有权限执行此操作',
    404: '接口不存在', 405: '请求方法不允许', 409: '资源冲突',
    413: '请求体过大，图片请压缩后再上传', 415: '不支持的媒体类型',
    429: '请求过于频繁，请稍后再试',
}


def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    app.json.ensure_ascii = False  # JSON 中文原样输出

    CORS(app)  # 前后端分离：全开放跨域（Bearer Token 鉴权，无 Cookie 依赖）

    database.init_db(app)          # 建表 + WAL + 轻量迁移
    register_blueprints(app)

    @app.before_request
    def _load_user():
        g.user = load_current_user()

    @app.teardown_appcontext
    def _close_db(_exc):
        database.close_db()

    # ---------- 统一 JSON 错误响应 ----------
    @app.errorhandler(HTTPException)
    def _http_exception(e: HTTPException):
        # 框架级 HTTP 异常（含 413 超限、400 解析失败等）转统一格式，不落入 500
        message = _HTTP_CN.get(e.code) or (e.description if e.description else '请求失败')
        return fail(message, http=e.code)

    @app.errorhandler(404)
    def _404(_e):
        return fail('接口不存在', http=404)

    @app.errorhandler(405)
    def _405(_e):
        return fail('请求方法不允许', http=405)

    @app.errorhandler(Exception)
    def _500(e):
        from flask import current_app
        current_app.logger.exception(e)
        return fail('服务器内部错误', http=500)

    @app.get('/api/health')
    def health():
        return jsonify({'code': 0, 'message': 'ok',
                        'data': {'service': 'lovewall-backend', 'db': 'sqlite'}})

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=True)
