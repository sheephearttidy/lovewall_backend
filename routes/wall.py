# -*- coding: utf-8 -*-
"""表白墙模块：表白的发布与删除、点赞切换、评论（含楼中楼）、图片上传
横切规则（服务端强制）：登录校验 → 频率限制 → 敏感词过滤 → 空内容校验 → 通知触发"""
import base64
import json
import os
import re
import time

from flask import Blueprint, current_app, g, request, send_from_directory

from common.confession_queries import get_confession_detail, query_confessions
from common.db import execute, query_one
from common.decorators import require_login
from common.notify import notify_comment, notify_like
from common.responses import fail, ok
from common.security import gen_id
from common.sensitive import filter_sensitive_text
from common.serializers import comment_public
from common.settings_store import get_settings
from common.throttle import check_throttle, mark_throttle
from common.validators import WALL_COLORS

bp = Blueprint('wall', __name__, url_prefix='/api')


# ---------------- 图片 ----------------

_DATA_URL_RE = re.compile(r'^data:image/(png|jpe?g|gif|webp);base64,(.+)$', re.S)


def _save_data_image(data_url: str) -> str:
    """data URL 落盘为静态文件，返回可访问 URL"""
    m = _DATA_URL_RE.match(data_url.strip())
    if not m:
        raise ValueError('图片格式不正确')
    ext = 'jpg' if m.group(1) in ('jpeg', 'jpg') else m.group(1)
    try:
        raw = base64.b64decode(m.group(2))
    except Exception:
        raise ValueError('图片数据损坏')
    if len(raw) > current_app.config['MAX_IMAGE_BYTES']:
        raise ValueError('单张图片不能超过 6MB')
    filename = f'{gen_id("img")}.{ext}'
    with open(os.path.join(current_app.config['UPLOAD_FOLDER'], filename), 'wb') as f:
        f.write(raw)
    return f'/uploads/{filename}'


def _normalize_images(images) -> list:
    """兼容两种输入：base64 data URL（后端落盘转 URL）与已上传的 URL"""
    if not images:
        return []
    if not isinstance(images, list):
        raise ValueError('images 必须为数组')
    if len(images) > current_app.config['MAX_IMAGES_PER_POST']:
        raise ValueError('图片最多 3 张')
    result = []
    for item in images:
        if not isinstance(item, str) or not item.strip():
            continue
        item = item.strip()
        if item.startswith('data:'):
            result.append(_save_data_image(item))
        else:
            result.append(item)
    return result[:current_app.config['MAX_IMAGES_PER_POST']]


@bp.post('/upload/images')
@require_login
def upload_images():
    """独立图片上传：body { images: [base64...] } → 返回 URL 数组"""
    data = request.get_json(silent=True) or {}
    try:
        urls = _normalize_images(data.get('images'))
    except ValueError as e:
        return fail(str(e))
    return ok({'images': urls})


