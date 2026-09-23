# Lovewall 表白墙后端

基于 **Python + Flask + SQLite + JWT 鉴权** 的前后端分离后端服务，完整实现前端 API 档案（v1.0.0）定义的全部业务契约：认证、表白、评论（楼中楼）、点赞、通知、找回密码、管理员后台与系统设置，共 **40+ REST 接口**。

## 快速开始

```bash
# 1. 安装依赖（Python ≥ 3.10）
pip install -r requirements.txt

# 2. 初始化数据库 + 种子数据（SQLite，自动建表）
python seed.py            # 首次执行；python seed.py --force 可清空重建

# 3. 启动服务（默认 0.0.0.0:5000）
python app.py
```

演示账号：

| 账号 | 密码 | 角色 |
|---|---|---|
| admin | admin123 | 管理员（内置超管，禁止删除/封禁） |
| xiaomei / chenhao / yaya / luming / tangtang | 123456 | 普通用户（小美/辰昊/丫丫/陆鸣/糖糖） |

## 技术栈与架构

- **Flask 3** + 蓝图分模块（auth / wall / notifications / users / admin / settings）
- **SQLite**（WAL 模式，零配置单文件 `lovewall.db`，请求级连接）
- **JWT 鉴权**：`Authorization: Bearer <token>`；登出服务端吊销（jti 黑名单）；封禁/改角色立即生效（每请求回查用户）
- **bcrypt** 密码哈希（替换前端演示用的 djb2 Mock 哈希）
- **flask-cors** 全开放跨域，适配前端本地开发

```
routes/            # REST 接口层
  auth.py          # 注册/登录/登出/邮箱验证码/图形验证码/找回密码三步
  wall.py          # 表白 CRUD/点赞/评论楼中楼/图片上传
  notifications.py # 通知列表/已读/清空
  users.py         # 个人资料/改密码/我的表白
  admin.py         # 统计/用户管理/内容管理/系统设置
  settings.py      # 公开设置读取（注册页初始化用）
common/            # 公共层
  db.py security.py decorators.py responses.py
  validators.py sensitive.py throttle.py notify.py
  confession_queries.py serializers.py settings_store.py
schema.sql         # 建表脚本（9 张表）
seed.py            # 种子数据（6 账号 + 12 表白 + 楼中楼评论 + 点赞 + 通知）
config.py          # 全部配置项（环境变量可覆盖）
```

## 接口总览

统一响应：`{ code, message, data }`；`code=0` 成功，错误时 `code` 与 HTTP 状态码一致，`message` 为中文文案（与前端现有文案完全一致，视图层可零改动展示）。

### 认证 `/api/auth`
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /register | 注册并自动登录；开关开启时强制校验图形/邮箱验证码 |
| POST | /login | 登录，返回 `{ user, token }` |
| POST | /logout | 登出（token 立即吊销） |
| GET | /session | 会话恢复（前端 init 用） |
| POST | /email-code | 6 位邮箱验证码（5 分钟有效/一次性/60s 防重发；开发模式回显） |
| GET | /captcha | 4 位图形验证码 SVG（不区分大小写/一次性） |
| POST | /forgot/verify | 找回密码第一步：用户名+邮箱匹配 → 重置凭证 |
| POST | /forgot/reset | 第三步：重置凭证+邮箱验证码 → 设置新密码 |

### 表白墙 `/api`
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /confessions | 分页+排序(latest/hottest)+keyword+color；`mine=1` 查自己的（含隐藏） |
| GET | /confessions/:id | 详情；hidden 仅作者/管理员可见 |
| POST | /confessions | 发布（60s 限频、敏感词过滤、图片≤3 张） |
| DELETE | /confessions/:id | 删除自己的表白 |
| PUT / DELETE | /confessions/:id/like | 点赞 / 取消点赞 |
| POST | /confessions/:id/comments | 评论/楼中楼（30s 限频，body 携带 replyTo） |
| POST | /upload/images | base64 图片批量上传 → URL |
| GET | /uploads/:file | 图片静态服务 |

### 通知 / 用户 / 设置
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/notifications | 当前用户通知 + unreadCount |
| PUT | /api/notifications/:id/read、/read-all | 单条/全部已读 |
| DELETE | /api/notifications | 清空当前用户通知 |
| GET | /api/users/me | 当前用户信息 |
| PATCH | /api/users/me | 改昵称/头像色（服务端自动同步历史署名） |
| PUT | /api/users/me/password | 修改密码 |
| GET | /api/users/me/confessions | 我的表白 |
| GET | /api/settings | 公开读取三个功能开关 |

