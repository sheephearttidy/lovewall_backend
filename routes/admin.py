# -*- coding: utf-8 -*-
"""管理员模块：仪表盘统计、用户管理、内容管理（表白/评论）、系统设置"""
from flask import Blueprint, g, request

from common.assets import delete_confession_images
from common.confession_queries import query_confessions
from common.db import execute, query_all, query_one
from common.decorators import require_admin
from common.responses import fail, ok
from common.security import hash_password, gen_id
from common.serializers import comment_public, confession_public, user_public
from common.settings_store import get_settings, set_setting
from common.validators import (avatar_color_of, check_email, check_nickname,
                               check_password, check_username)

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

BUILT_IN_ADMIN = 'admin'  # 内置超管用户名：封禁/改角色/删除均被拒绝
DEFAULT_RESET_PASSWORD = '123456'


def _is_built_in_admin(user: dict) -> bool:
    return user['username'] == BUILT_IN_ADMIN


# ---------------- 仪表盘统计 ----------------

@bp.get('/stats')
@require_admin
def stats():
    """服务端聚合统计（对应前端 getters：totalConfessions/totalLikes/totalComments/topLiked）"""
    top_rows = query_all('''
        SELECT c.*,
               (SELECT COUNT(*) FROM likes l WHERE l.confession_id = c.id) AS like_count,
               (SELECT COUNT(*) FROM comments cm WHERE cm.confession_id = c.id) AS comment_count,
               (SELECT COALESCE(json_group_array(l2.user_id), '[]')
                  FROM likes l2 WHERE l2.confession_id = c.id) AS likes_json
        FROM confessions c
        ORDER BY like_count DESC, c.created_at DESC LIMIT 5''')
    return ok({
        'totalUsers': query_one('SELECT COUNT(*) AS n FROM users')['n'],
        'activeUsers': query_one("SELECT COUNT(*) AS n FROM users WHERE status = 'active'")['n'],
        'bannedUsers': query_one("SELECT COUNT(*) AS n FROM users WHERE status = 'banned'")['n'],
        'totalConfessions': query_one('SELECT COUNT(*) AS n FROM confessions')['n'],
        'hiddenConfessions': query_one("SELECT COUNT(*) AS n FROM confessions WHERE status = 'hidden'")['n'],
        'totalLikes': query_one('SELECT COUNT(*) AS n FROM likes')['n'],
        'totalComments': query_one('SELECT COUNT(*) AS n FROM comments')['n'],
        'topLiked': [confession_public(r) for r in top_rows],
        'settings': get_settings(),
    })


# ---------------- 用户管理 ----------------

@bp.get('/users')
@require_admin
def list_users():
    """用户列表：keyword（用户名/昵称/邮箱模糊）+ 分页"""
    keyword = (request.args.get('keyword') or '').strip()
    page = max(int(request.args.get('page', 1) or 1), 1)
    page_size = min(max(int(request.args.get('pageSize', 20) or 20), 1), 100)

    where, args = '1=1', []
    if keyword:
        where = '(username LIKE ? OR nickname LIKE ? OR email LIKE ?)'
        kw = f'%{keyword}%'
        args = [kw, kw, kw]

    total = query_one(f'SELECT COUNT(*) AS n FROM users WHERE {where}', args)['n']
    rows = query_all(f'SELECT * FROM users WHERE {where} ORDER BY created_at DESC'
                     f' LIMIT ? OFFSET ?', args + [page_size, (page - 1) * page_size])
    return ok({'list': [user_public(u) for u in rows], 'total': total,
               'page': page, 'pageSize': page_size})


