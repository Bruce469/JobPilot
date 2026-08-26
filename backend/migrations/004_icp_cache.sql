-- 004_icp_cache: ICP 备案反查缓存（resolve 三级流水线的缓存表）
-- name 按公司名缓存查询结果（JSON 或 NULL 表示无记录），90 天过期。

CREATE TABLE IF NOT EXISTS icp_cache (
  name       TEXT PRIMARY KEY,
  result     TEXT,
  updated_at TEXT NOT NULL
);
