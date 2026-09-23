# -*- coding: utf-8 -*-
"""Lovewall 表白墙后端 · 全局配置（SQLite 版）"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- 基础 ----------
SECRET_KEY = os.environ.get('LOVEWALL_SECRET_KEY', 'lovewall-dev-secret-change-me')
JSON_AS_ASCII = False  # 中文原样输出

# ---------- 数据库（SQLite） ----------
DATABASE_PATH = os.environ.get('LOVEWALL_DB', os.path.join(BASE_DIR, 'lovewall.db'))

# ---------- 鉴权 ----------
TOKEN_EXPIRE_DAYS = int(os.environ.get('LOVEWALL_TOKEN_DAYS', '7'))  # JWT 有效期（天）
RESET_TOKEN_MINUTES = 10  # 找回密码一次性凭证有效期（分钟）

# ---------- 图片上传 ----------
UPLOAD_FOLDER = os.environ.get('LOVEWALL_UPLOAD_DIR', os.path.join(BASE_DIR, 'uploads'))
MAX_IMAGES_PER_POST = 3        # 每条表白最多 3 张
MAX_IMAGE_BYTES = 6 * 1024 * 1024  # 单张解压后 ≤ 6MB（前端已压缩至宽800/质量0.85）

# ---------- 频率限制（始终生效，不可关闭） ----------
POST_THROTTLE_MS = 60 * 1000    # 发布表白冷却 60s
COMMENT_THROTTLE_MS = 30 * 1000  # 发表评论冷却 30s

# ---------- 邮箱验证码 ----------
EMAIL_CODE_TTL_MS = 5 * 60 * 1000   # 验证码 5 分钟有效
EMAIL_CODE_RESEND_MS = 60 * 1000    # 60s 防重发
# 开发模式：不发真实邮件，响应中直接回显验证码（与前端 Mock 行为一致）
# 生产环境设为 false 并配置 SMTP 后由服务端发信且不回传验证码
MAIL_DEBUG = os.environ.get('LOVEWALL_MAIL_DEBUG', '1') == '1'

# ---------- 图形验证码 ----------
CAPTCHA_TTL_MS = 5 * 60 * 1000  # 5 分钟有效，一次性

# ---------- 通知 ----------
NOTIFICATION_KEEP_PER_USER = 50  # 每个用户最多保留最近 50 条通知

# ---------- 分页 ----------
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50
