# -*- coding: utf-8 -*-
"""认证模块：注册、登录、登出（token 吊销）、邮箱验证码、图形验证码、找回密码三步流程"""
import base64
import random
import re
import secrets
import string
import time

from flask import Blueprint, current_app, g, request

from common.db import execute, query_one
from common.decorators import require_login
from common.responses import fail, ok
from common.security import (decode_reset_token, decode_token, hash_password,
                             make_reset_token, make_token, revoke_token,
                             verify_password, gen_id)
from common.serializers import user_public
from common.settings_store import get_settings
from common.validators import (avatar_color_of, check_email, check_nickname,
                               check_password, check_username)

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


# ---------------- 邮箱验证码 ----------------

EMAIL_CODE_MAX_ATTEMPTS = 5  # 校验失败达 5 次即销毁验证码（防 6 位码暴力枚举）


def _consume_email_code(email: str, code: str):
    """校验并一次性销毁验证码；失败计数，达上限销毁。返回错误文案或 None"""
    row = query_one('SELECT * FROM email_codes WHERE email = ?', (email,))
    if not row or not code:
        return '请先获取邮箱验证码'
    if row['expires_at'] < int(time.time() * 1000):
        return '验证码已过期，请重新获取'
    if str(code).strip() != row['code']:
        attempts = (row['attempts'] or 0) + 1
        if attempts >= EMAIL_CODE_MAX_ATTEMPTS:
            execute('DELETE FROM email_codes WHERE email = ?', (email,))
            return '验证码错误次数过多，请重新获取'
        execute('UPDATE email_codes SET attempts = ? WHERE email = ?', (attempts, email))
        return '邮箱验证码错误'
    execute('DELETE FROM email_codes WHERE email = ?', (email,))
    return None


@bp.post('/email-code')
def send_email_code():
    """发送 6 位数字邮箱验证码（5 分钟有效，一次性，60s 防重发）
    开发模式（MAIL_DEBUG）直接回显验证码，与前端 Mock 行为一致"""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    if not email or not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return fail('邮箱格式不正确')

    now = int(time.time() * 1000)
    row = query_one('SELECT * FROM email_codes WHERE email = ?', (email,))
    if row and now - row['sent_at'] < current_app.config['EMAIL_CODE_RESEND_MS']:
        remain = int((current_app.config['EMAIL_CODE_RESEND_MS'] - (now - row['sent_at'])) / 1000) + 1
        return fail(f'发送太频繁，请 {remain} 秒后再试', http=429)

    code = ''.join(secrets.choice(string.digits) for _ in range(6))
    expires = now + current_app.config['EMAIL_CODE_TTL_MS']
    execute('INSERT INTO email_codes (email, code, expires_at, sent_at) VALUES (?,?,?,?) '
            'ON CONFLICT(email) DO UPDATE SET code = excluded.code,'
            ' expires_at = excluded.expires_at, sent_at = excluded.sent_at',
            (email, code, expires, now))

    if current_app.config['MAIL_DEBUG']:
        # 开发模式：不发信，直接回显（生产环境应改为 SMTP 发信且不回传）
        return ok({'email': email, 'code': code, 'expiresIn': 300}, message='验证码已发送（开发模式直接返回）')
    # 生产模式占位：接入真实 SMTP 后在此发信
    return ok({'email': email, 'expiresIn': 300}, message='验证码已发送，请查收邮箱')


# ---------------- 图形验证码（SVG，4 位字符，不区分大小写） ----------------

_CAPTCHA_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
_SVG_COLORS = ['#f56c6c', '#e6a23c', '#67c23a', '#409eff', '#9b59b6', '#364fc7']


def _gen_captcha_svg(text: str) -> str:
    chars = list(text)
    parts = []
    for i, ch in enumerate(chars):
        x = 12 + i * 22 + random.randint(-2, 2)
        y = 30 + random.randint(-4, 4)
        rot = random.randint(-25, 25)
        color = random.choice(_SVG_COLORS)
        size = random.randint(24, 30)
        parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-family="Arial, sans-serif" font-weight="bold" '
            f'transform="rotate({rot} {x} {y})">{ch}</text>')
    lines = []
    for _ in range(4):
        x1, y1 = random.randint(0, 100), random.randint(0, 40)
        x2, y2 = random.randint(0, 100), random.randint(0, 40)
        lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                     f'stroke="{random.choice(_SVG_COLORS)}" stroke-width="1" opacity="0.5"/>')
    dots = ''.join(
        f'<circle cx="{random.randint(0, 100)}" cy="{random.randint(0, 40)}" r="1.5" '
        f'fill="{random.choice(_SVG_COLORS)}" opacity="0.6"/>' for _ in range(12))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="104" height="40" '
           f'viewBox="0 0 104 40"><rect width="104" height="40" fill="#f0f2f5" rx="4"/>'
           + ''.join(lines) + dots + ''.join(parts) + '</svg>')
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode('utf-8')).decode('ascii')


