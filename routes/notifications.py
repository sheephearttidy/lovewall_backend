# -*- coding: utf-8 -*-
"""通知模块：当前用户的通知列表 / 已读管理 / 清空（仅作用于当前登录用户）"""
from flask import Blueprint, g, request

from common.db import execute, query_one
from common.decorators import require_login
from common.responses import fail, ok
from common.serializers import notification_public

bp = Blueprint('notifications', __name__, url_prefix='/api/notifications')


@bp.get('')
@require_login
def my_notifications():
    """当前用户的通知列表（时间倒序）+ 未读数（铃铛角标）"""
    page = max(int(request.args.get('page', 1) or 1), 1)
    page_size = min(max(int(request.args.get('pageSize', 20) or 20), 1), 50)
    uid = g.user['id']
    total = query_one('SELECT COUNT(*) AS n FROM notifications WHERE to_user_id = ?',
                      (uid,))['n']
    unread = query_one(
        'SELECT COUNT(*) AS n FROM notifications WHERE to_user_id = ? AND read = 0',
        (uid,))['n']
    rows = execute_and_fetch(uid, page, page_size)
    return ok({
        'list': [notification_public(n) for n in rows],
        'total': total,
        'unreadCount': unread,
        'page': page,
        'pageSize': page_size,
    })


def execute_and_fetch(uid, page, page_size):
    """联表 users 实时取触发者昵称（改名即生效）；用户已删除时回落写时快照"""
    from common.db import query_all
    return query_all(
        '''SELECT nt.*, COALESCE(u.nickname, nt.from_nickname, '未知用户') AS from_nickname
           FROM notifications nt LEFT JOIN users u ON u.id = nt.from_user_id
           WHERE nt.to_user_id = ? ORDER BY nt.created_at DESC
           LIMIT ? OFFSET ?''', (uid, page_size, (page - 1) * page_size))


@bp.put('/read-all')
@require_login
def mark_all_read():
    """全部标记已读（仅当前用户）"""
    execute('UPDATE notifications SET read = 1 WHERE to_user_id = ?', (g.user['id'],))
    return ok(message='已全部标记为已读')


@bp.put('/<notification_id>/read')
@require_login
def mark_read(notification_id):
    """单条标记已读"""
    row = query_one('SELECT * FROM notifications WHERE id = ? AND to_user_id = ?',
                    (notification_id, g.user['id']))
    if not row:
        return fail('通知不存在', http=404)
    execute('UPDATE notifications SET read = 1 WHERE id = ?', (notification_id,))
    return ok(message='已标记为已读')


@bp.delete('')
@require_login
def clear_all():
    """清空当前用户的通知"""
    execute('DELETE FROM notifications WHERE to_user_id = ?', (g.user['id'],))
    return ok(message='已清空通知')
