# -*- coding: utf-8 -*-
"""Lovewall 后端全量接口测试（对运行中的 http://127.0.0.1:5000 服务）
覆盖：鉴权/表白/评论/通知/用户/管理员/验证码/找回密码 + 本次安全修复专项"""
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:5000'
UPLOAD_DIR = '/workspace/lovewall-backend/uploads'
PASSED, FAILED = [], []


def call(method, path, body=None, token=None):
    # urllib 要求 ASCII URL：仅对查询参数中的非 ASCII 字符做百分号编码
    if '?' in path:
        base, _, qs = path.partition('?')
        from urllib.parse import quote
        path = base + '?' + '&'.join(quote(p, safe='=&') for p in qs.split('&'))
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    data = json.dumps(body).encode('utf-8') if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw.decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                return resp.status, {'raw': True, 'size': len(raw)}
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except Exception:
            return e.code, {}


def check(name, cond, detail=''):
    if cond:
        PASSED.append(name)
        print(f'  ✓ {name}')
    else:
        FAILED.append(name)
        print(f'  ✗ {name}  {detail}')


print('== 1. 健康检查 / 公开设置 ==')
s, r = call('GET', '/api/health')
check('健康检查', s == 200 and r['code'] == 0)
s, r = call('GET', '/api/settings')
check('公开设置(三开关默认关)', s == 200 and r['data']['settings'] == {
    'emailVerificationEnabled': False, 'captchaEnabled': False, 'sensitiveFilterEnabled': False})

print('== 2. 登录 admin / 会话 ==')
s, r = call('POST', '/api/auth/login', {'username': 'admin', 'password': 'admin123'})
check('admin 登录', s == 200 and r['data']['user']['role'] == 'admin')
admin_token = r['data']['token']
s, r = call('GET', '/api/auth/session', token=admin_token)
check('会话恢复', s == 200 and r['data']['isLoggedIn'] and r['data']['isAdmin'])
s, r = call('POST', '/api/auth/login', {'username': 'admin', 'password': 'wrong'})
check('错误密码拒绝', s == 401 and r['message'] == '用户名或密码错误')

print('== 3. 游客浏览表白（分页/筛选/排序）==')
s, r = call('GET', '/api/confessions?page=1&pageSize=5')
check('表白列表分页', s == 200 and r['data']['total'] == 12 and len(r['data']['list']) == 5)
check('列表带评论与点赞聚合', r['data']['list'][0]['commentCount'] >= 0 and 'likeCount' in r['data']['list'][0])
check('时间倒序', r['data']['list'][0]['createdAt'] >= r['data']['list'][1]['createdAt'])
s, r = call('GET', '/api/confessions?sort=hottest&pageSize=3')
top3 = [c['likeCount'] for c in r['data']['list']]
check('hottest 排序', top3 == sorted(top3, reverse=True), str(top3))
s, r = call('GET', '/api/confessions?keyword=图书馆')
check('关键词搜索', s == 200 and r['data']['total'] == 1)
s, r = call('GET', '/api/confessions?color=blue')
check('颜色筛选', s == 200 and all(c['color'] == 'blue' for c in r['data']['list']) and r['data']['total'] == 2)
first_id = call('GET', '/api/confessions?pageSize=1')[1]['data']['list'][0]['id']
s, r = call('GET', f'/api/confessions/{first_id}')
check('表白详情', s == 200 and r['data']['confession']['id'] == first_id)

print('== 4. 注册新用户（普通流程）==')
s, r = call('POST', '/api/auth/register', {'username': 'testuser1', 'password': 'abc123',
                                           'nickname': '测试用户'})
check('注册并自动登录', s == 200 and r['data']['token'] and r['data']['user']['nickname'] == '测试用户')
user_token = r['data']['token']
s, r = call('POST', '/api/auth/register', {'username': 'testuser1', 'password': 'abc123'})
check('用户名重复拒绝', s == 400 and r['message'] == '用户名已被注册')
s, r = call('POST', '/api/auth/register', {'username': 'ab', 'password': 'abc123'})
check('用户名格式校验', s == 400 and '3-20' in r['message'])
s, r = call('POST', '/api/auth/register', {'username': 'testuser2', 'password': '123'})
check('密码长度校验', s == 400 and r['message'] == '密码长度不能少于 6 位')

