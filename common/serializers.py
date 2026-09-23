# -*- coding: utf-8 -*-
"""序列化：数据库行 → 前端数据模型形状（User / Confession / Comment / Notification）
密码哈希永不外泄；评论与通知中的昵称冗余字段由联表实时返回，改名后自动生效"""
import json


def user_public(u: dict) -> dict:
    if not u:
        return None
    return {
        'id': u['id'],
        'username': u['username'],
        'nickname': u['nickname'],
        'role': u['role'],
        'avatarColor': u['avatar_color'],
        'email': u.get('email'),
        'createdAt': u['created_at'],
        'status': u.get('status', 'active'),
    }


def comment_public(c: dict) -> dict:
    return {
        'id': c['id'],
        'confessionId': c['confession_id'],
        'authorId': c['author_id'],
        'nickname': c['nickname'],
        'content': c['content'],
        'replyTo': c['reply_to'],
        'replyToNickname': c['reply_to_nickname'],
        'createdAt': c['created_at'],
        'status': c.get('status', 'normal'),
    }


def confession_public(row: dict, liked_by_me=False) -> dict:
    """row 需带 like_count / comment_count / likes_json 聚合字段（由查询提供）"""
    likes = []
    try:
        likes = json.loads(row.get('likes_json') or '[]')
    except (TypeError, ValueError):
        likes = []
    return {
        'id': row['id'],
        'to': row['to_name'],
        'content': row['content'],
        'from': row['from_name'],
        'authorId': row['author_id'],
        'color': row['color'],
        'images': likes_images(row),
        'likes': likes,
        'likeCount': row.get('like_count', len(likes)),
        'likedByMe': liked_by_me,
        'commentCount': row.get('comment_count', 0),
        'comments': row.get('comments_list', []),
        'createdAt': row['created_at'],
        'status': row.get('status', 'normal'),
    }


def likes_images(row: dict) -> list:
    try:
        return json.loads(row.get('images') or '[]')
    except (TypeError, ValueError):
        return []


def notification_public(n: dict) -> dict:
    return {
        'id': n['id'],
        'type': n['type'],
        'toUserId': n['to_user_id'],
        'fromUserId': n['from_user_id'],
        'fromNickname': n['from_nickname'],
        'confessionId': n['confession_id'],
        'text': n['text'],
        'read': bool(n['read']),
        'createdAt': n['created_at'],
    }