### 管理员 `/api/admin`（全部需 admin 角色）
`GET /stats`（仪表盘聚合）、`GET/POST /users`、`PATCH/DELETE /users/:id`（角色/封禁/重置密码为 123456）、`GET /confessions`（含 hidden+状态筛选）、`PATCH /confessions/:id/status`、`DELETE /confessions/:id`、`POST /confessions/batch-delete`、`GET /comments`（展平+表白摘要）、`DELETE /comments/:id`、`POST /comments/batch-delete`、`GET/PUT /settings`。

## 业务规则（全部服务端强制，前端无法绕过）

- **频率限制**：表白 60s/条、评论 30s/条（基于用户表时间戳，重启不丢失）
- **敏感词过滤**：后台开关控制，忽略大小写，命中替换为等长 `*`，返回 `filtered` 计数
- **验证码安全**：邮箱 6 位（5 分钟/一次性/**错误 5 次销毁**/60s 防重发）、图形 4 位 SVG（一次性/不分大小写）
- **找回密码闸门**：同用户名 60s 冷却；连续失败 5 次锁 15 分钟；重置凭证（resetToken）**用后即焚**，杜绝凭证重放
- **输入校验**：用户名 `^[a-zA-Z0-9_]{3,20}$` 唯一、密码 ≥6 位、昵称 ≤20 字、邮箱格式+唯一、表白 ≤200 字、评论 ≤100 字、收件人 ≤20 字
- **通知规则**：点赞→表白作者；评论→表白作者；回复→被回复者（若同为表白作者只收一条 reply）；自己给自己不发；每用户保留最近 50 条
- **权限**：游客仅浏览；登录用户发布/互动/个人中心；管理员后台全套；内置超管 `admin` 禁止删除/封禁/改角色
- **图片**：base64 落盘为静态文件 URL（≤3 张、单张 ≤6MB），`uploads/` 目录；**删除表白时同步清理图片文件**
- **请求体上限**：30MB（超限返回 413 中文提示，防止伪造巨型请求耗尽内存）

## 测试

```bash
# 先启动服务（python app.py），另开终端：
python tests/test_api.py
```

`tests/test_api.py` 共 **101 项断言**，覆盖全部接口 + 安全专项（验证码 5 次限制、重置凭证一次性、413 上限、图片文件清理、封禁踢下线、token 吊销等）。

## 与前端对接

前端仅需将 Pinia store actions 中的 localStorage 读写替换为对应 REST 请求（映射表见 API 档案第 7 章），请求头携带 `Authorization: Bearer <token>`：

- 登录/注册响应中的 `token` 存 localStorage，替换原 `lovewall:session`
- `message` 字段为与原 Mock 一致的中文文案，可直接用于 `ElMessage` 提示
- 表白对象新增 `likedByMe` / `likeCount` / `commentCount` 便捷字段，`likes` 仍为用户 id 数组（形状兼容）
- 图片字段从 base64 改为 URL（发布接口同时兼容 base64 自动落盘）

## 配置项（环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| LOVEWALL_SECRET_KEY | lovewall-dev-secret-change-me | JWT 签名密钥（**生产必改**） |
| LOVEWALL_DB | ./lovewall.db | SQLite 文件路径 |
| LOVEWALL_TOKEN_DAYS | 7 | token 有效期（天） |
| LOVEWALL_UPLOAD_DIR | ./uploads | 图片存储目录 |
| LOVEWALL_MAIL_DEBUG | 1 | 开发模式回显邮箱验证码；生产置 0 并接入 SMTP |

## 生产部署建议

- 使用 gunicorn：`gunicorn -w 4 -b 0.0.0.0:5000 app:app`（SQLite WAL 支持多 worker 读，写并发低场景适用；高并发可换 MySQL/PostgreSQL，仅需替换 `common/db.py`）
- 修改 `SECRET_KEY`，启用 HTTPS
- 邮箱验证码接入真实 SMTP（`routes/auth.py` 发信占位处），关闭 `MAIL_DEBUG`
- 图片迁移至对象存储（预签名 URL 直传），接口已预留独立上传端点
