# -*- coding: utf-8 -*-
"""用户模块：个人资料（昵称/头像色）、修改密码、我的表白"""
from flask import Blueprint, g, request

from common.confession_queries import query_confessions
from common.db import execute, query_one
from common.decorators import require_login
from common.responses import fail, ok
from common.security import hash_password, verify_password
from common.serializers import user_public
from common.validators import AVATAR_COLORS, check_nickname, check_password

bp = Blueprint('users', __name__, url_prefix='/api/users')


@bp.get('/me')
@require_login
def me():
    """当前登录用户信息（会话恢复）"""
    return ok({'user': user_public(g.user)})


@bp.patch('/me')
@require_login
def update_profile():
    """更新昵称与头像颜色。
    历史署名同步在服务端完成（表白 from 署名 + 评论昵称快照），前端无需再调 sync。"""
    data = request.get_json(silent=True) or {}
    nickname = (data.get('nickname') or '').strip()
    avatar_color = data.get('avatarColor')

    err = check_nickname(nickname)
    if err:
        return fail(err)
    if avatar_color and avatar_color not in AVATAR_COLORS:
        avatar_color = None  # 非法色值忽略（与前端行为一致）

    old_nickname = g.user['nickname']
    execute('UPDATE users SET nickname = ?'
            + (', avatar_color = ?' if avatar_color else '')
            + ' WHERE id = ?',
            (nickname, avatar_color, g.user['id']) if avatar_color
            else (nickname, g.user['id']))

    # 署名同步：仅当历史署名等于旧昵称时才替换，保留「匿名」等自定义署名
    if old_nickname != nickname:
        execute('UPDATE confessions SET from_name = ? WHERE author_id = ? AND from_name = ?',
                (nickname, g.user['id'], old_nickname))
        execute('UPDATE comments SET nickname = ? WHERE author_id = ?',
                (nickname, g.user['id']))

    user = query_one('SELECT * FROM users WHERE id = ?', (g.user['id'],))
    return ok({'user': user_public(user), 'oldNickname': old_nickname}, message='资料已更新')


@bp.put('/me/password')
@require_login
def change_password():
    """验证原密码后修改密码（不强制重新登录）"""
    data = request.get_json(silent=True) or {}
    old_password = data.get('oldPassword') or ''
    new_password = data.get('newPassword') or ''

    if not verify_password(old_password, g.user['password_hash']):
        return fail('原密码错误', http=403)
    err = check_password(new_password)
    if err:
        return fail(err)

    execute('UPDATE users SET password_hash = ? WHERE id = ?',
            (hash_password(new_password), g.user['id']))
    return ok(message='密码修改成功')


@bp.get('/me/confessions')
@require_login
def my_confessions():
    """我的表白（个人中心用，含 hidden 并带标注）"""
    params = {
        'scope': 'mine',
        'keyword': request.args.get('keyword', ''),
        'color': request.args.get('color', ''),
        'sort': request.args.get('sort', 'latest'),
        'page': request.args.get('page', 1),
        'pageSize': request.args.get('pageSize', 0),
    }
    return ok(query_confessions(params, g.user))
