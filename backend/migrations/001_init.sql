-- 001_init: 初始四张业务表 + 迁移记录表
-- 外键顺序：companies / resumes 先建，jobs 后建（引用二者），job_events 最后（引用 jobs）

CREATE TABLE IF NOT EXISTS schema_migrations (
  version    INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS companies (
  id                TEXT PRIMARY KEY,
  name              TEXT NOT NULL UNIQUE,
  website           TEXT NOT NULL,
  career_url        TEXT,
  industry          TEXT,
  probe_status      TEXT,
  ats_type          TEXT,
  notes             TEXT,
  last_fetched_at   TEXT,
  last_fetch_result TEXT,
  created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resumes (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  basic      TEXT NOT NULL,
  education  TEXT,
  experience TEXT,
  projects   TEXT,
  skills     TEXT,
  summary    TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
  id            TEXT PRIMARY KEY,
  company       TEXT NOT NULL,
  company_id    TEXT REFERENCES companies(id) ON DELETE SET NULL,
  position      TEXT,
  job_type      TEXT,
  degree        TEXT,
  city          TEXT,
  industry      TEXT,
  channel       TEXT,
  job_url       TEXT,
  source_job_id TEXT,
  publish_date  TEXT,
  deadline      TEXT,
  applied_at    TEXT,
  status        TEXT NOT NULL DEFAULT '待投递',
  ended_at      TEXT,
  resume_id     TEXT REFERENCES resumes(id) ON DELETE SET NULL,
  resume_name   TEXT,
  notes         TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status        ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_deadline      ON jobs(deadline);
CREATE INDEX IF NOT EXISTS idx_jobs_company_id    ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_source_job_id ON jobs(source_job_id);

CREATE TABLE IF NOT EXISTS job_events (
  id          TEXT PRIMARY KEY,
  job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  time        TEXT NOT NULL,
  type        TEXT NOT NULL,
  from_status TEXT,
  to_status   TEXT,
  note        TEXT,
  created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON job_events(job_id);
CREATE INDEX IF NOT EXISTS idx_job_events_time   ON job_events(time);