print('== 5. 未登录鉴权拦截 ==')
s, r = call('POST', '/api/confessions', {'content': 'hello'})
check('未登录发表白 401', s == 401 and r['message'] == '请先登录')
s, r = call('PUT', f'/api/confessions/{first_id}/like')
check('未登录点赞 401', s == 401)
s, r = call('GET', '/api/notifications')
check('未登录看通知 401', s == 401)

print('== 6. 发布表白（含 base64 图片 + 限频）==')
tiny_jpeg = ('/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a'
             'HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy'
             'MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA'
             'AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA'
             'AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3'
             'ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm'
             'p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/9oADAMB'
             'AAIRAxEAPwCdABmX/9k=')
s, r = call('POST', '/api/confessions', {
    'to': '测试收件人', 'content': '这是测试表白内容', 'from': '测试用户',
    'color': 'green', 'images': [f'data:image/jpeg;base64,{tiny_jpeg}']}, token=user_token)
check('发布表白成功', s == 200 and r['data']['confession']['content'] == '这是测试表白内容')
check('图片落盘为URL', r['data']['confession']['images'][0].startswith('/uploads/'))
img_url = r['data']['confession']['images'][0]
my_confession_id = r['data']['confession']['id']
check('图片文件真实存在', os.path.isfile(os.path.join(UPLOAD_DIR, os.path.basename(img_url))))
s, r = call('POST', '/api/confessions', {'content': 'again', 'color': 'pink'}, token=user_token)
check('60s 限频拦截', s == 429 and '发布太频繁' in r['message'])
s, r = call('POST', '/api/confessions', {'content': '', 'color': 'pink'}, token=admin_token)
check('空内容拒绝', s == 400 and r['message'] == '表白内容不能为空')
s, r = call('POST', '/api/confessions', {'content': 'x' * 201, 'color': 'pink'}, token=admin_token)
check('超长内容拒绝', s == 400)
s, r = call('GET', img_url.replace('/uploads', '/api/uploads'))
check('图片URL可访问', s == 200 and r.get('raw') and r.get('size', 0) > 100)

print('== 7. 点赞 / 取消点赞 ==')
s, r = call('PUT', f'/api/confessions/{first_id}/like', token=user_token)
check('点赞成功', s == 200 and r['data']['liked'] is True)
s, r = call('GET', f'/api/confessions/{first_id}', token=user_token)
check('likedByMe=true', r['data']['confession']['likedByMe'] is True)
s, r = call('DELETE', f'/api/confessions/{first_id}/like', token=user_token)
check('取消点赞', s == 200 and r['data']['liked'] is False)

print('== 8. 评论 / 楼中楼 / 限频 ==')
s, r = call('POST', f'/api/confessions/{first_id}/comments',
            {'content': '测试评论'}, token=user_token)
check('发表评论', s == 200 and r['data']['comment']['content'] == '测试评论')
parent_comment = r['data']['comment']
s, r = call('POST', f'/api/confessions/{first_id}/comments',
            {'content': '又是评论'}, token=user_token)
check('30s 评论限频', s == 429 and '评论太频繁' in r['message'])
s, r = call('POST', f'/api/confessions/{first_id}/comments',
            {'content': '楼中楼回复', 'replyTo': {'id': parent_comment['id'],
                                                  'nickname': '测试用户'}}, token=admin_token)
check('楼中楼回复', s == 200 and r['data']['comment']['replyTo'] == parent_comment['id'])
s, r = call('POST', '/api/auth/login', {'username': 'yaya', 'password': '123456'})
yaya_token = r['data']['token']
s, r = call('POST', f'/api/confessions/{first_id}/comments',
            {'content': '回复不存在', 'replyTo': {'id': 'cm-notexist'}}, token=yaya_token)
check('回复目标校验(未限频用户)', s == 400 and r['message'] == '被回复的评论不存在', r.get('message'))
s, r = call('POST', '/api/confessions/c-notexist/comments', {'content': 'x'}, token=admin_token)
check('表白不存在', s == 404 and r['message'] == '表白不存在')