@bp.get('/uploads/<path:filename>')
def uploaded_file(filename):
    """静态图片服务"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


# ---------------- 查询 ----------------

@bp.get('/confessions')
def list_confessions():
    """表白列表：分页 + 排序(latest|hottest) + keyword + color 筛选
    ?mine=1 时返回当前用户自己的表白（含隐藏，带标注）"""
    user = g.get('user')
    params = {
        'scope': 'mine' if (request.args.get('mine') == '1' and user) else 'normal',
        'keyword': request.args.get('keyword', ''),
        'color': request.args.get('color', ''),
        'sort': request.args.get('sort', 'latest'),
        'page': request.args.get('page', 1),
        'pageSize': request.args.get('pageSize', 0),
    }
    return ok(query_confessions(params, user))


@bp.get('/confessions/<confession_id>')
def confession_detail(confession_id):
    """单条表白（分享链接 ?post={id} 定位高亮用）：hidden 仅作者/管理员可见"""
    detail = get_confession_detail(confession_id, g.get('user'))
    if not detail:
        return fail('表白不存在', http=404)
    return ok({'confession': detail})


# ---------------- 发布表白 ----------------

@bp.post('/confessions')
@require_login
def add_confession():
    """发布表白：登录 → 60s 限频 → 敏感词过滤（开关）→ 空内容校验 → 写入
    返回 { confession, filtered }，filtered 为命中敏感词数量"""
    user = g.user
    data = request.get_json(silent=True) or {}

    throttle = check_throttle(user['id'], 'post')
    if not throttle['ok']:
        return fail(throttle['message'], http=429)

    to_name = (data.get('to') or '').strip() or '所有人'
    content = (data.get('content') or '').strip()
    from_name = (data.get('from') or '').strip() or '匿名'
    color = data.get('color') or 'pink'

    if len(to_name) > 20:
        return fail('收件人不能超过 20 字符')
    if len(from_name) > 20:
        return fail('署名不能超过 20 字符')
    if len(content) > 200:
        return fail('表白内容不能超过 200 字符')
    if color not in WALL_COLORS:
        return fail('颜色主题不正确')

    filtered = 0
    if get_settings()['sensitiveFilterEnabled']:
        result = filter_sensitive_text(content)
        content, filtered = result['clean'], result['hitCount']
    if not content:
        return fail('表白内容不能为空')

    try:
        images = _normalize_images(data.get('images'))
    except ValueError as e:
        return fail(str(e))

    now = int(time.time() * 1000)
    cid = gen_id('c')
    execute(
        'INSERT INTO confessions (id, to_name, content, from_name, author_id, color,'
        ' images, created_at, status) VALUES (?,?,?,?,?,?,?,?,?)',
        (cid, to_name, content, from_name, user['id'], color,
         json.dumps(images, ensure_ascii=False), now, 'normal'))
    mark_throttle(user['id'], 'post')

    detail = get_confession_detail(cid, user)
    return ok({'confession': detail, 'filtered': filtered}, message='发布成功')


# ---------------- 删除自己的表白 ----------------

@bp.delete('/confessions/<confession_id>')
@require_login
def delete_own_confession(confession_id):
    """删除自己发布的表白（物理删除，含其全部评论与点赞）"""
    row = query_one('SELECT * FROM confessions WHERE id = ?', (confession_id,))
    if not row:
        return fail('表白不存在', http=404)
    if row['author_id'] != g.user['id']:
        return fail('只能删除自己发布的表白', http=403)
    execute('DELETE FROM confessions WHERE id = ?', (confession_id,))
    return ok(message='删除成功')


# ---------------- 点赞 ----------------

@bp.put('/confessions/<confession_id>/like')
@require_login
def like_confession(confession_id):
    """点赞；点赞成功向表白作者推送 like 通知（自己赞自己不通知）"""
    row = query_one('SELECT * FROM confessions WHERE id = ?', (confession_id,))
    if not row:
        return fail('表白不存在', http=404)
    existed = query_one('SELECT 1 AS x FROM likes WHERE user_id = ? AND confession_id = ?',
                        (g.user['id'], confession_id))
    if not existed:
        execute('INSERT INTO likes (user_id, confession_id, created_at) VALUES (?,?,?)',
                (g.user['id'], confession_id, int(time.time() * 1000)))
        notify_like(row, g.user)
    return ok({'liked': True, 'likeCount': _like_count(confession_id)})


@bp.delete('/confessions/<confession_id>/like')
@require_login
def unlike_confession(confession_id):
    """取消点赞"""
    row = query_one('SELECT * FROM confessions WHERE id = ?', (confession_id,))
    if not row:
        return fail('表白不存在', http=404)
    execute('DELETE FROM likes WHERE user_id = ? AND confession_id = ?',
            (g.user['id'], confession_id))
    return ok({'liked': False, 'likeCount': _like_count(confession_id)})


def _like_count(confession_id: str) -> int:
    return query_one('SELECT COUNT(*) AS n FROM likes WHERE confession_id = ?',
                     (confession_id,))['n']


# ---------------- 评论 ----------------

@bp.post('/confessions/<confession_id>/comments')
@require_login
def add_comment(confession_id):
    """发表评论 / 楼中楼回复：登录 → 30s 限频 → 敏感词过滤 → 空内容校验 → 写入 → 推送通知
    body: { content, replyTo: { id, nickname } | null }"""
    user = g.user
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    reply_to = data.get('replyTo') or None

    row = query_one('SELECT * FROM confessions WHERE id = ?', (confession_id,))
    if not row:
        return fail('表白不存在', http=404)

    # 执行顺序（对齐前端 API 档案）：登录校验 → 30s 限频 → 敏感词过滤 → 空内容校验 → 写入
    throttle = check_throttle(user['id'], 'comment')
    if not throttle['ok']:
        return fail(throttle['message'], http=429)

    if len(content) > 100:
        return fail('评论内容不能超过 100 字符')

    filtered = 0
    if get_settings()['sensitiveFilterEnabled']:
        result = filter_sensitive_text(content)
        content, filtered = result['clean'], result['hitCount']
    if not content:
        return fail('评论内容不能为空')

    replied_comment = None
    if reply_to:
        reply_id = reply_to.get('id') if isinstance(reply_to, dict) else reply_to
        replied_comment = query_one(
            'SELECT * FROM comments WHERE id = ? AND confession_id = ?',
            (reply_id, confession_id))
        if not replied_comment:
            return fail('被回复的评论不存在')

    now = int(time.time() * 1000)
    comment = {
        'id': gen_id('cm'),
        'confession_id': confession_id,
        'author_id': user['id'],
        'nickname': user['nickname'],
        'content': content,
        'reply_to': replied_comment['id'] if replied_comment else None,
        'reply_to_nickname': replied_comment['nickname'] if replied_comment else None,
        'created_at': now,
        'status': 'normal',
    }
    execute(
        'INSERT INTO comments (id, confession_id, author_id, nickname, content,'
        ' reply_to, reply_to_nickname, created_at, status) VALUES (?,?,?,?,?,?,?,?,?)',
        (comment['id'], confession_id, user['id'], user['nickname'], content,
         comment['reply_to'], comment['reply_to_nickname'], now, 'normal'))
    mark_throttle(user['id'], 'comment')

    # 通知：评论→表白作者；回复→被回复评论作者（同一接收者只发一条，自己给自己不发）
    notify_comment(row, user, comment, replied_comment)

    return ok({'comment': comment_public(comment), 'filtered': filtered}, message='评论成功')
