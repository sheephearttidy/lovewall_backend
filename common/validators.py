# -*- coding: utf-8 -*-
"""输入校验：规则与错误文案严格对齐前端 API 档案（表 20）"""
import re

USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,20}$')
EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

# 头像七色色池（与前端 AVATAR_COLORS 一致）
AVATAR_COLORS = ['#f56c6c', '#e6a23c', '#f7ba2a', '#67c23a',
                 '#409eff', '#9b59b6', '#ff85c0']

# 便签六色主题 key（与前端 WALL_COLORS 一致）
WALL_COLORS = ['pink', 'blue', 'green', 'yellow', 'purple', 'orange']


def avatar_color_of(seed: str) -> str:
    """按字符串种子稳定取色：charCode 求和取模（与前端 avatarColorOf 一致）"""
    total = sum(ord(ch) for ch in (seed or 'x'))
    return AVATAR_COLORS[total % len(AVATAR_COLORS)]


def check_username(username) -> str | None:
    if not username or not isinstance(username, str):
        return '用户名需为 3-20 位字母、数字或下划线'
    if not USERNAME_RE.match(username):
        return '用户名需为 3-20 位字母、数字或下划线'
    return None


def check_password(password) -> str | None:
    if not password or not isinstance(password, str) or len(password) < 6:
        return '密码长度不能少于 6 位'
    return None


def check_nickname(nickname) -> str | None:
    if not nickname or not isinstance(nickname, str) or not nickname.strip():
        return '昵称不能为空'
    if len(nickname.strip()) > 20:
        return '昵称长度不能超过 20 位'
    return None


def check_email(email) -> str | None:
    if not email:
        return None  # 选填：空值直接放行
    if not isinstance(email, str) or not EMAIL_RE.match(email):
        return '邮箱格式不正确'
    return None
