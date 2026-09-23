# -*- coding: utf-8 -*-
"""表白查询构造器：分页 + 排序(latest/hottest) + keyword + color 筛选
前台（normal）/ 我的作品（含 hidden 标注）/ 管理后台（含 hidden）三种口径共用"""
from flask import current_app, g

from common.db import query_all, query_one
from common.serializers import comment_public, confession_public


def _base_select(extra_where='1=1'):
    """聚合 like_count / comment_count / 点赞用户列表（与前端 likes: string[] 形状对齐）"""
    return f'''
        SELECT c.*,
               (SELECT COUNT(*) FROM likes l WHERE l.confession_id = c.id) AS like_count,
               (SELECT COUNT(*) FROM comments cm WHERE cm.confession_id = c.id) AS comment_count,
               (SELECT COALESCE(json_group_array(l2.user_id), '[]')
                  FROM likes l2 WHERE l2.confession_id = c.id) AS likes_json
        FROM confessions c
        WHERE {extra_where}
    '''


def _attach_comments(rows):
    """为每条表白挂载平铺评论列表（按时间正序，前端按 replyTo 自行渲染楼中楼）
    评论者昵称联表 users 实时返回（改名即生效）；作者被删除时回落快照昵称"""
    if not rows:
        return rows
    ids = [r['id'] for r in rows]
    marks = ','.join('?' * len(ids))
    comments = query_all(
        f'''SELECT cm.*,
                   COALESCE(u.nickname, cm.nickname, '未知用户') AS nickname
            FROM comments cm LEFT JOIN users u ON u.id = cm.author_id
            WHERE cm.confession_id IN ({marks})
            ORDER BY cm.created_at ASC''', ids)
    by_confession = {}
    for cm in comments:
        by_confession.setdefault(cm['confession_id'], []).append(cm)
    for r in rows:
        r['comments_list'] = [comment_public(c) for c in by_confession.get(r['id'], [])]
    return rows


def _liked_ids(confession_ids, user):
    """当前用户在给定表白集合中已点赞的 id 集"""
    if not user or not confession_ids:
        return set()
    marks = ','.join('?' * len(confession_ids))
    rows = query_all(
        f'SELECT confession_id FROM likes WHERE user_id = ? AND confession_id IN ({marks})',
        [user['id']] + list(confession_ids))
    return {r['confession_id'] for r in rows}


def query_confessions(params: dict, user: dict):
    """统一列表查询。
    params: scope(normal|mine|admin) / keyword / color / sort(latest|hottest) / page / pageSize
    返回 { list, total, page, pageSize }"""
    scope = params.get('scope', 'normal')
    where, args = [], []

    if scope == 'mine':
        if not user:
            return {'list': [], 'total': 0, 'page': 1, 'pageSize': 0}
        where.append('c.author_id = ?')  # 我的表白：含 hidden，前端有隐藏标注
        args.append(user['id'])
    elif scope == 'admin':
        where.append('1=1')  # 管理后台：含 hidden
    else:
        where.append("c.status = 'normal'")  # 前台：仅可见表白

    keyword = (params.get('keyword') or '').strip()
    if keyword:
        where.append('(c.content LIKE ? OR c.to_name LIKE ? OR c.from_name LIKE ?)')
        kw = f'%{keyword}%'
        args.extend([kw, kw, kw])

    color = (params.get('color') or '').strip()
    if color:
        where.append('c.color = ?')
        args.append(color)

    sort = params.get('sort') or 'latest'
    if scope == 'admin' and params.get('status'):
        where.append('c.status = ?')
        args.append(params['status'])

    order = 'c.created_at DESC'
    if sort == 'hottest':
        order = 'like_count DESC, c.created_at DESC'

    page = max(int(params.get('page') or 1), 1)
    page_size = min(max(int(params.get('pageSize') or current_app.config['DEFAULT_PAGE_SIZE']), 1),
                    current_app.config['MAX_PAGE_SIZE'])

    where_sql = ' AND '.join(where) if where else '1=1'
    total = query_one(f'SELECT COUNT(*) AS n FROM confessions c WHERE {where_sql}', args)['n']

    base = _base_select(where_sql)
    sql = f'{base} ORDER BY {order} LIMIT ? OFFSET ?'
    rows = query_all(sql, args + [page_size, (page - 1) * page_size])
    _attach_comments(rows)
    liked = _liked_ids([r['id'] for r in rows], user)

    return {
        'list': [confession_public(r, liked_by_me=(r['id'] in liked)) for r in rows],
        'total': total,
        'page': page,
        'pageSize': page_size,
    }


def get_confession_detail(confession_id: str, user: dict):
    """单条表白：normal 公开；hidden 仅作者本人或管理员可见"""
    row = query_one(_base_select('c.id = ?'), [confession_id])
    if not row:
        return None
    is_admin = bool(user and user.get('role') == 'admin')
    is_author = bool(user and user.get('id') == row['author_id'])
    if row['status'] == 'hidden' and not (is_admin or is_author):
        return None
    _attach_comments([row])
    liked = bool(user) and query_one(
        'SELECT 1 AS x FROM likes WHERE user_id = ? AND confession_id = ?',
        (user['id'], confession_id)) is not None
    return confession_public(row, liked_by_me=liked)
