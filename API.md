# Lovewall 表白墙后端 API 文档

> 基础路径：`/api`  
> 鉴权方式：`Authorization: Bearer <token>`（JWT，有效期 7 天）  
> 统一响应格式：

```json
{
  "code": 0,
  "message": "ok",
  "data": { ... }
}
```

- `code = 0` 表示成功，非 0 为业务错误码（通常与 HTTP 状态码一致）
- `message` 为中文提示文案
- `data` 在成功时存在，错误时省略

---

## 目录

1. [健康检查](#1-健康检查)
2. [系统设置（公开）](#2-系统设置公开)
3. [认证模块](#3-认证模块)
4. [表白墙模块](#4-表白墙模块)
5. [用户模块](#5-用户模块)
6. [通知模块](#6-通知模块)
7. [管理员模块](#7-管理员模块)
8. [数据模型](#8-数据模型)
9. [错误码速查](#9-错误码速查)

---

## 1. 健康检查

### `GET /api/health`

无需鉴权。

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| service | string | 服务名 `lovewall-backend` |
| db | string | 数据库类型 `sqlite` |

---

## 2. 系统设置（公开）

### `GET /api/settings`

无需鉴权。前端注册页等初始化时调用，决定是否渲染邮箱验证码 / 图形验证码输入框。

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| settings | object | 见下方 |

**settings 对象：**

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| emailVerificationEnabled | bool | false | 是否开启邮箱验证码 |
| captchaEnabled | bool | false | 是否开启图形验证码 |
| sensitiveFilterEnabled | bool | false | 是否开启敏感词过滤 |

---

## 3. 认证模块

前缀：`/api/auth`

### 3.1 获取图形验证码

### `GET /api/auth/captcha`

无需鉴权。返回 SVG 图片 data URL，5 分钟有效，一次性使用。

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| captchaId | string | 验证码 ID，提交时需携带 |
| image | string | SVG data URL（base64 编码） |

---

### 3.2 发送邮箱验证码

### `POST /api/auth/email-code`

无需鉴权。6 位数字验证码，5 分钟有效，一次性使用，60s 防重发。校验失败达 5 次销毁验证码。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 邮箱地址 |

**响应 data（开发模式 MAIL_DEBUG=1）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| email | string | 邮箱 |
| code | string | 验证码（仅开发模式回显） |
| expiresIn | number | 有效秒数 300 |

**响应 data（生产模式）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| email | string | 邮箱 |
| expiresIn | number | 有效秒数 300 |

**错误：** 429 — 发送太频繁

---

### 3.3 注册

### `POST /api/auth/register`

无需鉴权。注册成功自动登录，返回 token。图形验证码和邮箱验证码由服务端按系统开关强制校验。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |
| nickname | string | 否 | 昵称，默认同用户名 |
| email | string | 否 | 邮箱（开启邮箱验证时必填） |
| captchaId | string | 条件 | 图形验证码 ID（开启时必填） |
| captchaText | string | 条件 | 图形验证码文本（开启时必填） |
| emailCode | string | 条件 | 邮箱验证码（开启时必填） |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| user | object | 用户公开信息 |
| token | string | JWT token |

---

### 3.4 登录

### `POST /api/auth/login`

无需鉴权。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| user | object | 用户公开信息 |
| token | string | JWT token |

**错误：** 401 — 用户名或密码错误；403 — 账号被封禁

---

### 3.5 登出

### `POST /api/auth/logout`

需鉴权。服务端吊销 token（立即失效）。

**请求头：** `Authorization: Bearer <token>`

**响应：** `{ code: 0, message: "已退出登录" }`

---

### 3.6 会话恢复

### `GET /api/auth/session`

无需鉴权（有 token 则恢复，无则返回未登录状态）。前端 init() 调用。

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| user | object\|null | 用户信息，未登录为 null |
| isLoggedIn | bool | 是否已登录 |
| isAdmin | bool | 是否管理员 |

---

### 3.7 找回密码 — 第一步：验证身份

### `POST /api/auth/forgot/verify`

无需鉴权。校验用户名与绑定邮箱匹配，返回一次性重置凭证。安全闸门：同用户名 60s 冷却，连续失败 5 次锁 15 分钟。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| email | string | 是 | 绑定邮箱 |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| user | object | `{ id, username, nickname, email }` |
| resetToken | string | 一次性重置凭证（10 分钟有效） |
| expiresIn | number | 凭证有效秒数 |

**错误：** 429 — 操作太频繁 / 尝试次数过多

---

### 3.8 找回密码 — 第三步：重置密码

### `POST /api/auth/forgot/reset`

无需鉴权。携带一次性重置凭证 + 邮箱验证码设置新密码。凭证用后即焚。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| userId | string | 是 | 用户 ID |
| resetToken | string | 是 | 重置凭证 |
| newPassword | string | 是 | 新密码 |
| emailCode | string | 是 | 邮箱验证码 |

**错误：** 403 — 凭证已失效 / 邮箱验证码错误

---

## 4. 表白墙模块

前缀：`/api`

### 4.1 表白列表

### `GET /api/confessions`

无需鉴权（登录用户可看到自己是否点赞）。

**查询参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| keyword | string | "" | 关键词搜索 |
| color | string | "" | 颜色筛选 |
| sort | string | latest | 排序：`latest` / `hottest` |
| page | number | 1 | 页码 |
| pageSize | number | 10 | 每页条数 |
| mine | string | - | `1` 时返回当前用户自己的表白（含隐藏，需登录） |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| list | array | 表白列表 |
| total | number | 总数 |
| page | number | 当前页 |
| pageSize | number | 每页条数 |

---

### 4.2 表白详情

### `GET /api/confessions/:confession_id`

无需鉴权。hidden 状态仅作者和管理员可见。

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| confession | object | 表白详情（含评论列表） |

---

### 4.3 发布表白

### `POST /api/confessions`

需鉴权。60s 限频。敏感词过滤（开关控制）。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| to | string | 否 | 收件人，默认"所有人"，≤20 字符 |
| content | string | 是 | 表白内容，≤200 字符 |
| from | string | 否 | 署名，默认"匿名"，≤20 字符 |
| color | string | 否 | 颜色主题，默认 pink |
| images | array | 否 | 图片数组（base64 data URL 或已上传 URL），最多 3 张 |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| confession | object | 新发布的表白详情 |
| filtered | number | 命中敏感词数量 |

**错误：** 429 — 限频

---

### 4.4 删除自己的表白

### `DELETE /api/confessions/:confession_id`

需鉴权。物理删除，含全部评论、点赞与图片文件。仅作者可删。

**错误：** 403 — 只能删除自己的表白；404 — 表白不存在

---

### 4.5 点赞

### `PUT /api/confessions/:confession_id/like`

需鉴权。点赞成功向表白作者推送通知（自己赞自己不通知）。

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| liked | bool | true |
| likeCount | number | 当前点赞总数 |

---

### 4.6 取消点赞

### `DELETE /api/confessions/:confession_id/like`

需鉴权。

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| liked | bool | false |
| likeCount | number | 当前点赞总数 |

---

### 4.7 发表评论

### `POST /api/confessions/:confession_id/comments`

需鉴权。30s 限频。敏感词过滤（开关控制）。支持楼中楼回复。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 是 | 评论内容，≤100 字符 |
| replyTo | object\|null | 否 | 被回复评论 `{ id, nickname }` |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| comment | object | 新评论 |
| filtered | number | 命中敏感词数量 |

**错误：** 429 — 限频

---

### 4.8 图片上传

### `POST /api/upload/images`

需鉴权。独立上传图片，base64 data URL 落盘为静态文件。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| images | array | 是 | base64 data URL 数组，最多 3 张，单张 ≤6MB |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| images | array | 上传后的 URL 数组 |

---

### 4.9 静态图片服务

### `GET /api/uploads/:filename`

无需鉴权。返回上传的图片文件。

---

## 5. 用户模块

前缀：`/api/users`

### 5.1 当前用户信息

### `GET /api/users/me`

需鉴权。会话恢复用。

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| user | object | 用户公开信息 |

---

### 5.2 更新个人资料

### `PATCH /api/users/me`

需鉴权。修改昵称时，历史表白署名和评论昵称快照自动同步。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nickname | string | 是 | 新昵称 |
| avatarColor | string | 否 | 头像颜色 |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| user | object | 更新后的用户信息 |
| oldNickname | string | 旧昵称 |

---

### 5.3 修改密码

### `PUT /api/users/me/password`

需鉴权。验证原密码后修改，不强制重新登录。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| oldPassword | string | 是 | 原密码 |
| newPassword | string | 是 | 新密码 |

**错误：** 403 — 原密码错误

---

### 5.4 我的表白

### `GET /api/users/me/confessions`

需鉴权。含 hidden 状态并带标注。

**查询参数：** 同 [4.1 表白列表](#41-表白列表)（无 mine 参数）

---

## 6. 通知模块

前缀：`/api/notifications`

### 6.1 通知列表

### `GET /api/notifications`

需鉴权。时间倒序，含未读数。

**查询参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| page | number | 1 | 页码 |
| pageSize | number | 20 | 每页条数（最大 50） |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| list | array | 通知列表 |
| total | number | 总数 |
| unreadCount | number | 未读数 |
| page | number | 当前页 |
| pageSize | number | 每页条数 |

---

### 6.2 全部标记已读

### `PUT /api/notifications/read-all`

需鉴权。

---

### 6.3 单条标记已读

### `PUT /api/notifications/:notification_id/read`

需鉴权。

**错误：** 404 — 通知不存在

---

### 6.4 清空通知

### `DELETE /api/notifications`

需鉴权。删除当前用户所有通知。

---

## 7. 管理员模块

前缀：`/api/admin`。所有接口需管理员鉴权（role = admin）。

### 7.1 仪表盘统计

### `GET /api/admin/stats`

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| totalUsers | number | 总用户数 |
| activeUsers | number | 活跃用户数 |
| bannedUsers | number | 封禁用户数 |
| totalConfessions | number | 总表白数 |
| hiddenConfessions | number | 隐藏表白数 |
| totalLikes | number | 总点赞数 |
| totalComments | number | 总评论数 |
| topLiked | array | 点赞 Top5 表白 |
| settings | object | 系统设置 |

---

### 7.2 用户列表

### `GET /api/admin/users`

**查询参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| keyword | string | "" | 用户名/昵称/邮箱模糊搜索 |
| page | number | 1 | 页码 |
| pageSize | number | 20 | 每页条数（最大 100） |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| list | array | 用户列表 |
| total | number | 总数 |
| page | number | 当前页 |
| pageSize | number | 每页条数 |

---

### 7.3 新建用户

### `POST /api/admin/users`

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |
| nickname | string | 否 | 昵称，默认同用户名 |
| email | string | 否 | 邮箱 |
| role | string | 否 | 角色 `user` / `admin`，默认 user |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| user | object | 新用户信息 |

---

### 7.4 更新用户

### `PATCH /api/admin/users/:user_id`

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| action | string | 否 | `resetPassword` — 重置密码为 123456 |
| banned | bool | 否 | true 封禁 / false 解封 |
| role | string | 否 | 角色 `user` / `admin` |

**特殊：** 内置管理员（username=admin）不允许封禁、改角色、删除、重置密码。

---

### 7.5 删除用户

### `DELETE /api/admin/users/:user_id`

不级联清理历史表白与评论，作者字段置空、昵称回落快照。不能删除自己，不能删除内置管理员。

---

### 7.6 后台表白列表

### `GET /api/admin/confessions`

含 hidden 状态，可按 status 过滤。

**查询参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| keyword | string | "" | 关键词 |
| color | string | "" | 颜色筛选 |
| status | string | "" | 状态筛选 `normal` / `hidden` |
| sort | string | latest | 排序 |
| page | number | 1 | 页码 |
| pageSize | number | 10 | 每页条数 |

---

### 7.7 设置表白状态

### `PATCH /api/admin/confessions/:confession_id/status`

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 是 | `normal`（前台可见）/ `hidden`（仅管理员与作者可见） |

---

### 7.8 删除单条表白

### `DELETE /api/admin/confessions/:confession_id`

级联删除评论、点赞与图片文件。

---

### 7.9 批量删除表白

### `POST /api/admin/confessions/batch-delete`

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ids | array | 是 | 要删除的表白 ID 数组 |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| deleted | number | 实际删除条数 |

---

### 7.10 全站评论列表

### `GET /api/admin/comments`

**查询参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| keyword | string | "" | 评论内容/昵称模糊搜索 |
| page | number | 1 | 页码 |
| pageSize | number | 20 | 每页条数（最大 100） |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| list | array | 评论列表（附表白摘要） |
| total | number | 总数 |
| page | number | 当前页 |
| pageSize | number | 每页条数 |

---

### 7.11 删除单条评论

### `DELETE /api/admin/comments/:comment_id`

---

### 7.12 批量删除评论

### `POST /api/admin/comments/batch-delete`

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ids | array | 是 | 要删除的评论 ID 数组 |

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| deleted | number | 实际删除条数 |

---

### 7.13 获取系统设置

### `GET /api/admin/settings`

**响应 data：**

| 字段 | 类型 | 说明 |
|------|------|------|
| settings | object | 系统设置 |

---

### 7.14 更新系统设置

### `PUT /api/admin/settings`

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| emailVerificationEnabled | bool | 否 | 邮箱验证开关 |
| captchaEnabled | bool | 否 | 图形验证码开关 |
| sensitiveFilterEnabled | bool | 否 | 敏感词过滤开关 |

---

## 8. 数据模型

### User

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 用户 ID（前缀 `u_`） |
| username | string | 用户名 |
| nickname | string | 昵称 |
| role | string | 角色：`user` / `admin` |
| avatarColor | string | 头像颜色 |
| email | string\|null | 邮箱 |
| createdAt | number | 创建时间戳（ms） |
| status | string | 状态：`active` / `banned` |

### Confession

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 表白 ID（前缀 `c_`） |
| to | string | 收件人 |
| content | string | 内容 |
| from | string | 署名 |
| authorId | string | 作者 ID |
| color | string | 颜色主题 |
| images | array | 图片 URL 数组 |
| likes | array | 点赞用户 ID 数组 |
| likeCount | number | 点赞总数 |
| likedByMe | bool | 当前用户是否已点赞 |
| commentCount | number | 评论总数 |
| comments | array | 评论列表（详情接口返回） |
| createdAt | number | 创建时间戳（ms） |
| status | string | 状态：`normal` / `hidden` |

### Comment

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 评论 ID（前缀 `cm_`） |
| confessionId | string | 所属表白 ID |
| authorId | string | 作者 ID |
| nickname | string | 昵称快照 |
| content | string | 内容 |
| replyTo | string\|null | 被回复评论 ID |
| replyToNickname | string\|null | 被回复评论昵称 |
| createdAt | number | 创建时间戳（ms） |
| status | string | 状态：`normal` |

### Notification

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 通知 ID |
| type | string | 类型：`like` / `comment` / `reply` |
| toUserId | string | 接收用户 ID |
| fromUserId | string | 触发用户 ID |
| fromNickname | string | 触发用户昵称 |
| confessionId | string | 关联表白 ID |
| text | string | 通知文案 |
| read | bool | 是否已读 |
| createdAt | number | 创建时间戳（ms） |

---

## 9. 错误码速查

| HTTP | 业务码 | 说明 |
|------|--------|------|
| 400 | 400 | 请求参数错误 |
| 401 | 401 | 未登录 / 用户名或密码错误 |
| 403 | 403 | 无权限 / 账号被封禁 / 原密码错误 / 凭证失效 |
| 404 | 404 | 资源不存在 |
| 405 | 405 | 请求方法不允许 |
| 409 | 409 | 资源冲突 |
| 413 | 413 | 请求体过大（图片请压缩） |
| 429 | 429 | 请求过于频繁（限频 / 验证码重发冷却） |
| 500 | 500 | 服务器内部错误 |