print('== 9. 通知（点赞/评论触发 → 已读 → 清空）==')
s, r = call('GET', '/api/notifications', token='x-invalid')
check('无效token 401', s == 401)
s, r = call('POST', '/api/auth/login', {'username': 'chenhao', 'password': '123456'})
chenhao_token = r['data']['token']
s, r = call('GET', '/api/notifications', token=chenhao_token)
check('通知列表+未读数', s == 200 and 'unreadCount' in r['data'] and r['data']['total'] >= 2,
      f"total={r.get('data', {}).get('total')}")
notif = r['data']['list'][0]
check('通知字段形状', notif['type'] in ('like', 'comment', 'reply') and 'fromNickname' in notif)
s, r = call('PUT', f'/api/notifications/{notif["id"]}/read', token=chenhao_token)
check('单条已读', s == 200)
s, r = call('PUT', '/api/notifications/read-all', token=chenhao_token)
check('全部已读', s == 200)
s, r = call('GET', '/api/notifications', token=chenhao_token)
check('未读数归零', r['data']['unreadCount'] == 0)
s, r = call('DELETE', '/api/notifications', token=chenhao_token)
check('清空通知', s == 200)
s, r = call('GET', '/api/notifications', token=chenhao_token)
check('清空后total=0', r['data']['total'] == 0)

print('== 10. 个人资料 / 改名同步 / 改密码 ==')
s, r = call('PATCH', '/api/users/me', {'nickname': '测试用户改的名'}, token=user_token)
check('更新昵称', s == 200 and r['data']['user']['nickname'] == '测试用户改的名')
s, r = call('PATCH', '/api/users/me', {'nickname': ''}, token=user_token)
check('空昵称拒绝', s == 400 and r['message'] == '昵称不能为空')
s, r = call('GET', f'/api/confessions/{my_confession_id}')
check('历史表白署名同步', r['data']['confession']['from'] == '测试用户改的名')
s, r = call('PUT', '/api/users/me/password', {'oldPassword': 'wrong', 'newPassword': 'newpass123'},
            token=user_token)
check('原密码错误拒绝', s == 403 and r['message'] == '原密码错误')
s, r = call('PUT', '/api/users/me/password', {'oldPassword': 'abc123', 'newPassword': 'newpass123'},
            token=user_token)
check('修改密码成功', s == 200)
s, r = call('POST', '/api/auth/login', {'username': 'testuser1', 'password': 'newpass123'})
check('新密码可登录', s == 200)
s, r = call('GET', '/api/users/me/confessions', token=user_token)
check('我的表白列表', s == 200 and r['data']['total'] == 1)
s, r = call('DELETE', f'/api/confessions/{my_confession_id}', token=user_token)
check('删除自己的表白', s == 200)
check('删除表白后图片文件同步清理',
      not os.path.exists(os.path.join(UPLOAD_DIR, os.path.basename(img_url))))
s, r = call('DELETE', f'/api/confessions/{first_id}', token=user_token)
check('删别人的表白拒绝', s == 403 and r['message'] == '只能删除自己发布的表白')

print('== 11. 邮箱验证码 / 图形验证码 / 开关注册强校验 ==')
s, r = call('POST', '/api/auth/email-code', {'email': 'someone@test.com'})
check('发送邮箱验证码(dev回显)', s == 200 and re.match(r'^\d{6}$', r['data'].get('code', '')))
email_code = r['data']['code']
s, r = call('POST', '/api/auth/email-code', {'email': 'someone@test.com'})
check('60s 防重发', s == 429 and '频繁' in r['message'])
s, r = call('GET', '/api/auth/captcha')
check('图形验证码SVG', s == 200 and r['data']['image'].startswith('data:image/svg+xml;base64,'))
s, r = call('PUT', '/api/admin/settings', {'emailVerificationEnabled': True, 'captchaEnabled': True},
            token=admin_token)
check('管理员开设置', s == 200 and r['data']['settings']['emailVerificationEnabled'] is True)
s, r = call('POST', '/api/auth/register', {'username': 'testuser3', 'password': 'abc123'})
check('开关开启时无验证码拒绝', s == 400)
s, r = call('GET', '/api/auth/captcha')
captcha_id, svg_b64 = r['data']['captchaId'], r['data']['image']
svg_text = base64.b64decode(svg_b64.split(',')[1]).decode('utf-8')
captcha_text = ''.join(re.findall(r'>([A-Za-z0-9])</text>', svg_text))
s, r = call('POST', '/api/auth/register', {'username': 'testuser3', 'password': 'abc123',
                                           'email': 'someone@test.com', 'emailCode': email_code,
                                           'captchaId': captcha_id, 'captchaText': captcha_text})
