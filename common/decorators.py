# -*- coding: utf-8 -*-
"""鉴权装饰器：登录校验 / 管理员校验；每请求解析 Bearer Token 放入 g.user"""
from functools import wraps

from flask import g, request

from common.responses import fail
from common.security import decode_token
from common.db import query_one


def load_current_user():
    """从 Authorization: Bearer <token> 解析当前用户（未登录返回 None）。
    每次请求都回查数据库，保证封禁/角色调整立即生效。"""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    payload = decode_token(auth[7:].strip())
    if not payload:
        return None
    user = query_one('SELECT * FROM users WHERE id = ?', (payload['sub'],))
    if not user or user['status'] != 'active':
        return None
    return user


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get('user'):
            return fail('请先登录', http=401)
        return fn(*args, **kwargs)
    return wrapper


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = g.get('user')
        if not user:
            return fail('请先登录', http=401)
        if user['role'] != 'admin':
            return fail('需要管理员权限', http=403)
        return fn(*args, **kwargs)
    return wrapper