@bp.post('/users')
@require_admin
def create_user():
    """后台新建用户（role 可指定 admin，校验规则与注册一致）"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    nickname = (data.get('nickname') or '').strip() or username
    email = (data.get('email') or '').strip() or None
    role = data.get('role') or 'user'
    if role not in ('user', 'admin'):
        return fail('角色不合法')

    err = check_username(username) or check_password(password) or check_nickname(nickname)
    if err:
        return fail(err)
    err = check_email(email)
    if err:
        return fail(err)
    if query_one('SELECT id FROM users WHERE username = ?', (username,)):
        return fail('用户名已存在')
    if email and query_one('SELECT id FROM users WHERE email = ?', (email,)):
        return fail('该邮箱已被使用')

    import time
    user = {
        'id': gen_id('u'), 'username': username, 'nickname': nickname,
        'role': role, 'avatar_color': avatar_color_of(nickname),
        'created_at': int(time.time() * 1000),
    }
    execute('INSERT INTO users (id, username, nickname, password_hash, role, avatar_color,'
            ' email, created_at, status) VALUES (?,?,?,?,?,?,?,?,?)',
            (user['id'], username, nickname, hash_password(password), role,
             user['avatar_color'], email, user['created_at'], 'active'))
    return ok({'user': user_public(user)}, message='用户创建成功')


@bp.patch('/users/<user_id>')
@require_admin
def update_user(user_id):
    """调整角色 / 封禁解封 / 重置密码（action=resetPassword → 重置为 123456）"""
    target = query_one('SELECT * FROM users WHERE id = ?', (user_id,))
    if not target:
        return fail('用户不存在', http=404)

    data = request.get_json(silent=True) or {}
    action = data.get('action')

    if action == 'resetPassword':
        if _is_built_in_admin(target):
            return fail('内置管理员密码请在数据库或配置中修改', http=403)
        execute('UPDATE users SET password_hash = ? WHERE id = ?',
                (hash_password(DEFAULT_RESET_PASSWORD), user_id))
        return ok({'password': DEFAULT_RESET_PASSWORD}, message='密码已重置为 123456')

    if _is_built_in_admin(target):
        return fail('内置管理员账号不允许此操作', http=403)

    if 'banned' in data:
        banned = bool(data['banned'])
        if banned and user_id == g.user['id']:
            return fail('不能封禁自己', http=403)
        execute('UPDATE users SET status = ? WHERE id = ?',
                ('banned' if banned else 'active', user_id))
    if 'role' in data:
        role = data['role']
        if role not in ('user', 'admin'):
            return fail('角色不合法')
        execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))

    user = query_one('SELECT * FROM users WHERE id = ?', (user_id,))
    return ok({'user': user_public(user)}, message='用户已更新')


@bp.delete('/users/<user_id>')
@require_admin
def delete_user(user_id):
    """删除用户（不级联清理其历史表白与评论，作者字段置空、昵称回落快照）"""
    target = query_one('SELECT * FROM users WHERE id = ?', (user_id,))
    if not target:
        return fail('用户不存在', http=404)
    if _is_built_in_admin(target):
        return fail('不能删除内置管理员账号', http=403)
    if user_id == g.user['id']:
        return fail('不能删除自己', http=403)
    execute('DELETE FROM users WHERE id = ?', (user_id,))
    return ok(message='用户已删除')


# ---------------- 内容管理 ----------------

@bp.get('/confessions')
@require_admin
def list_confessions_admin():
    """后台表白列表（含 hidden，可按 status 过滤）"""
    params = {
        'scope': 'admin',
        'keyword': request.args.get('keyword', ''),
        'color': request.args.get('color', ''),
        'status': request.args.get('status', ''),
        'sort': request.args.get('sort', 'latest'),
        'page': request.args.get('page', 1),
        'pageSize': request.args.get('pageSize', 0),
    }
    return ok(query_confessions(params, g.user))


@bp.patch('/confessions/<confession_id>/status')
@require_admin
def set_confession_status(confession_id):
    """设置表白状态：normal（前台可见）/ hidden（仅管理员与作者可见）"""
    status = (request.get_json(silent=True) or {}).get('status')
    if status not in ('normal', 'hidden'):
        return fail('状态不合法')
    row = query_one('SELECT id FROM confessions WHERE id = ?', (confession_id,))
    if not row:
        return fail('表白不存在', http=404)
    execute('UPDATE confessions SET status = ? WHERE id = ?', (status, confession_id))
    return ok({'id': confession_id, 'status': status}, message='状态已更新')


@bp.delete('/confessions/<confession_id>')
@require_admin
def remove_confession(confession_id):
    """删除单条表白（级联删除其评论、点赞与图片文件）"""
    row = query_one('SELECT * FROM confessions WHERE id = ?', (confession_id,))
    if not row:
        return fail('表白不存在', http=404)
    delete_confession_images(row)
    execute('DELETE FROM confessions WHERE id = ?', (confession_id,))
    return ok(message='表白已删除')


@bp.post('/confessions/batch-delete')
@require_admin
def batch_remove_confessions():
    """批量删除表白：body { ids: [...] }"""
    ids = (request.get_json(silent=True) or {}).get('ids') or []
    if not isinstance(ids, list) or not ids:
        return fail('请提供要删除的 id 数组')
    marks = ','.join('?' * len(ids))
    rows = query_all(f'SELECT * FROM confessions WHERE id IN ({marks})', ids)
    for row in rows:
        delete_confession_images(row)
    n = execute(f'DELETE FROM confessions WHERE id IN ({marks})', ids)
    return ok({'deleted': n}, message=f'已删除 {n} 条表白')


@bp.delete('/comments/<comment_id>')
@require_admin
def remove_comment(comment_id):
    """删除单条评论（从所属表白的评论中移除）"""
    row = query_one('SELECT id FROM comments WHERE id = ?', (comment_id,))
    if not row:
        return fail('评论不存在', http=404)
    execute('DELETE FROM comments WHERE id = ?', (comment_id,))
    return ok(message='评论已删除')


@bp.post('/comments/batch-delete')
@require_admin
def batch_remove_comments():
    """批量删除评论：body { ids: [...] }"""
    ids = (request.get_json(silent=True) or {}).get('ids') or []
    if not isinstance(ids, list) or not ids:
        return fail('请提供要删除的 id 数组')
    marks = ','.join('?' * len(ids))
    n = execute(f'DELETE FROM comments WHERE id IN ({marks})', ids)
    return ok({'deleted': n}, message=f'已删除 {n} 条评论')


@bp.get('/comments')
@require_admin
def list_comments_admin():
    """全站评论展平列表（后台评论管理用，附表白摘要，时间倒序）"""
    page = max(int(request.args.get('page', 1) or 1), 1)
    page_size = min(max(int(request.args.get('pageSize', 20) or 20), 1), 100)
    keyword = (request.args.get('keyword') or '').strip()

    where, args = '1=1', []
    if keyword:
        where = '(cm.content LIKE ? OR cm.nickname LIKE ?)'
        kw = f'%{keyword}%'
        args = [kw, kw]

    total = query_one(f'SELECT COUNT(*) AS n FROM comments cm WHERE {where}', args)['n']
    rows = query_all(f'''
        SELECT cm.*, COALESCE(u.nickname, cm.nickname, '未知用户') AS nickname,
               c.content AS confession_content, c.to_name AS confession_to
        FROM comments cm
        LEFT JOIN users u ON u.id = cm.author_id
        LEFT JOIN confessions c ON c.id = cm.confession_id
        WHERE {where}
        ORDER BY cm.created_at DESC LIMIT ? OFFSET ?''', args + [page_size, (page - 1) * page_size])
    for r in rows:
        r['confessionContent'] = r.pop('confession_content', None)
        r['confessionTo'] = r.pop('confession_to', None)
    return ok({'list': [comment_public(r) for r in rows], 'total': total,
               'page': page, 'pageSize': page_size})


# ---------------- 系统设置 ----------------

@bp.get('/settings')
@require_admin
def get_admin_settings():
    return ok({'settings': get_settings()})


@bp.put('/settings')
@require_admin
def put_admin_settings():
    """更新系统设置：body { emailVerificationEnabled?, captchaEnabled?, sensitiveFilterEnabled? }"""
    data = request.get_json(silent=True) or {}
    current = get_settings()
    for key in ('emailVerificationEnabled', 'captchaEnabled', 'sensitiveFilterEnabled'):
        if key in data:
            set_setting(key, bool(data[key]))
    return ok({'settings': get_settings()}, message='设置已保存')