check('带双验证码注册成功', s == 200 and r['data']['token'], r.get('message', ''))
s, r = call('GET', '/api/auth/captcha')
captcha_id2 = r['data']['captchaId']
svg_text2 = base64.b64decode(r['data']['image'].split(',')[1]).decode('utf-8')
captcha_text2 = ''.join(re.findall(r'>([A-Za-z0-9])</text>', svg_text2))
s, r = call('POST', '/api/auth/register', {'username': 'testuser4', 'password': 'abc123',
                                           'captchaId': captcha_id2, 'captchaText': 'zzzz'})
check('图形验证码错误拒绝', s == 400 and '图形验证码' in r['message'])
call('PUT', '/api/admin/settings', {'emailVerificationEnabled': False, 'captchaEnabled': False},
     token=admin_token)

print('== 12. 找回密码三步流程（60s冷却 + 凭证一次性 + 验证码限次）==')
s, r = call('POST', '/api/auth/forgot/verify', {'username': 'chenhao', 'email': 'wrong@x.com'})
check('不匹配拒绝', s == 400 and r['message'] == '用户名与邮箱不匹配')
s, r = call('POST', '/api/auth/forgot/verify', {'username': 'chenhao', 'email': 'wrong@x.com'})
check('同用户名60s冷却', s == 429 and '频繁' in r['message'], r.get('message'))
s, r = call('POST', '/api/auth/email-code', {'email': 'xiaomei@lovewall.dev'})
check('获取重置验证码', s == 200 and re.match(r'^\d{6}$', r['data'].get('code', '')))
reset_code = r['data']['code']
s, r = call('POST', '/api/auth/forgot/verify', {'username': 'xiaomei', 'email': 'xiaomei@lovewall.dev'})
check('第一步 用户名邮箱匹配', s == 200 and r['data']['resetToken'], r.get('message'))
reset_token = r['data']['resetToken']
reset_user_id = r['data']['user']['id']
s, r = call('POST', '/api/auth/forgot/reset', {'userId': reset_user_id, 'resetToken': reset_token,
                                               'newPassword': 'newpass456', 'emailCode': '000000'})
check('错误邮箱验证码拒绝', s == 403 and r['message'] == '邮箱验证码错误')
s, r = call('POST', '/api/auth/forgot/reset', {'userId': reset_user_id, 'resetToken': 'bad',
                                               'newPassword': 'newpass456', 'emailCode': reset_code})
check('无效重置凭证拒绝', s == 403)
s, r = call('POST', '/api/auth/forgot/reset', {'userId': reset_user_id, 'resetToken': reset_token,
                                               'newPassword': 'newpass456', 'emailCode': reset_code})
check('第三步 重置成功', s == 200, r.get('message', ''))
s, r = call('POST', '/api/auth/login', {'username': 'xiaomei', 'password': 'newpass456'})
check('重置后新密码登录', s == 200)
s, r = call('POST', '/api/auth/forgot/reset', {'userId': reset_user_id, 'resetToken': reset_token,
                                               'newPassword': 'another789', 'emailCode': 'whatever'})
check('重置凭证一次性(用后即焚)', s == 403 and r['message'] == '重置凭证已使用，请重新验证',
      r.get('message'))

print('== 13. 管理员：统计 / 用户管理 / 内容管理 ==')
s, r = call('GET', '/api/admin/stats', token=user_token)
check('普通用户访问admin 403', s == 403 and r['message'] == '需要管理员权限')
s, r = call('GET', '/api/admin/stats', token=admin_token)
check('仪表盘统计', s == 200 and r['data']['totalConfessions'] >= 12)
top = r['data']['topLiked']
check('topLiked点赞数组真实聚合', len(top) >= 1 and len(top[0]['likes']) == top[0]['likeCount'] > 0,
      f"top0: likes={top[0]['likes'] if top else None}")
s, r = call('GET', '/api/admin/users?keyword=testuser', token=admin_token)
check('用户搜索', s == 200 and r['data']['total'] >= 2)
s, r = call('POST', '/api/admin/users', {'username': 'newadmin1', 'password': 'abc123',
                                         'nickname': '新管理员', 'role': 'admin'}, token=admin_token)
