# 💕 Lovewall 表白墙后端

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

基于 **Flask + SQLite + JWT** 的前后端分离表白墙后端服务，覆盖认证、表白、评论（楼中楼）、点赞、通知、找回密码、管理员后台与系统设置全业务链，共 **27 个 REST 接口**。

---

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/Jay/lovewall_backend.git
cd lovewall_backend

# 2. 创建虚拟环境 & 安装依赖
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt

# 3. 初始化数据库 + 种子数据
python seed.py              # python seed.py --force 可清空重建

# 4. 启动服务
python app.py               # 默认 http://0.0.0.0:5000
```

### 演示账号

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | admin123 | 管理员（内置超管，禁止删除/封禁） |
| xiaomei | 123456 | 普通用户（小美） |
| chenhao | 123456 | 普通用户（辰昊） |
| yaya | 123456 | 普通用户（丫丫） |
| luming | 123456 | 普通用户（陆鸣） |
| tangtang | 123456 | 普通用户（糖糖） |

---

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| Web 框架 | Flask 3 | 蓝图分模块 |
| 数据库 | SQLite (WAL) | 零配置单文件，请求级连接 |
| 鉴权 | JWT + bcrypt | Bearer Token，登出服务端吊销 |
| 跨域 | flask-cors | 全开放，适配前端本地开发 |
| 验证码 | SVG 图形码 + 邮箱码 | 一次性，防暴力枚举 |

---

## 项目结构

```
lovewall_backend/
├── app.py                  # 应用入口（Flask 工厂 + 错误处理）
├── config.py               # 全局配置（环境变量可覆盖）
├── schema.sql              # 建表脚本（11 张表）
├── seed.py                 # 种子数据
├── requirements.txt        # 依赖
├── routes/                 # REST 接口层
│   ├── auth.py             #   注册/登录/登出/验证码/找回密码
│   ├── wall.py             #   表白 CRUD/点赞/评论/图片上传
│   ├── notifications.py    #   通知列表/已读/清空
│   ├── users.py            #   个人资料/改密码/我的表白
│   ├── admin.py            #   仪表盘/用户管理/内容管理/系统设置
│   └── settings.py         #   公开设置读取
├── common/                 # 公共层
│   ├── db.py               #   数据库连接与查询
│   ├── security.py         #   JWT/bcrypt/ID 生成
│   ├── decorators.py       #   鉴权装饰器
│   ├── responses.py        #   统一响应格式
│   ├── validators.py       #   输入校验
│   ├── sensitive.py        #   敏感词过滤
│   ├── throttle.py         #   频率限制
│   ├── notify.py           #   通知触发
│   ├── serializers.py      #   序列化（DB 行 → 前端模型）
│   ├── confession_queries.py #  表白查询构建
│   └── settings_store.py   #   系统设置读写
├── tests/
│   └── test_api.py         #   集成测试（101 项断言）
└── API.md                  #   完整 API 文档
```

---

## API 总览

统一响应格式：`{ code, message, data }`，`code=0` 成功，错误时 `code` 与 HTTP 状态码一致。

> 完整接口文档见 [API.md](API.md)

### 认证 `/api/auth`

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | /register | - | 注册并自动登录 |
| POST | /login | - | 登录 |
| POST | /logout | ✅ | 登出（token 吊销） |
| GET | /session | - | 会话恢复 |
| GET | /captcha | - | 获取图形验证码 |
| POST | /email-code | - | 发送邮箱验证码 |
| POST | /forgot/verify | - | 找回密码 — 验证身份 |
| POST | /forgot/reset | - | 找回密码 — 重置密码 |

### 表白墙 `/api`

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | /confessions | - | 表白列表（分页/排序/筛选） |
| GET | /confessions/:id | - | 表白详情 |
| POST | /confessions | ✅ | 发布表白（60s 限频） |
| DELETE | /confessions/:id | ✅ | 删除自己的表白 |
| PUT | /confessions/:id/like | ✅ | 点赞 |
| DELETE | /confessions/:id/like | ✅ | 取消点赞 |
| POST | /confessions/:id/comments | ✅ | 发表评论（30s 限频） |
| POST | /upload/images | ✅ | 图片上传 |
| GET | /uploads/:filename | - | 图片静态服务 |

### 用户 `/api/users`

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | /me | ✅ | 当前用户信息 |
| PATCH | /me | ✅ | 更新昵称/头像色 |
| PUT | /me/password | ✅ | 修改密码 |
| GET | /me/confessions | ✅ | 我的表白 |

### 通知 `/api/notifications`

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | / | ✅ | 通知列表 + 未读数 |
| PUT | /read-all | ✅ | 全部标记已读 |
| PUT | /:id/read | ✅ | 单条标记已读 |
| DELETE | / | ✅ | 清空通知 |

### 管理员 `/api/admin`（全部需 admin 角色）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /stats | 仪表盘统计 |
| GET | /users | 用户列表 |
| POST | /users | 新建用户 |
| PATCH | /users/:id | 更新用户（角色/封禁/重置密码） |
| DELETE | /users/:id | 删除用户 |
| GET | /confessions | 表白列表（含 hidden） |
| PATCH | /confessions/:id/status | 设置表白状态 |
| DELETE | /confessions/:id | 删除表白 |
| POST | /confessions/batch-delete | 批量删除表白 |
| GET | /comments | 全站评论列表 |
| DELETE | /comments/:id | 删除评论 |
| POST | /comments/batch-delete | 批量删除评论 |
| GET | /settings | 获取系统设置 |
| PUT | /settings | 更新系统设置 |

### 公共

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /api/settings | 公开系统设置 |

---

## 安全规则

全部服务端强制，前端无法绕过：

- **频率限制**：表白 60s/条、评论 30s/条（基于 DB 时间戳，重启不丢失）
- **敏感词过滤**：后台开关控制，命中替换为等长 `*`，返回命中计数
- **验证码安全**：邮箱码 6 位（5min 有效 / 一次性 / 错误 5 次销毁 / 60s 防重发）；图形码 4 位 SVG（一次性 / 不区分大小写）
- **找回密码**：同用户名 60s 冷却；连续失败 5 次锁 15 分钟；重置凭证用后即焚
- **输入校验**：用户名 `^[a-zA-Z0-9_]{3,20}$` 唯一、密码 ≥6 位、昵称 ≤20 字、邮箱格式+唯一、表白 ≤200 字、评论 ≤100 字
- **通知**：点赞→表白作者；评论→表白作者；回复→被回复者；自己给自己不发；每用户保留最近 50 条
- **权限**：游客仅浏览；登录用户发布/互动；管理员后台全套；内置超管 `admin` 禁止删除/封禁/改角色
- **图片**：base64 落盘为静态文件 URL（≤3 张、单张 ≤6MB）；删除表白时同步清理图片文件
- **请求体上限**：30MB（超限返回 413）

---

## 测试

```bash
# 先启动服务
python app.py

