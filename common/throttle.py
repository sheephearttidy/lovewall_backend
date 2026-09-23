# -*- coding: utf-8 -*-
"""发布频率限制（始终生效，不可关闭）：基于 users 表时间戳，服务端强制校验
表白 60s/条，评论 30s/条"""
import time

from flask import current_app

from common.db import query_one, execute

_ACTIONS = {
    'post': ('last_post_at', 'POST_THROTTLE_MS', '发布太频繁啦，请 {n} 秒后再试'),
    'comment': ('last_comment_at', 'COMMENT_THROTTLE_MS', '评论太频繁，请 {n} 秒后再试'),
}


def check_throttle(user_id: str, action: str) -> dict:
    """返回 { ok, remainSec, message }；ok=False 时 message 为超限提示"""
    field, cfg_key, tpl = _ACTIONS[action]
    row = query_one(f'SELECT {field} AS last FROM users WHERE id = ?', (user_id,))
    last = (row or {}).get('last') or 0
    interval = current_app.config[cfg_key]
    now = time.time() * 1000
    remain_ms = interval - (now - last)
    if remain_ms > 0:
        remain_sec = int(remain_ms / 1000) + 1
        return {'ok': False, 'remainSec': remain_sec, 'message': tpl.format(n=remain_sec)}
    return {'ok': True, 'remainSec': 0, 'message': ''}


def mark_throttle(user_id: str, action: str):
    """业务成功执行后记录本次时间戳"""
    field = _ACTIONS[action][0]
    execute(f'UPDATE users SET {field} = ? WHERE id = ?',
            (int(time.time() * 1000), user_id))