@bp.get('/captcha')
def get_captcha():
    """生成图形验证码：返回 captchaId + SVG data URL（5 分钟有效，一次性，不区分大小写）"""
    text = ''.join(secrets.choice(_CAPTCHA_CHARS) for _ in range(4))
    captcha_id = gen_id('cap')
    expires = int(time.time() * 1000) + current_app.config['CAPTCHA_TTL_MS']
    execute('INSERT INTO captchas (id, text, expires_at) VALUES (?,?,?)',
            (captcha_id, text.lower(), expires))
    # 顺手清理过期验证码
    execute('DELETE FROM captchas WHERE expires_at < ?', (int(time.time() * 1000),))
    return ok({'captchaId': captcha_id, 'image': _gen_captcha_svg(text)})


def _consume_captcha(captcha_id: str, answer: str):
    row = query_one('SELECT * FROM captchas WHERE id = ?', (captcha_id or '',))
    if not row:
        return '请先获取图形验证码'
    execute('DELETE FROM captchas WHERE id = ?', (captcha_id,))  # 一次性
    if row['expires_at'] < int(time.time() * 1000):
        return '验证码已过期，请重新获取'
    if str(answer or '').strip().lower() != row['text']:
        return '图形验证码错误'
    return None


# ---------------- 注册 / 登录 / 登出 ----------------

@bp.post('/register')
def register():
    """注册新用户（成功自动登录）。邮箱验证码 / 图形验证码由服务端按系统开关强制校验"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    nickname = (data.get('nickname') or '').strip() or username
    email = (data.get('email') or '').strip() or None

    err = check_username(username) or check_password(password) or check_nickname(nickname)
    if err:
        return fail(err)
    err = check_email(email)
    if err:
        return fail(err)

    if query_one('SELECT id FROM users WHERE username = ?', (username,)):
        return fail('用户名已被注册')
    if email and query_one('SELECT id FROM users WHERE email = ?', (email,)):
        return fail('该邮箱已被注册')

    settings = get_settings()

    # 开关开启时：图形验证码 + 邮箱验证码必须通过（服务端强制，前端无法绕过）
    if settings['captchaEnabled']:
        err = _consume_captcha(data.get('captchaId'), data.get('captchaText'))
        if err:
            return fail(err)
    if settings['emailVerificationEnabled']:
        if not email:
            return fail('邮箱验证已开启，请填写邮箱并获取验证码')
        err = _consume_email_code(email, data.get('emailCode'))
        if err:
            return fail(err)

    now = int(time.time() * 1000)
    user = {
        'id': gen_id('u'),
        'username': username,
        'nickname': nickname,
        'role': 'user',
        'avatar_color': avatar_color_of(nickname),
        'created_at': now,
    }
    execute(
        'INSERT INTO users (id, username, nickname, password_hash, role, avatar_color,'
        ' email, created_at, status) VALUES (?,?,?,?,?,?,?,?,?)',
        (user['id'], username, nickname, hash_password(password), 'user',
         user['avatar_color'], email, now, 'active'))

    token, _ = make_token(user)
    return ok({'user': user_public(user), 'token': token}, message='注册成功')


@bp.post('/login')
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return fail('用户名或密码错误')

    user = query_one('SELECT * FROM users WHERE username = ?', (username,))
    if not user or not verify_password(password, user['password_hash']):
        return fail('用户名或密码错误', http=401)
    if user['status'] != 'active':
        return fail('该账号已被封禁，请联系管理员', http=403)

    token, _ = make_token(user)
    return ok({'user': user_public(user), 'token': token}, message='登录成功')


@bp.post('/logout')
@require_login
def logout():
    """登出：服务端吊销 token（jti 入黑名单，立即失效）"""
    auth = request.headers.get('Authorization', '')
    payload = decode_token(auth[7:].strip())
    revoke_token(payload)
    return ok(message='已退出登录')


@bp.get('/session')
def session_info():
    """会话恢复：前端 init() 用当前 token 换取用户信息（未登录返回 user=null）"""
    user = g.get('user')
    return ok({'user': user_public(user) if user else None,
               'isLoggedIn': bool(user), 'isAdmin': bool(user and user['role'] == 'admin')})


# ---------------- 找回密码（三步流程） ----------------

FORGOT_COOLDOWN_MS = 60 * 1000        # 同一用户名 60s 内只能尝试一次 verify
FORGOT_MAX_FAILS = 5                  # 连续失败 5 次锁定
FORGOT_LOCK_MS = 15 * 60 * 1000       # 锁定 15 分钟


def _forgot_gate(username: str):
    """verify 前置闸门：60s 冷却 + 失败锁定。返回错误文案或 None"""
    now = int(time.time() * 1000)
    row = query_one('SELECT * FROM forgot_logs WHERE username = ?', (username,))
    if not row:
        return None
    if row['locked_until'] > now:
        remain = int((row['locked_until'] - now) / 60000) + 1
        return f'尝试次数过多，请 {remain} 分钟后再试'
    if now - row['last_at'] < FORGOT_COOLDOWN_MS:
        remain = int((FORGOT_COOLDOWN_MS - (now - row['last_at'])) / 1000) + 1
        return f'操作太频繁，请 {remain} 秒后再试'
    return None


def _forgot_record(username: str, success: bool):
    """记录 verify 结果：成功清零失败计数，失败累计并可能锁定"""
    now = int(time.time() * 1000)
    if success:
        execute('INSERT INTO forgot_logs (username, last_at, fails, locked_until) VALUES (?,?,0,0) '
                'ON CONFLICT(username) DO UPDATE SET last_at = excluded.last_at,'
                ' fails = 0, locked_until = 0', (username, now))
        return
    row = query_one('SELECT fails FROM forgot_logs WHERE username = ?', (username,))
    fails = ((row['fails'] if row else 0) or 0) + 1
    locked_until = now + FORGOT_LOCK_MS if fails >= FORGOT_MAX_FAILS else 0
    execute('INSERT INTO forgot_logs (username, last_at, fails, locked_until) VALUES (?,?,?,?) '
            'ON CONFLICT(username) DO UPDATE SET last_at = excluded.last_at,'
            ' fails = excluded.fails, locked_until = excluded.locked_until',
            (username, now, fails, locked_until))


@bp.post('/forgot/verify')
def forgot_verify():
    """第一步：校验用户名与绑定邮箱匹配，返回脱敏信息 + 一次性重置凭证
    安全闸门：同用户名 60s 冷却；连续失败 5 次锁 15 分钟（防用户名/邮箱枚举）"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    if not username or not email:
        return fail('请填写用户名和邮箱')

    err = _forgot_gate(username)
    if err:
        return fail(err, http=429)

    user = query_one('SELECT * FROM users WHERE username = ?', (username,))
    matched = bool(user and user['email'] and user['email'].lower() == email.lower()
                   and user['status'] == 'active')
    _forgot_record(username, matched)

    if not user or not user['email'] or user['email'].lower() != email.lower():
        return fail('用户名与邮箱不匹配')
    if user['status'] != 'active':
        return fail('该账号已被封禁，无法重置密码')

    reset_token = make_reset_token(user['id'], current_app.config['RESET_TOKEN_MINUTES'])
    return ok({
        'user': {'id': user['id'], 'username': user['username'],
                 'nickname': user['nickname'], 'email': user['email']},
        'resetToken': reset_token,
        'expiresIn': current_app.config['RESET_TOKEN_MINUTES'] * 60,
    })