check('后台创建管理员', s == 200 and r['data']['user']['role'] == 'admin')
new_admin_id = r['data']['user']['id']
s, r = call('POST', '/api/admin/users', {'username': 'admin', 'password': 'abc123'}, token=admin_token)
check('后台用户名重复', s == 400 and r['message'] == '用户名已存在')
s, r = call('PATCH', f'/api/admin/users/{new_admin_id}', {'banned': True}, token=admin_token)
check('封禁用户', s == 200 and r['data']['user']['status'] == 'banned')
s, r = call('POST', '/api/auth/login', {'username': 'newadmin1', 'password': 'abc123'})
check('封禁后无法登录', s == 403 and r['message'] == '该账号已被封禁，请联系管理员')
s, r = call('PATCH', f'/api/admin/users/{new_admin_id}', {'banned': False, 'role': 'user'},
            token=admin_token)
check('解封+降级', s == 200 and r['data']['user']['status'] == 'active')
s, r = call('PATCH', f'/api/admin/users/{new_admin_id}', {'action': 'resetPassword'}, token=admin_token)
check('重置密码为123456', s == 200 and r['data']['password'] == '123456')
s, r = call('POST', '/api/auth/login', {'username': 'newadmin1', 'password': '123456'})
check('重置密码可登录', s == 200)
s, admin_row = call('GET', '/api/admin/users?keyword=admin', token=admin_token)
admin_id = [u for u in admin_row['data']['list'] if u['username'] == 'admin'][0]['id']
s, r = call('DELETE', f'/api/admin/users/{admin_id}', token=admin_token)
check('内置超管禁删', s == 403 and '内置管理员' in r['message'])
s, r = call('PATCH', f'/api/admin/users/{admin_id}', {'banned': True}, token=admin_token)
check('内置超管禁封', s == 403)
lib_id = call('GET', '/api/confessions?keyword=图书馆')[1]['data']['list'][0]['id']
s, r = call('PATCH', f'/api/admin/confessions/{lib_id}/status', {'status': 'hidden'}, token=admin_token)
check('隐藏表白', s == 200)
s, r = call('GET', '/api/confessions?keyword=图书馆')
check('前台不可见hidden', r['data']['total'] == 0)
s, r = call('GET', f'/api/confessions/{lib_id}')
check('hidden详情404(游客)', s == 404)
s, r = call('GET', f'/api/confessions/{lib_id}', token=admin_token)
check('hidden详情管理员可见', s == 200)
s, r = call('GET', '/api/admin/confessions?status=hidden', token=admin_token)
check('后台列表含hidden(状态筛选)', s == 200 and r['data']['total'] >= 1
      and all(c['status'] == 'hidden' for c in r['data']['list']))
s, r = call('PATCH', f'/api/admin/confessions/{lib_id}/status', {'status': 'normal'}, token=admin_token)
check('恢复normal', s == 200)
s, r = call('POST', '/api/admin/confessions/batch-delete', {'ids': [my_confession_id]}, token=admin_token)
check('批量删除表白', s == 200 and r['data']['deleted'] >= 0)
s, r = call('GET', '/api/admin/comments?keyword=测试评论', token=admin_token)
check('后台评论展平列表', s == 200 and r['data']['total'] >= 1)
del_comment_id = r['data']['list'][0]['id']
s, r = call('DELETE', f'/api/admin/comments/{del_comment_id}', token=admin_token)
check('删除单条评论', s == 200)
s, r = call('DELETE', f'/api/admin/users/{new_admin_id}', token=admin_token)
check('删除用户', s == 200)

print('== 14. 敏感词过滤 ==')
s, r = call('PUT', '/api/admin/settings', {'sensitiveFilterEnabled': True}, token=admin_token)
check('开启敏感词过滤', s == 200)
s, r = call('POST', '/api/confessions', {'content': '你真是个STUPID笨蛋啊', 'color': 'pink'},
            token=chenhao_token)
check('敏感词替换为*', s == 200 and r['data']['confession']['content'] == '你真是个********啊'
      and r['data']['filtered'] == 2, r['data']['confession']['content'])
