-- 002_market_jobs: JobPulse 招聘情报（market 模块）两张表
-- 字段定义对齐 market/storage/models.py（SQLAlchemy ORM），SQLite 方言。
-- market_jobs 每个 job_id 只保留最新状态（幂等 upsert）；market_job_snapshots 按 (job_id, crawl_date) 追加历史快照。

CREATE TABLE IF NOT EXISTS market_jobs (
  job_id         TEXT PRIMARY KEY,
  job_title      TEXT NOT NULL,
  job_category   TEXT NOT NULL,
  job_type       TEXT NOT NULL,
  company_name   TEXT NOT NULL,
  industry       TEXT NOT NULL,
  company_size   TEXT,
  city           TEXT NOT NULL,
  salary_raw     TEXT NOT NULL,
  salary_min     INTEGER,
  salary_max     INTEGER,
  salary_avg     INTEGER,
  experience_req TEXT NOT NULL,
  education_req  TEXT NOT NULL,
  job_desc       TEXT NOT NULL,
  tags           TEXT,
  post_date      TEXT,
  crawl_date     TEXT NOT NULL,
  url            TEXT NOT NULL,
  is_valid       INTEGER NOT NULL DEFAULT 1,
  source         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_market_jobs_crawl_date ON market_jobs(crawl_date);

CREATE TABLE IF NOT EXISTS market_job_snapshots (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id     TEXT NOT NULL,
  crawl_date TEXT NOT NULL,
  salary_min INTEGER,
  salary_max INTEGER,
  salary_avg INTEGER,
  is_valid   INTEGER NOT NULL DEFAULT 1,
  url        TEXT,
  UNIQUE (job_id, crawl_date)
);
CREATE INDEX IF NOT EXISTS ix_snapshot_crawl_date ON market_job_snapshots(crawl_date);