@bp.post('/forgot/reset')
def forgot_reset():
    """第三步：携带一次性重置凭证 + 邮箱验证码设置新密码
    安全约束：resetToken 用后即焚；邮箱验证码 5 次尝试限制"""
    data = request.get_json(silent=True) or {}
    user_id = data.get('userId')
    reset_token = data.get('resetToken') or ''
    new_password = data.get('newPassword') or ''
    email_code = data.get('emailCode') or data.get('code') or ''

    payload = decode_reset_token(reset_token)
    if not payload or payload.get('sub') != user_id:
        return fail('重置凭证已失效，请重新验证', http=403)
    used = query_one('SELECT 1 AS x FROM used_reset_tokens WHERE jti = ?', (payload.get('jti'),))
    if used:
        return fail('重置凭证已使用，请重新验证', http=403)

    user = query_one('SELECT * FROM users WHERE id = ?', (user_id,))
    if not user:
        return fail('用户不存在', http=404)

    err = check_password(new_password)
    if err:
        return fail(err)

    # 邮箱验证码：一次性销毁，失败计数
    err = _consume_email_code(user['email'], email_code)
    if err:
        return fail(err, http=403)

    # 凭证用后即焚（先写黑名单再改密码，保证原子性语义）
    execute('INSERT INTO used_reset_tokens (jti, expires_at) VALUES (?, ?)',
            (payload['jti'], payload.get('exp', int(time.time()))))
    execute('DELETE FROM used_reset_tokens WHERE expires_at < ?', (int(time.time()),))
    execute('UPDATE users SET password_hash = ? WHERE id = ?',
            (hash_password(new_password), user_id))
    return ok(message='密码重置成功，请使用新密码登录')
