# -*- coding: utf-8 -*-
"""SQLite 数据库连接管理与通用查询封装（Flask 请求级连接）"""
import os
import sqlite3

from flask import current_app, g

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'schema.sql')


def _connect(path=None):
    path = path or current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA busy_timeout = 5000')
    return conn


def get_db():
    """请求级单例连接"""
    if 'db' not in g:
        g.db = _connect()
    return g.db


def close_db(_e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """应用启动时：确保目录存在、开启 WAL、建表"""
    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']) or '.', exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    conn = _connect(app.config['DATABASE_PATH'])
    try:
        conn.execute('PRAGMA journal_mode = WAL')
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def query_all(sql, args=()):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def query_one(sql, args=()):
    cur = get_db().execute(sql, args)
    row = cur.fetchone()
    return dict(row) if row is not None else None


def execute(sql, args=()):
    """执行写操作并提交，返回受影响行数"""
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.rowcount
