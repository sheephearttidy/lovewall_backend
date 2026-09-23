# -*- coding: utf-8 -*-
"""系统设置（公开读取）：注册页等初始化时读取，决定是否渲染邮箱验证码/图形验证码输入框"""
from flask import Blueprint

from common.responses import ok
from common.settings_store import get_settings

bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@bp.get('')
def public_settings():
    return ok({'settings': get_settings()})