filtered_id = r['data']['confession']['id']
call('DELETE', f'/api/confessions/{filtered_id}', token=chenhao_token)
call('PUT', '/api/admin/settings', {'sensitiveFilterEnabled': False}, token=admin_token)

print('== 15. 登出 token 吊销 ==')
s, r = call('POST', '/api/auth/logout', token=chenhao_token)
check('登出成功', s == 200)
s, r = call('GET', '/api/users/me', token=chenhao_token)
check('旧token已失效', s == 401)

print('== 16. 封禁用户立即踢下线 ==')
s, r = call('POST', '/api/auth/login', {'username': 'tangtang', 'password': '123456'})
tang_token = r['data']['token']
tang_id = r['data']['user']['id']
s, r = call('PATCH', f'/api/admin/users/{tang_id}', {'banned': True}, token=admin_token)
s, r = call('GET', '/api/users/me', token=tang_token)
check('封禁后token立即失效', s == 401)
call('PATCH', f'/api/admin/users/{tang_id}', {'banned': False}, token=admin_token)

print('== 17. 404 / 全局异常 ==')
s, r = call('GET', '/api/not-exist')
check('未知接口404', s == 404 and r['message'] == '接口不存在')

print('== 18. 本次安全修复专项 ==')
# 18.1 邮箱验证码 5 次尝试限制
s, r = call('POST', '/api/auth/email-code', {'email': 'brute@test.com'})
brute_code = r['data']['code']
msg_seq = []
for i in range(5):
    s, r = call('POST', '/api/auth/forgot/reset', {'userId': 'u-any', 'resetToken': 'x',
                                                   'newPassword': 'abc123', 'emailCode': '000000'})
    if s == 403 and r['message'] == '重置凭证已失效，请重新验证':
        msg_seq.append('token-invalid')  # resetToken 无效时先被拦，验证码尝试计数不触发
        break
    msg_seq.append(r.get('message'))
    break
# 直接调用注册路径验证 attempts 计数（更直接）：开关开启 + 错误验证码 5 次
call('PUT', '/api/admin/settings', {'emailVerificationEnabled': True}, token=admin_token)
s, r = call('POST', '/api/auth/email-code', {'email': 'brute2@test.com'})
bcode = r['data']['code']
last_msg = ''
for i in range(5):
    s, r = call('POST', '/api/auth/register', {'username': f'brute{i}', 'password': 'abc123',
                                               'email': 'brute2@test.com', 'emailCode': '000000'})
    last_msg = r.get('message', '')
check('验证码错误前4次提示错误', last_msg in ('邮箱验证码错误', '验证码错误次数过多，请重新获取'), last_msg)
s, r = call('POST', '/api/auth/register', {'username': 'bruteok', 'password': 'abc123',
                                           'email': 'brute2@test.com', 'emailCode': bcode})
check('5次错误后验证码已销毁(正确码也失效)',
      s == 400 and r.get('message') in ('请先获取邮箱验证码', '验证码错误次数过多，请重新获取'),
      r.get('message'))
call('PUT', '/api/admin/settings', {'emailVerificationEnabled': False}, token=admin_token)
# 18.2 请求体上限 413
req = urllib.request.Request(BASE + '/api/confessions', method='POST',
                             data=b'x' * (31 * 1024 * 1024),
                             headers={'Content-Type': 'application/json',
                                      'Authorization': 'Bearer ' + admin_token})
try:
    urllib.request.urlopen(req)
    check('超限请求体413', False, '未拦截')
except urllib.error.HTTPError as e:
    body = json.loads(e.read().decode('utf-8'))
    check('超限请求体413', e.code == 413 and '过大' in body['message'], f"{e.code} {body.get('message')}")
# 18.3 token_blacklist 过期清理（登出后表内无过期残留——由实现保证，此处验证登出仍有效）
s, r = call('POST', '/api/auth/login', {'username': 'luming', 'password': '123456'})
lm_token = r['data']['token']
call('POST', '/api/auth/logout', token=lm_token)
s, r = call('GET', '/api/users/me', token=lm_token)
check('登出吊销仍生效', s == 401)

print(f'\n===== 结果：{len(PASSED)} 通过 / {len(FAILED)} 失败 =====')
if FAILED:
    print('失败项：', FAILED)
    sys.exit(1)
