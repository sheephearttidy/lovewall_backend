# -*- coding: utf-8 -*-
"""统一响应格式：{ code, message, data }；错误文案与前端中文契约保持一致"""
from flask import jsonify


def ok(data=None, message='ok'):
    body = {'code': 0, 'message': message}
    if data is not None:
        body['data'] = data
    return jsonify(body)


def fail(message, http=400, code=None):
    """http: HTTP 状态码；code: 业务码（缺省与 http 一致）"""
    return jsonify({'code': code if code is not None else http, 'message': message}), http
