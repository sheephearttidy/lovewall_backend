# -*- coding: utf-8 -*-
"""系统设置读写：全站唯一配置（邮箱验证 / 图形验证码 / 敏感词过滤三个开关）"""
from common.db import query_all, execute

DEFAULTS = {
    'emailVerificationEnabled': False,
    'captchaEnabled': False,
    'sensitiveFilterEnabled': False,
}


def get_settings() -> dict:
    rows = query_all('SELECT key, value FROM settings')
    stored = {r['key']: r['value'] == '1' for r in rows}
    merged = dict(DEFAULTS)
    merged.update(stored)
    return merged


def set_setting(key: str, value: bool):
    if key not in DEFAULTS:
        raise KeyError(key)
    execute('INSERT INTO settings (key, value) VALUES (?, ?) '
            'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
            (key, '1' if value else '0'))
