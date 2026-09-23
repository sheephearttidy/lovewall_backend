# -*- coding: utf-8 -*-
"""通知推送（仅由点赞/评论触发，规则见表 23）：
- 点赞表白 → 通知表白作者（type=like）
- 评论表白（非回复）→ 通知表白作者（type=comment）
- 回复评论 → 通知被回复评论作者（type=reply）；若其同时是表白作者，只收一条 reply
- 自己给自己的操作不发通知；每用户仅保留最近 50 条"""
import time

from flask import current_app

from common.db import execute, query_one
from common.security import gen_id


def _truncate(text: str, limit=15) -> str:
    text = (text or '').strip()
    return text if len(text) <= limit else text[:limit] + '…'


def _push(type_: str, to_user_id: str, from_user: dict, confession_id: str, text: str):
    now = int(time.time() * 1000)
    execute(
        'INSERT INTO notifications (id, type, to_user_id, from_user_id, from_nickname,'
        ' confession_id, text, read, created_at) VALUES (?,?,?,?,?,?,?,?,?)',
        (gen_id('n'), type_, to_user_id, from_user['id'], from_user['nickname'],
         confession_id, _truncate(text), 0, now))
    # 只保留该用户最近 N 条
    keep = current_app.config['NOTIFICATION_KEEP_PER_USER']
    execute(
        'DELETE FROM notifications WHERE to_user_id = ? AND id NOT IN ('
        '  SELECT id FROM notifications WHERE to_user_id = ? ORDER BY created_at DESC LIMIT ?)',
        (to_user_id, to_user_id, keep))


def notify_like(confession: dict, from_user: dict):
    author_id = confession.get('author_id')
    if author_id and author_id != from_user['id']:
        _push('like', author_id, from_user, confession['id'],
              f'赞了你的表白「{_truncate(confession["content"], 12)}」')


def notify_comment(confession: dict, from_user: dict, comment: dict, replied_comment: dict):
    """评论/回复的通知分发（同一操作同一接收者只发一条；自己给自己不发）"""
    author_id = confession.get('author_id')
    me = from_user['id']
    reply_to_author = replied_comment.get('author_id') if replied_comment else None
    summary = _truncate(comment['content'], 12)

    if comment.get('reply_to'):
        # 楼中楼：只通知被回复评论的作者（若其同时是表白作者，也只收这一条 reply）
        if reply_to_author and reply_to_author != me:
            _push('reply', reply_to_author, from_user, confession['id'],
                  f'回复了你「{summary}」')
    else:
        # 普通评论：通知表白作者
        if author_id and author_id != me:
            _push('comment', author_id, from_user, confession['id'],
                  f'评论了你的表白「{summary}」')
