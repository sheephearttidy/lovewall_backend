# -*- coding: utf-8 -*-
"""敏感词过滤（后台开关控制）：忽略大小写，命中词替换为等长 *
词表为演示库（10 词，中英混合），生产可替换为服务端词库或审核 API"""
import re

SENSITIVE_WORDS = [
    '傻瓜', '笨蛋', '白痴', '弱智', '滚蛋',
    '垃圾', '去死', 'stupid', 'idiot', 'damn',
]

_COMPILED = [re.compile(re.escape(w), re.IGNORECASE) for w in SENSITIVE_WORDS]


def filter_sensitive_text(text: str) -> dict:
    """返回 { clean, hitCount, hitWords }；hitWords 去重"""
    clean = text or ''
    hit_words = set()
    for word, pattern in zip(SENSITIVE_WORDS, _COMPILED):
        if pattern.search(clean):
            hit_words.add(word)
            clean = pattern.sub(lambda m: '*' * len(m.group(0)), clean)
    return {'clean': clean, 'hitCount': len(hit_words), 'hitWords': sorted(hit_words)}
