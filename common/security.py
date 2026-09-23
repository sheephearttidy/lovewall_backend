# -*- coding: utf-8 -*-
"""安全组件：bcrypt 密码哈希、JWT 签发/校验（含登出黑名单）、短 ID 生成"""
import base64
import secrets
import string
import time
import uuid

import bcrypt
import jwt

from common.db import query_one

ALPHABET = string.ascii_lowercase + string.digits


# ---------------- 密码 ----------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt(rounds=10)).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except ValueError:
        return False


# ---------------- 短 ID：前缀 + 时间戳base36 + 5位随机（与前端 genId 形状一致） ----------------

def _to_base36(n: int) -> str:
    digits = ''
    while n:
        n, r = divmod(n, 36)
        digits = (string.digits + string.ascii_lowercase)[r] + digits
    return digits or '0'


def gen_id(prefix: str) -> str:
    rand = ''.join(secrets.choice(ALPHABET) for _ in range(5))
    return f'{prefix}-{_to_base36(int(time.time() * 1000))}{rand}'


# ---------------- JWT ----------------

def make_token(user: dict, expire_days: int = None) -> tuple:
    """返回 (token, payload)；payload 含 jti 用于服务端吊销"""
    from flask import current_app
    days = expire_days if expire_days is not None else current_app.config['TOKEN_EXPIRE_DAYS']
    now = int(time.time())
    payload = {
        'sub': user['id'],
        'username': user['username'],
        'role': user['role'],
        'jti': uuid.uuid4().hex,
        'iat': now,
        'exp': now + days * 86400,
    }
    token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
    return token, payload


def decode_token(token: str):
    """解析并校验 token；命中黑名单（已登出）返回 None"""
    from flask import current_app
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    black = query_one('SELECT jti FROM token_blacklist WHERE jti = ?', (payload.get('jti'),))
    if black:
        return None
    return payload


def revoke_token(payload: dict):
    """登出吊销：把 jti 写入黑名单，存活至 token 自然过期"""
    if payload and payload.get('jti'):
        from common.db import execute
        execute('INSERT OR IGNORE INTO token_blacklist (jti, expires_at) VALUES (?, ?)',
                (payload['jti'], payload.get('exp', int(time.time()))))


def make_reset_token(user_id: str, minutes: int) -> str:
    """找回密码第三步的一次性重置凭证（短时效 JWT）"""
    from flask import current_app
    now = int(time.time())
    payload = {
        'sub': user_id,
        'type': 'password_reset',
        'jti': uuid.uuid4().hex,
        'iat': now,
        'exp': now + minutes * 60,
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def decode_reset_token(token: str):
    from flask import current_app
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
    except jwt.InvalidTokenError:
        return None
    if payload.get('type') != 'password_reset':
        return None
    return payload
