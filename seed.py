# -*- coding: utf-8 -*-
"""种子数据初始化：6 个演示账号 + 12 条表白（含楼中楼评论、点赞）+ 通知
用法：python seed.py [--force]  （--force 清空重建）
演示账号：
  admin / admin123（管理员）
  xiaomei chenhao yaya luming tangtang / 123456（普通用户，昵称：小美/辰昊/丫丫/陆鸣/糖糖）"""
import json
import os
import sqlite3
import sys
import time

from common.security import gen_id, hash_password
from common.validators import avatar_color_of

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('LOVEWALL_DB', os.path.join(BASE_DIR, 'lovewall.db'))

USERS = [
    # (username, password, nickname, role, email)
    ('admin',    'admin123', '管理员', 'admin', 'admin@lovewall.dev'),
    ('xiaomei',  '123456',   '小美',   'user',  'xiaomei@lovewall.dev'),
    ('chenhao',  '123456',   '辰昊',   'user',  'chenhao@lovewall.dev'),
    ('yaya',     '123456',   '丫丫',   'user',  'yaya@lovewall.dev'),
    ('luming',   '123456',   '陆鸣',   'user',  'luming@lovewall.dev'),
    ('tangtang', '123456',   '糖糖',   'user',  'tangtang@lovewall.dev'),
]

# (to, content, from(署名), author_key, color, 小时前)
CONFESSIONS = [
    ('小美', '第一次见到你，是在图书馆三楼靠窗的位置。阳光落在你翻书的指尖，那一刻我忽然明白了什么叫心动。',
     '辰昊', 'chenhao', 'blue', 58),
    ('所有人', '其实我每天都绕远路经过你家楼下，只为了那一点点可能偶遇的运气。',
     '匿名', 'xiaomei', 'pink', 55),
    ('陆鸣', '篮球场上你转身投篮的样子真的很帅，可惜我永远只敢在场边默默加油。',
     '丫丫', 'yaya', 'green', 51),
    ('糖糖', '你笑起来有两个梨涡，是我整个高三最温柔的注脚。',
     '匿名', 'chenhao', 'yellow', 47),
    ('辰昊', '谢谢你在雨天把伞塞给我，自己淋着雨跑走。那把伞我还留着，想找个机会还给你。',
     '小美', 'xiaomei', 'purple', 43),
    ('所有人', '毕业两年了，我还是会梦见教室后门那个扎马尾的女孩。',
     '陆鸣', 'luming', 'orange', 40),
    ('丫丫', '你认真讲题的样子，比我做对所有的题都让我开心。',
     '匿名', 'tangtang', 'pink', 36),
    ('小美', '食堂三楼靠窗第二张桌子，你常坐的位置。我每天都提前去坐你斜对面，你从来没发现过。',
     '匿名', 'yaya', 'blue', 32),
    ('所有人', '有些人说不出哪里好，但就是谁都替代不了。',
     '糖糖', 'tangtang', 'green', 27),
    ('陆鸣', '运动会你摔倒又爬起来冲线的那个瞬间，我在终点哭得比你还惨。',
     '匿名', 'xiaomei', 'purple', 22),
    ('所有人', '如果青春有味道，那一定是小卖部汽水的甜，和你路过时空气里的甜。',
     '辰昊', 'chenhao', 'yellow', 16),
    ('丫丫', '下周就要各奔东西了，鼓起勇气说一句：丫丫，其实我一直很喜欢你。',
     '陆鸣', 'luming', 'orange', 8),
]

# (表白序号, 作者key, 内容, 回复目标序号或None, 分钟偏移)
COMMENTS = [
    (1, 'xiaomei',  '哇，这也太甜了吧！', None, -50),
    (1, 'chenhao',  '嘿嘿，被发现了～', 1, -49),
    (1, 'yaya',     '磕到了磕到了，祝你们长久！', None, -48),
    (3, 'tangtang', '姐姐勇敢一点啊！', None, -44),
    (3, 'yaya',     '呜呜，不敢不敢。', 4, -43),
    (5, 'chenhao',  '伞……我从来没想要回来过。', None, -38),
    (5, 'xiaomei',  '？？？你等我说完', 6, -37),
    (8, 'yaya',     '这个我磕，蹲一个后续。', None, -26),
    (12, 'yaya',    '陆鸣，其实我也一直喜欢你。', None, -6),
]

# (表白序号, 点赞用户keys)
LIKES = [
    (1, ['xiaomei', 'yaya', 'tangtang', 'luming']),
    (2, ['chenhao', 'yaya']),
    (3, ['tangtang', 'xiaomei', 'chenhao']),
    (4, ['yaya']),
    (5, ['chenhao', 'luming']),
    (6, ['xiaomei', 'tangtang']),
    (7, ['luming']),
    (8, ['chenhao']),
    (9, ['xiaomei', 'yaya', 'chenhao']),
    (10, ['tangtang']),
    (11, ['yaya', 'xiaomei']),
    (12, ['xiaomei', 'chenhao', 'tangtang', 'yaya']),
]


