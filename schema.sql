-- Lovewall 表白墙 · SQLite 建表脚本
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id             TEXT PRIMARY KEY,                -- u- 前缀短 ID
  username       TEXT NOT NULL UNIQUE,            -- ^[a-zA-Z0-9_]{3,20}$
  nickname       TEXT NOT NULL,                   -- ≤ 20 字符
  password_hash  TEXT NOT NULL,                   -- bcrypt
  role           TEXT NOT NULL DEFAULT 'user',    -- user | admin
  avatar_color   TEXT NOT NULL DEFAULT '#f56c6c', -- 头像七色之一
  email          TEXT UNIQUE,                     -- 选填，唯一
  created_at     INTEGER NOT NULL,                -- 毫秒时间戳
  status         TEXT NOT NULL DEFAULT 'active',  -- active | banned
  last_post_at   INTEGER NOT NULL DEFAULT 0,      -- 发布表白限频时间戳
  last_comment_at INTEGER NOT NULL DEFAULT 0      -- 发表评论限频时间戳
);

CREATE TABLE IF NOT EXISTS confessions (
  id          TEXT PRIMARY KEY,                   -- c- 前缀短 ID
  to_name     TEXT NOT NULL DEFAULT '所有人',      -- 收件人 ≤ 20 字符
  content     TEXT NOT NULL,                      -- ≤ 200 字符
  from_name   TEXT NOT NULL DEFAULT '匿名',        -- 署名（作者改名的同步规则见 users 接口）
  author_id   TEXT,                               -- 发布者（匿名表白仍记录作者）
  color       TEXT NOT NULL DEFAULT 'pink',       -- 便签六色主题
  images      TEXT NOT NULL DEFAULT '[]',         -- JSON 数组：图片 URL
  created_at  INTEGER NOT NULL,
  status      TEXT NOT NULL DEFAULT 'normal',     -- normal | hidden
  FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_confessions_status_created ON confessions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_confessions_author ON confessions(author_id);

CREATE TABLE IF NOT EXISTS likes (
  user_id       TEXT NOT NULL,
  confession_id TEXT NOT NULL,
  created_at    INTEGER NOT NULL,
  PRIMARY KEY (user_id, confession_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (confession_id) REFERENCES confessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_likes_confession ON likes(confession_id);

CREATE TABLE IF NOT EXISTS comments (
  id                 TEXT PRIMARY KEY,            -- cm- 前缀短 ID
  confession_id      TEXT NOT NULL,
  author_id          TEXT,
  nickname           TEXT NOT NULL,               -- 写时冗余快照（查询时联表优先实时昵称）
  content            TEXT NOT NULL,               -- ≤ 100 字符
  reply_to           TEXT,                        -- 楼中楼：指向被回复 Comment.id
  reply_to_nickname  TEXT,
  created_at         INTEGER NOT NULL,
  status             TEXT NOT NULL DEFAULT 'normal',
  FOREIGN KEY (confession_id) REFERENCES confessions(id) ON DELETE CASCADE,
  FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_confession ON comments(confession_id, created_at);
CREATE INDEX IF NOT EXISTS idx_comments_author ON comments(author_id);

CREATE TABLE IF NOT EXISTS notifications (
  id             TEXT PRIMARY KEY,                -- n- 前缀短 ID
  type           TEXT NOT NULL,                   -- like | comment | reply
  to_user_id     TEXT NOT NULL,
  from_user_id   TEXT NOT NULL,
  from_nickname  TEXT NOT NULL,
  confession_id  TEXT,
  text           TEXT NOT NULL,
  read           INTEGER NOT NULL DEFAULT 0,
  created_at     INTEGER NOT NULL,
  FOREIGN KEY (to_user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(to_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,                          -- emailVerificationEnabled / captchaEnabled / sensitiveFilterEnabled
  value TEXT NOT NULL DEFAULT '0'                  -- '1' | '0'
);

CREATE TABLE IF NOT EXISTS email_codes (
  email      TEXT PRIMARY KEY,
  code       TEXT NOT NULL,                        -- 6 位数字
  expires_at INTEGER NOT NULL,
  sent_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS captchas (
  id         TEXT PRIMARY KEY,
  text       TEXT NOT NULL,                        -- 4 位字符（小写存储，校验不区分大小写）
  expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS token_blacklist (
  jti        TEXT PRIMARY KEY,                     -- 登出吊销的 JWT ID
  expires_at INTEGER NOT NULL
);