# 另开终端运行测试
python tests/test_api.py
```

101 项断言，覆盖全部接口 + 安全专项（验证码 5 次限制、重置凭证一次性、413 上限、图片文件清理、封禁踢下线、token 吊销等）。

---

## 配置项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `LOVEWALL_SECRET_KEY` | lovewall-dev-secret-change-me | JWT 签名密钥（**生产必改**） |
| `LOVEWALL_DB` | ./lovewall.db | SQLite 文件路径 |
| `LOVEWALL_TOKEN_DAYS` | 7 | Token 有效期（天） |
| `LOVEWALL_UPLOAD_DIR` | ./uploads | 图片存储目录 |
| `LOVEWALL_MAIL_DEBUG` | 1 | 开发模式回显邮箱验证码；生产置 0 |

---

## 生产部署

```bash
# gunicorn 启动（SQLite WAL 支持多 worker 读）
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

部署清单：

- [ ] 修改 `SECRET_KEY` 为强随机值
- [ ] 启用 HTTPS
- [ ] 关闭 `MAIL_DEBUG`，接入真实 SMTP
- [ ] 图片迁移至对象存储（接口已预留独立上传端点）
- [ ] 高并发场景可换 MySQL/PostgreSQL（仅需替换 `common/db.py`）

---

## 与前端对接

前端将 Pinia store 中的 localStorage 读写替换为 REST 请求，请求头携带 `Authorization: Bearer <token>`：

- 登录/注册响应中的 `token` 存 localStorage，替换原 `lovewall:session`
- `message` 字段为中文文案，可直接用于 `ElMessage` 提示
- 表白对象新增 `likedByMe` / `likeCount` / `commentCount` 便捷字段
- 图片字段从 base64 改为 URL（发布接口同时兼容 base64 自动落盘）

---

## License

[MIT](LICENSE) © 2026 Jay