def main():
    force = '--force' in sys.argv
    if os.path.exists(DB_PATH) and not force:
        print(f'数据库已存在：{DB_PATH}（如需重建请加 --force）')
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    with open(os.path.join(BASE_DIR, 'schema.sql'), 'r', encoding='utf-8') as f:
        conn.executescript(f.read())

    if force:
        for t in ('users', 'confessions', 'likes', 'comments',
                  'notifications', 'settings', 'email_codes', 'captchas', 'token_blacklist'):
            conn.execute(f'DELETE FROM {t}')

    now = int(time.time() * 1000)

    # ---- 用户 ----
    uid = {}
    for username, pwd, nickname, role, email in USERS:
        user_id = gen_id('u')
        uid[username] = user_id
        conn.execute(
            'INSERT INTO users (id, username, nickname, password_hash, role, avatar_color,'
            ' email, created_at, status) VALUES (?,?,?,?,?,?,?,?,?)',
            (user_id, username, nickname, hash_password(pwd), role,
             avatar_color_of(nickname), email, now - 90 * 86400 * 1000, 'active'))
    print(f'✓ 用户 {len(USERS)} 个（admin/admin123 管理员，其余 123456）')

    nickname_of = {u[0]: u[2] for u in USERS}

    # ---- 表白 ----
    cid = {}
    for i, (to, content, from_name, author_key, color, hours_ago) in enumerate(CONFESSIONS, 1):
        confession_id = gen_id('c')
        cid[i] = confession_id
        conn.execute(
            'INSERT INTO confessions (id, to_name, content, from_name, author_id, color,'
            ' images, created_at, status) VALUES (?,?,?,?,?,?,?,?,?)',
            (confession_id, to, content, from_name, uid[author_key], color,
             json.dumps([], ensure_ascii=False), now - hours_ago * 3600 * 1000, 'normal'))
    print(f'✓ 表白 {len(CONFESSIONS)} 条')

    # ---- 评论（含楼中楼）----
    cmid = {}
    for seq, (conf_seq, author_key, content, reply_seq, minutes_ago) in enumerate(COMMENTS, 1):
        comment_id = gen_id('cm')
        cmid[seq] = comment_id
        reply_to = cmid.get(reply_seq) if reply_seq else None
        reply_nick = None
        if reply_seq:
            replied_author = COMMENTS[reply_seq - 1][1]
            reply_nick = nickname_of[replied_author]
        created = now - (CONFESSIONS[conf_seq - 1][5] * 60 - abs(minutes_ago) * -1) * 60 * 1000
        # 简化：评论时间 = 表白发布后若干分钟
        base = now - CONFESSIONS[conf_seq - 1][5] * 3600 * 1000
        created = base + (seq * 17 + 5) * 60 * 1000
        conn.execute(
            'INSERT INTO comments (id, confession_id, author_id, nickname, content,'
            ' reply_to, reply_to_nickname, created_at, status) VALUES (?,?,?,?,?,?,?,?,?)',
            (comment_id, cid[conf_seq], uid[author_key], nickname_of[author_key], content,
             reply_to, reply_nick, created, 'normal'))
    print(f'✓ 评论 {len(COMMENTS)} 条（含楼中楼回复）')

    # ---- 点赞 ----
    like_count = 0
    for conf_seq, user_keys in LIKES:
        for k in user_keys:
            conn.execute('INSERT INTO likes (user_id, confession_id, created_at) VALUES (?,?,?)',
                         (uid[k], cid[conf_seq], now))
            like_count += 1
    print(f'✓ 点赞 {like_count} 个')

    # ---- 通知（示例：辰昊收到点赞/评论通知）----
    notif_seed = [
        ('like', 'chenhao', 'xiaomei', 1, f'赞了你的表白「{CONFESSIONS[0][1][:12]}…」', 1),
        ('comment', 'chenhao', 'yaya', 1, f'评论了你的表白「{COMMENTS[2][2][:12]}…」', 0),
        ('reply', 'xiaomei', 'chenhao', 5, f'回复了你「{COMMENTS[6][2][:12]}…」', 0),
    ]
    for type_, to_key, from_key, conf_seq, text, read in notif_seed:
        conn.execute(
            'INSERT INTO notifications (id, type, to_user_id, from_user_id, from_nickname,'
            ' confession_id, text, read, created_at) VALUES (?,?,?,?,?,?,?,?,?)',
            (gen_id('n'), type_, uid[to_key], uid[from_key], nickname_of[from_key],
             cid[conf_seq], text, read, now - 3600 * 1000))
    print(f'✓ 通知 {len(notif_seed)} 条')

    # ---- 设置（默认全关，与前端档案一致）----
    for key in ('emailVerificationEnabled', 'captchaEnabled', 'sensitiveFilterEnabled'):
        conn.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, '0'))
    print('✓ 系统设置：三个开关默认关闭')

    conn.commit()
    conn.close()
    print(f'\n种子数据写入完成 → {DB_PATH}')


if __name__ == '__main__':
    main()
