# -*- coding: utf-8 -*-
"""磁盘资产清理：删除表白时同步移除 uploads/ 下对应的图片文件
仅处理 /uploads/ 前缀的 URL，防路径穿越；文件不存在时静默跳过"""
import json
import os

from flask import current_app


def delete_confession_images(row: dict):
    """从表白行解析 images JSON 并删除对应磁盘文件"""
    try:
        urls = json.loads(row.get('images') or '[]')
    except (TypeError, ValueError):
        return
    if not isinstance(urls, list):
        return
    for url in urls:
        if not isinstance(url, str) or not url.startswith('/uploads/'):
            continue  # 外链或异常数据不动
        filename = url[len('/uploads/'):]
        # 防路径穿越：文件名不得含路径分隔符与特殊前缀
        if not filename or '/' in filename or '\\' in filename or filename.startswith('.'):
            continue
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass  # 磁盘清理失败不阻断业务删除
