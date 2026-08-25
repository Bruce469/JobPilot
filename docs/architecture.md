# 秋招投递助手 架构设计文档

版本：v1.0
日期：2026-08-24
上游输入：`docs/prd.md`（v0.5 定稿）、`docs/review.md`（评审记录）
作者：架构师

> 本文档是前后端工程师的施工依据。字段名、接口路径、目录结构均以本文为准；与 PRD 冲突时以本文为技术落地口径。设计总原则：**个人工具、够用可靠、避免过度设计**——不引入消息队列、重型 ORM、容器化、无头浏览器、第三方服务。

---

## 0. 非功能指标（可量化）

| 指标 | 目标 | 说明 |
|---|---|---|
| 首屏加载 | < 2s | 本机前端 dev server 打开看板 |
| 本机 API 延迟 | P95 < 50ms | 除抓取外的所有回环请求 |
| 列表流畅度 | 1000 条内滚动流畅 | 个人数据量上限，无需虚拟滚动 |
| 单 HTTP 抓取请求 | 超时 < 10s | httpx timeout |
| 单公司探测+抓取任务 | 总时长 < 60s | 超时降级「保留链接+手动录入」 |
| 抓取限速 | 串行(并发=1)、同域间隔 ≥1.5s、全局 ≤30 req/min | 固定 UA |
| 数据可靠性 | 刷新/重启后端不丢数据 | SQLite WAL + 落盘；启动距上次导出 >7 天提示备份 |
| 安全 | 仅监听 127.0.0.1，不对外暴露 | CORS 白名单 + Host 校验 + 随机 token |

---

## 1. 系统架构总览

### 1.1 组件划分

```
┌─────────────────────────── 浏览器（Chromium 系） ───────────────────────────┐
│  前端 SPA（Vite + Vue 3 + TS）                                              │
│  ├─ 路由页面：看板 / 列表 / 公司库 / 简历 / 统计(M2) / 设置                  │
│  ├─ Pinia store：jobs / companies / resumes / ui                            │
│  ├─ API 封装（axios + X-Auth-Token 注入）                                   │
│  └─ 简历 A4 渲染 + window.print() 打印/PDF                                  │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │ HTTP（127.0.0.1，JSON REST）
                                │ 前端 dev 通过 Vite proxy 转发到后端
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  后端轻量服务（Python + FastAPI，uvicorn，host=127.0.0.1）                    │
│  ├─ 中间件：CORS 白名单 / Host 头校验 / token 校验                           │
│  ├─ 路由层：/api/boot /api/jobs /api/resumes /api/companies                  │
│  │          /api/tasks /api/backup /api/stats                                │
│  ├─ 业务层（service）：jobs / resumes / companies / backup / stats           │
│  ├─ 数据层（DAO，sqlite3 标准库）：连接工厂 + 参数化 SQL + 迁移              │
│  └─ 抓取模块（fetcher）：probe → ATS 识别 → 适配器 → JSON-LD 兜底           │
│       └─ 异步任务：内存任务表 + 后台工作线程 + 限速器                         │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │ sqlite3（WAL 模式）
                          ┌─────▼─────┐
                          │ SQLite 文件 │  data/app.db（本机磁盘）
                          └───────────┘
```

### 1.2 数据流

**核心 CRUD 链路（同步）**：
前端交互（看板拖拽/表单编辑）→ axios 请求（带 token）→ FastAPI 路由 → service 业务校验 → DAO 执行参数化 SQL → SQLite 落盘 → 返回 JSON → 前端更新 store 与视图。

**状态流转链路**：前端调 `POST /api/jobs/{id}/status` → service 校验状态合法性（同状态不产生事件；终态写 ended_at，回退清 ended_at）→ 事务内写 `jobs` 行 + 插 `job_events` 事件 → 返回更新后的 job + 新 event → 前端刷新卡片与时间线。

**抓取任务链路（异步）**：
前端发起 `POST /api/companies/{id}/probe`（或 `/fetch`）→ 后端立即创建任务（状态 `queued`）并返回 `{job_id}` → 后台工作线程串行执行（robots 检查 → 探测/抓取 → 限速）→ 前端每 1~2s 轮询 `GET /api/tasks/{job_id}` → 拿到 `done` 的 result（候选链接 / 岗位列表）→ 前端预览确认 → `POST /api/jobs/import` 去重导入。

### 1.3 部署形态（本机启动）

- 后端：`uvicorn app.main:app --host 127.0.0.1 --port 8000`（生产形态即本机单进程，无需 gunicorn 多 worker；个人单用户）。
- 前端：开发期 `vite` dev server（默认 5173），`vite.config.ts` 配置 proxy：`/api` → `http://127.0.0.1:8000`，避免跨域与 CORS 困扰。
- 端口策略：后端端口被占时允许 `--port` 指定或自动探测可用端口并打印；前端 dev proxy 目标随之调整。
- 本机使用无需构建前端静态产物；若要「双击即用」，可后续用 `vite build` 产出静态文件由 FastAPI `StaticFiles` 托管（M3 可选，见 9 章）。

---

## 2. 技术选型与 ADR

### 2.1 技术选型总表

| 领域 | 选型 | 选中理由 | 否决方案与原因 |
|---|---|---|---|
| 前端框架 | Vue 3 + TypeScript | 用户拍板；组合式 API 与 TS 类型安全；生态成熟 | React：用户已拍板 Vue，不采用 |
| 前端构建 | Vite | 冷启动快、HMR 快，个人工具零配置 | webpack：配置重、启动慢，否决 |
| 前端状态 | Pinia | Vue 3 官方推荐，轻量 | Vuex 4：较重且官方转向 Pinia，否决 |
| 前端路由 | Vue Router 4 | 官方标准 | 手写路由：无必要 |
| HTTP 客户端 | axios | 拦截器统一注入 token/错误处理，标准轻量 | 原生 fetch：需手写拦截，重复劳动 |
| 后端框架 | FastAPI | 用户拍板；异步支持、Pydantic 校验、自动 OpenAPI 文档 | Node/Fastify、Flask：用户已拍板 Python；Flask 缺原生 Pydantic 校验，否决 |
| 数据校验 | Pydantic v2 | FastAPI 原生集成，请求/响应 schema 单一事实源 | 手写 dict 校验：易漏，否决 |
| 数据存储 | SQLite（WAL） | 本机单文件、零运维、事务可靠，PRD 定稿 | PostgreSQL/MySQL：需装服务，违背个人工具定位，否决 |
| SQLite 访问 | **Python 标准库 sqlite3** | 零额外依赖；4 张表结构简单，手写参数化 SQL 完全可控；已有 Pydantic 做类型/校验，ORM 的类型映射价值被稀释 | SQLModel：依赖 SQLAlchemy + Pydantic 两个重库，4 表场景性价比低；SQLAlchemy ORM：重型，否决；Peewee：小众，否决 |
| HTTP 抓取 | httpx | 用户拍板；同步/异步双模式、超时/代理/UA 控制完善 | requests：无原生异步，限速场景不如 httpx，否决 |
| HTML 解析 | BeautifulSoup4 | 用户拍板；容错强，适合多变招聘页 | lxml/正则：正则脆弱、lxml 对脏 HTML 容错差，否决 |
| 异步任务 | 内存任务表 + threading 后台线程 | 个人单用户、任务串行，无需持久化/分布式队列 | Celery/Redis：重依赖+需 broker，违背定位，否决 |
| 简历 PDF | `window.print()` + A4 打印样式 | 零依赖、浏览器原生、可另存 PDF（PRD Q6 定稿） | jsPDF/html2pdf：仅在分页不可控时评估（Q6 后备），MVP 否决 |
| 拖拽 | vuedraggable（SortableJS） | 跨列 group 拖拽契合看板流转 | 原生 HTML5 DnD：跨列拖放需手写较多，作为备选 |

### 2.2 关键 ADR 摘要

- **ADR-1（数据访问 sqlite3）**：采用标准库 sqlite3 + 自建轻量 DAO 层（连接工厂 + 参数化 SQL + 每操作短连接）。WAL 模式下读写并发良好，连接开销可忽略。迁移用编号 SQL 脚本 + `schema_migrations` 表。放弃 SQLModel/SQLAlchemy（重型）。
- **ADR-2（events 拆表）**：时间线拆为独立 `job_events` 表，而非 jobs 表 JSON 列。理由：笔试/面试事件需要按时间查询聚合（4.3「今日/本周安排」、4.9 提醒），独立表可建索引、可按 job_id 高效检索；jobs 表保持扁平利于筛选。
- **ADR-3（抓取异步化）**：探测+抓取为后端异步任务（内存任务表 + 单工作线程），前端轮询。理由：抓取耗时秒级到几十秒，同步阻塞会卡 UI；个人工具单任务串行，线程即可，无需消息队列。
- **ADR-4（安全 token）**：启动生成随机 token，`/api/boot` 下发，后续请求经 `X-Auth-Token` 头携带。配合 Host 校验与 CORS 白名单，构成无登录场景下的最小信任边界（详见 7 章）。
- **ADR-5（城市字段存储）**：city 存逗号分隔文本（如 `北京,上海`），筛选用 `LIKE` 子串匹配。理由：个人数据量小（≤100 条）、城市名不含逗号，逗号分隔最简单可导出；不做多值关联表（过度设计）。

---

## 3. 数据库设计

### 3.1 存储参数

- 文件：`data/app.db`（相对后端运行目录，可用环境变量 `APP_DB_PATH` 覆盖）。
- 打开参数：`sqlite3.connect(path)`，执行 `PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;`。
- 连接策略：DAO 层提供 `get_conn()` 连接工厂，每操作/每事务一个短连接，用完关闭（`with closing(conn)`）。后台抓取线程与请求处理各自独立连接，由 WAL + busy_timeout 保证并发安全。
- 时间格式：统一 ISO 8601 文本。date 字段 `YYYY-MM-DD`；datetime 字段 `YYYY-MM-DDTHH:MM:SS`（本地时区，不存时区偏移，个人工具本机使用）。全部 `TEXT`。
- 主键：`id` 为 UUID v4 字符串（`uuid4().hex` 或带连字符统一为无连字符 32 位 hex，后端生成，前端不传）。

### 3.2 表结构

#### jobs（岗位）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | TEXT | PRIMARY KEY | UUID |
| company | TEXT | NOT NULL | 公司名称快照（唯一必填项） |
| company_id | TEXT | NULL, 外键 companies(id) ON DELETE SET NULL | 关联公司库，可空 |
| position | TEXT | NULL | 岗位名称 |
| job_type | TEXT | NULL | 校招/社招/实习 |
| degree | TEXT | NULL | 本科/硕士/博士 |
| city | TEXT | NULL | 逗号分隔多值，如 `北京,上海`；特殊值 `全国` |
| industry | TEXT | NULL | 行业类别（互联网/金融/国企/外企/制造业/其他，可自定义） |
| channel | TEXT | NULL | 官网/Boss直聘/牛客/内推/邮箱/其他，抓取默认 `官网` |
| job_url | TEXT | NULL | JD 直链 |
| source_job_id | TEXT | NULL | 外部招聘系统职位 ID（去重主键） |
| publish_date | TEXT | NULL | 职位发布日期 YYYY-MM-DD |
| deadline | TEXT | NULL | 投递截止 YYYY-MM-DD |
| applied_at | TEXT | NULL | 实际投递时间 YYYY-MM-DD（转「已投递」时写入） |
| status | TEXT | NOT NULL DEFAULT '待投递' | 状态全集见 4.1 |
| ended_at | TEXT | NULL | 终态日期（进终态写，回退清） |
| resume_id | TEXT | NULL, 外键 resumes(id) ON DELETE SET NULL | 所投简历 |
| resume_name | TEXT | NULL | 简历名快照（绑定时刻冻结） |
| notes | TEXT | NULL | JSON 数组 `[{time, content}]`（M1 定结构，M2 出界面） |
| created_at | TEXT | NOT NULL | 创建时间 |
| updated_at | TEXT | NOT NULL | 更新时间 |

状态全集常量：`待投递 / 已投递 / 简历筛选 / 笔试 / 一面 / 二面 / 三面/HR面 / 已Offer / 已拒绝 / 已放弃`；终态 = `{已Offer, 已拒绝, 已放弃}`。

#### job_events（时间线，独立表）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | TEXT | PRIMARY KEY | UUID |
| job_id | TEXT | NOT NULL, 外键 jobs(id) ON DELETE CASCADE | 所属岗位 |
| time | TEXT | NOT NULL | 事件时间 datetime（笔试/面试携带具体时刻） |
| type | TEXT | NOT NULL | `状态流转` / `笔试` / `面试` / `备注` |
| from_status | TEXT | NULL | 状态流转的旧状态 |
| to_status | TEXT | NULL | 状态流转的新状态 |
| note | TEXT | NULL | 可选说明 |
| created_at | TEXT | NOT NULL | 记录创建时间 |

索引：`job_events(job_id)`、`job_events(time)`（支撑「今日/本周安排」聚合与提醒）。

#### companies（公司库）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | TEXT | PRIMARY KEY | UUID |
| name | TEXT | NOT NULL UNIQUE | 公司名（同名拦截） |
| website | TEXT | NOT NULL | 官网地址 |
| career_url | TEXT | NULL | 招聘页 URL（可人工修正） |
| industry | TEXT | NULL | 行业（导入岗位自动带入） |
| probe_status | TEXT | NULL | 未探测/成功/失败/需人工 |
| ats_type | TEXT | NULL | 识别到的招聘系统类型（飞书/北森/Greenhouse/Lever/通用 等） |
| notes | TEXT | NULL | 备注 |
| last_fetched_at | TEXT | NULL | 最近抓取时间 datetime |
| last_fetch_result | TEXT | NULL | 结果摘要，如「新增 5 条，跳过 2 条」 |
| created_at | TEXT | NOT NULL | 添加时间 |

索引：`companies(name)`（UNIQUE 已隐式建索引，无需重复）。

#### resumes（简历）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | TEXT | PRIMARY KEY | UUID |
| name | TEXT | NOT NULL | 简历名称 |
| basic | TEXT | NOT NULL | JSON 对象：name/phone/email/target_position/city |
| education | TEXT | NULL | JSON 数组：school/major/degree/start_date/end_date/description |
| experience | TEXT | NULL | JSON 数组：company/position/start_date/end_date/responsibilities |
| projects | TEXT | NULL | JSON 数组：name/role/start_date/end_date/description |
| skills | TEXT | NULL | JSON 数组（字符串列表） |
| summary | TEXT | NULL | 自我评价 |
| created_at | TEXT | NOT NULL | 创建时间 |
| updated_at | TEXT | NOT NULL | 更新时间 |

> 结构化区块（basic/education/experience/projects/skills/summary）用 JSON 列存储，Python 层 `json.loads/dumps` 读写，Pydantic 负责结构校验。basic 内容结构由简历 Pydantic 模型统一定义。

#### schema_migrations（迁移记录）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| version | INTEGER | PRIMARY KEY | 迁移序号 |
| name | TEXT | NOT NULL | 迁移名 |
| applied_at | TEXT | NOT NULL | 应用时间 |

### 3.3 建表 SQL 草案（migrations/001_init.sql）

```sql
PRAGMA foreign_keys=ON;

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
CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_deadline ON jobs(deadline);
CREATE INDEX IF NOT EXISTS idx_jobs_company_id ON jobs(company_id);
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

CREATE TABLE IF NOT EXISTS companies (
  id                 TEXT PRIMARY KEY,
  name               TEXT NOT NULL UNIQUE,
  website            TEXT NOT NULL,
  career_url         TEXT,
  industry           TEXT,
  probe_status       TEXT,
  ats_type           TEXT,
  notes              TEXT,
  last_fetched_at    TEXT,
  last_fetch_result  TEXT,
  created_at         TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS schema_migrations (
  version    INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  applied_at TEXT NOT NULL
);
```

> 注：`jobs` 引用 `companies`/`resumes` 的外键放在建表顺序上需先建后两者，故实际迁移中 `companies`、`resumes` 建表语句置于 `jobs` 之前（上方 SQL 逻辑上 `companies`/`resumes` 已存在）。迁移脚本按依赖顺序组织。

### 3.4 迁移脚本策略

- 目录 `backend/migrations/`，命名 `001_init.sql`、`002_add_xxx.sql`...（数字递增）。
- 启动时：读 `schema_migrations` 已应用版本集合 → 按序号升序执行未应用脚本（每条脚本一个事务，成功写一条 `schema_migrations` 记录）→ 失败即中止并报错（不静默继续）。
- 演进约定：表结构变更必须新写一个编号脚本（追加/改列），**禁止**修改已发布的 001 脚本；导出备份文件含 `schema_version`，导入时校验 `schema_version <= 当前支持版本`，高于则拒绝并提示升级。

---

## 4. API 契约（REST）

### 4.1 通用约定

- 基础前缀：`/api`；Content-Type：`application/json`；字符集 UTF-8。
- 鉴权：除 `GET /api/boot` 外，所有请求携带 `X-Auth-Token: <token>` 头（token 来自 boot）。
- 统一错误结构（HTTP 4xx/5xx）：

```json
{ "error": { "code": "NOT_FOUND", "message": "岗位不存在", "details": { "id": "..." } } }
```

- 错误码表：

| HTTP | code | 含义 |
|---|---|---|
| 400 | VALIDATION_ERROR | 请求体/参数校验失败（Pydantic） |
| 401 | UNAUTHORIZED | token 缺失或错误 |
| 403 | FORBIDDEN | Host/Origin 校验失败 |
| 404 | NOT_FOUND | 资源不存在 |
| 409 | CONFLICT | 冲突（公司名重复等） |
| 422 | IMPORT_ERROR | 导入文件非法（字段缺失/版本过高） |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

- 列表响应统一：`{ "items": [...], "total": 42 }`；单资源响应直接返回对象。

### 4.2 端点清单

#### 系统
- `GET /api/boot` → 无 token。返回：
```json
{ "token": "hex64", "schema_version": 1, "app": { "name": "秋招投递助手", "version": "0.1.0" } }
```

#### 岗位 jobs
- `GET /api/jobs` → 列表（含筛选，返回 `{items, total}`）
  查询参数（均可选）：`status`（可多值，逗号分隔）、`company`、`city`、`industry`、`channel`、`keyword`（匹配 company/position，LIKE）、`include_ended`（bool，默认 false 时过滤终态）、`sort`（默认 `updated_at desc`）、`sort_dir`。每个 item 不含 events（列表轻量）。
- `POST /api/jobs` → 创建。请求体（仅 `company` 必填，其余可选）：
```json
{
  "company": "字节跳动", "company_id": null, "position": "后端开发工程师",
  "job_type": "校招", "degree": "本科", "city": "北京,上海", "industry": "互联网",
  "channel": "官网", "job_url": "https://...", "source_job_id": null,
  "publish_date": null, "deadline": "2026-09-30", "resume_id": null
}
```
响应 201 + 完整 job 对象（status 默认 `待投递`，含 created_at/updated_at）。
- `GET /api/jobs/{id}` → 详情，返回 job 对象 + `events` 数组（含时间线，按 time 升序）。
- `PUT /api/jobs/{id}` → 更新，请求体同创建字段（可部分字段），仅更新传入字段并刷新 `updated_at`；`status`/`ended_at` 不经此接口变更（走流转接口）。返回完整 job。
- `DELETE /api/jobs/{id}` → 删除（级联删 job_events），响应 204。
- `POST /api/jobs/batch-delete` → 批量删除，请求体 `{ "ids": ["..."] }`，响应 `{ "deleted": 3 }`。
- `POST /api/jobs/{id}/status` → 状态流转。请求体：
```json
{ "status": "笔试", "note": "收到笔试邀请", "time": "2026-08-24T10:00:00" }
```
`time` 可选（默认服务端当前时间）。响应 200：
```json
{ "job": { "...": "更新后的 job" }, "event": { "...": "新写入的 job_events 行" } }
```
业务规则：同状态流转（`to_status == 当前 status`）不产生新事件、直接返回 200 且 `event` 为 null；进终态写 `ended_at`；从终态回退清 `ended_at`；状态合法性校验失败返回 400。
- `POST /api/jobs/import` → 抓取/批量导入岗位（去重）。请求体：
```json
{
  "company_id": "uuid",
  "jobs": [
    { "position": "后端开发", "city": "北京", "job_url": "https://...", "source_job_id": "12345",
      "deadline": null, "degree": "本科", "job_type": "校招" }
  ]
}
```
响应 200：
```json
{ "added": 5, "skipped": 2, "failed": 0, "added_ids": ["..."], "failures": [] }
```
去重规则：先按 `source_job_id` 命中跳过；无 source_job_id 时按 `company_id`（或归一化公司名）+ 规范化岗位名 + city 判定（岗位名规范化：去【】批次前缀、去「急聘/热招」后缀、去空格与全半角差异；公司名归一化：去「有限公司/股份/（中国）」后缀）。

#### 简历 resumes
- `GET /api/resumes` → `{items, total}`。
- `POST /api/resumes` → 创建，请求体：
```json
{
  "name": "简历 v2-算法岗",
  "basic": { "name": "张三", "phone": "138...", "email": "a@b.com", "target_position": "算法工程师", "city": "北京" },
  "education": [ { "school": "XX大学", "major": "计算机", "degree": "硕士", "start_date": "2023-09", "end_date": "2026-06", "description": "..." } ],
  "experience": [ { "company": "...", "position": "...", "start_date": "...", "end_date": "...", "responsibilities": "..." } ],
  "projects": [ { "name": "...", "role": "...", "start_date": "...", "end_date": "...", "description": "..." } ],
  "skills": ["Python", "PyTorch"],
  "summary": "..."
}
```
- `GET /api/resumes/{id}` / `PUT /api/resumes/{id}`（更新刷新 updated_at）/ `DELETE /api/resumes/{id}`（删除；若被岗位引用，返回引用数 `{ "referenced_by": 3 }` 供前端二次确认，确认后删除并将引用岗位的 resume_id/resume_name 置空）。

#### 公司 companies
- `GET /api/companies` → `{items, total}`。
- `POST /api/companies` → 创建，请求体 `{ "name": "字节跳动", "website": "https://www.bytedance.com", "industry": "互联网", "notes": "" }`；`name` 重复返回 409 CONFLICT。响应 201 + company。
- `GET /api/companies/{id}` / `PUT /api/companies/{id}`（可人工修正 `career_url`）/ `DELETE /api/companies/{id}`（删除公司不删除其岗位，岗位 company_id 置空）。
- `POST /api/companies/{id}/probe` → 探测招聘页（异步）。响应 202 `{ "job_id": "uuid", "type": "probe" }`。
- `POST /api/companies/{id}/fetch` → 抓取岗位（异步）。请求体可选 `{ "career_url": "https://..." }`（不传则用公司已存 career_url）。响应 202 `{ "job_id": "uuid", "type": "fetch" }`。

#### 任务 tasks
- `GET /api/tasks/{job_id}` → 轮询：
```json
{ "job_id": "uuid", "type": "probe", "status": "queued|running|done|failed",
  "progress": "首页扫描", "result": { "...": "done 时按任务类型返回" },
  "error": { "code": "ROBOTS_DISALLOW", "message": "robots.txt 禁止抓取" } }
```
probe 的 `result`：
```json
{ "candidates": [ { "url": "https://.../careers", "confidence": "high|medium|low",
                     "source": "sitemap|homepage|subdomain|robots", "reason": "..." } ] }
```
fetch 的 `result`：
```json
{ "ats_type": "greenhouse", "career_url": "https://...",
  "job_candidates": [ { "position": "...", "city": "...", "job_url": "...", "source_job_id": "...",
                        "deadline": null, "degree": null, "job_type": "校招" } ], "count": 10 }
```

#### 备份 backup
- `GET /api/backup/export` → 全量备份（含三集合 + schema_version）：
```json
{ "schema_version": 1, "exported_at": "2026-08-24T20:00:00",
  "jobs": [...], "companies": [...], "resumes": [...] }
```
- `POST /api/backup/import` → 请求体：
```json
{ "schema_version": 1, "mode": "merge|overwrite",
  "jobs": [...], "companies": [...], "resumes": [...] }
```
响应 200：
```json
{ "mode": "merge", "jobs_added": 10, "jobs_skipped": 3, "companies_added": 2, "resumes_added": 1,
  "errors": [] }
```
规则：merge 模式同 id 以本机为准（跳过并计 skipped）；overwrite 模式全量替换（前端二次确认）；导入前校验 JSON 结构/schema_version/必填字段，非法返回 422 且不改动现有数据；导入后岗位对简历/公司引用按 id 恢复，无引用对象置空。

#### 统计 stats（M2 契约先定）
- `GET /api/stats` →
```json
{ "total_applied": 40, "active": 20, "offered": 2, "rejected": 5, "pending_followup": 3,
  "funnel": [ { "status": "已投递", "count": 40 } ],
  "channel_dist": [ { "channel": "官网", "count": 30 } ],
  "weekly_trend": [ { "week_start": "2026-08-17", "count": 8 } ] }
```
指标口径按 PRD 4.8：总投递=已投递及之后状态；进行中=已投递至三面/HR面且未到终态；待跟进=已投递且距上次流转 >3 天；趋势按 applied_at。

---

## 5. 抓取模块设计

### 5.1 模块结构与职责

```
backend/app/fetcher/
  probe.py        # 探测分层（robots / 首页链接 / sitemap / 子域候选）
  ats/
    __init__.py   # 适配器注册表 + 识别
    base.py       # ATSAdapter Protocol / ABC 接口定义
    greenhouse.py # Greenhouse 适配器
    lever.py      # Lever 适配器
    feishu.py     # 飞书招聘适配器
    jsonld.py     # JSON-LD 通用兜底解析器
  rate_limiter.py # 限速器（全局令牌桶 + 同域间隔）
  tasks.py        # 内存任务表 + 后台工作线程
  http.py         # httpx 客户端封装（固定 UA、超时、超时降级）
  normalize.py    # 岗位名/公司名规范化（去重用）
```

### 5.2 适配器接口（Python 协议定义）

```python
# ats/base.py
from typing import Protocol, List, Optional
from pydantic import BaseModel

class JobCandidate(BaseModel):
    """适配器产出的岗位候选，字段即 jobs 表抓取字段。"""
    position: str
    city: Optional[str] = None
    job_url: Optional[str] = None
    source_job_id: Optional[str] = None
    deadline: Optional[str] = None
    degree: Optional[str] = None
    job_type: Optional[str] = None  # 校招/社招/实习

class ATSAdapter(Protocol):
    name: str          # 如 "greenhouse"
    def detect(self, url: str, html: str) -> bool:
        """根据 URL 特征与页面内容判断是否命中该 ATS。"""
        ...
    def extract_jobs(self, html: str, base_url: str) -> List[JobCandidate]:
        """从页面 HTML 提取岗位列表。"""
        ...
```

识别流程：`detect(url)` 依次用各适配器 `detect`（先 URL 特征快匹配，再必要时看 HTML），命中即用其 `extract_jobs`；全部未命中则走 JSON-LD 兜底；JSON-LD 也解析不出则返回失败原因。

### 5.3 探测分层（probe.py）

执行顺序（任一命中即收集候选，最终返回候选列表 + 置信度，供人工择一）：

1. **robots.txt 检查**：请求 `{origin}/robots.txt`；若该域名/路径 Disallow 招聘页，标记 `ROBOTS_DISALLOW` 并停止（任务失败，提示原因，公司 `probe_status=需人工`）。同时收集其 `Sitemap:` 条目。
2. **首页链接扫描**：请求官网首页，`a[href]` 含 `careers|jobs|recruit|招聘|加入我们` 的 URL 作为候选（confidence 按关键词精确度定 high/medium）。
3. **Sitemap 解析**：拉取 robots 中 Sitemap 指向的 sitemap(.xml/.gz)，解析 URL，命中含 `career|job|recruit` 的 URL 入候选（confidence high）。
4. **常见招聘子域候选**：对已知域名生成候选，如 `talent.{domain}`、`campus.{domain}`、`careers.{domain}`、`jobs.{domain}`、飞书 `{tenant}.jobs.feishu.cn`，仅探测是否可访问（confidence low，需人工确认）。

产出 `ProbeCandidate { url, confidence, source, reason }` 列表；探测完成后可把置信度最高的写入 `companies.career_url`（仍需前端人工确认/修正，修正值持久化复用）。

### 5.4 ATS 适配器数据获取与字段映射

**Greenhouse**
- 识别：URL 含 `greenhouse.io` / `boards.greenhouse.io` / `boards-api.greenhouse.io`。
- 获取：优先调公开 board API `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs`（JSON，稳定）；失败则解析 HTML 页面。
- 映射：`id` → source_job_id；`title` → position；`location.name` → city；`absolute_url` → job_url；`updated_at` → publish_date（尽力）。job_type/degree 尽力从 `metadata`/字段解析。

**Lever**
- 识别：URL 含 `lever.co` / `jobs.lever.co`。
- 获取：`GET https://api.lever.co/v0/postings/{company}?mode=json`（公开 API）；失败解析 HTML。
- 映射：`id` → source_job_id；`text` → position；`categories.location` → city；`hostedUrl` → job_url；`createdAt` → publish_date（尽力）。

**飞书招聘（Feishu）**
- 识别：URL 含 `jobs.feishu.cn` 或 `.feishu.cn` 招聘子域，或页面含飞书招聘标识。
- 获取：飞书招聘为 JS 渲染 SPA、无稳定公开 JSON API，适配器抓取 HTML 后尝试提取内嵌 JSON（`__NEXT_DATA__` / `window.__INITIAL_STATE__` / `__APP_DATA__` 等常见注入点），解析其中岗位列表；失败降级。
- 映射：`post_id`/`job_id`/`id` → source_job_id；`name`/`title` → position；`city`/`work_location` → city；链接拼接 → job_url；发布时间 → publish_date（尽力）。
- 说明：飞书适配解析成功率不稳定，失败时任务降级「保留链接+手动录入」，不影响整体。

**JSON-LD 通用兜底（jsonld.py）**
- 解析页面所有 `<script type="application/ld+json">`，筛选 `@type` 含 `JobPosting`（或 `@graph` 内嵌）的对象。
- 映射：`title` → position；`jobLocation.address.addressLocality` → city；`url` → job_url；`identifier.value` → source_job_id；`validThrough` → deadline；`datePosted` → publish_date；`employmentType` → job_type（校招/社招/实习 尽力映射）；`educationRequirements` → degree（尽力）。
- 覆盖：Greenhouse/Lever 未命中、以及未来大量采用 JSON-LD 的官网，无需逐个写适配器。

### 5.5 限速与异步任务实现

**限速器（rate_limiter.py）**
- 全局令牌桶：每分钟 30 个令牌（`≤30 req/min`），请求前取令牌，不足则 sleep 至下个令牌可用。
- 同域间隔：维护 `dict[domain, last_ts]`，同域名下次请求前保证 `now - last_ts >= 1.5s`，不足 sleep。
- 全部在后台工作线程内同步执行，天然串行（并发=1）。
- 固定 UA：`JobHunter/1.0 (personal-use job tracker; +local)`。

**异步任务（tasks.py）**
- 内存任务表：`TASKS: dict[str, Task]` + `threading.Lock`。`Task` 含 `job_id/type/status/progress/result/error/created_at`，status ∈ `{queued, running, done, failed}`。
- 提交：`POST probe/fetch` 生成 `job_id`，写 `queued`，放入 `queue.Queue`，立即返回 job_id（HTTP 202）。
- 执行：单个后台守护线程（daemon thread）`run_worker()` 循环从队列取任务，置 `running`，执行 probe/fetch，置 `done`（写 result）或 `failed`（写 error）。串行 = 天然限速与低并发。
- 超时：httpx 单请求 `timeout=10s`；整任务用 `threading.Timer` 或 deadline 检查（start + 60s），超时置 `failed` 并附 `TIMEOUT`，公司 `probe_status=需人工`、`last_fetch_result="超时，请手动录入"`。
- 任务清理：保留最近 N 条（如 100 条）防止内存无限增长；进程重启任务清空（个人工具可接受，抓取可重试）。
- 幂等：重复「抓取」不重复写入岗位（导入去重），不产生副作用。

### 5.6 降级与错误处理

| 场景 | 处理 |
|---|---|
| robots.txt Disallow | 任务 failed，`ROBOTS_DISALLOW`，公司 probe_status=需人工，前端提示「该站点禁止抓取，请手动录入」 |
| 探测无候选 | result 空 candidates + reason，probe_status=需人工，允许手动填 career_url |
| 解析 0 条岗位 | 任务 done 但 count=0 + 原因，前端提示原因，降级手动录入 |
| 单请求超时 / 整任务超时 | failed + TIMEOUT，保留 career_url，降级手动录入 |
| 解析异常（部分成功） | 返回已解析候选 + 失败原因；导入时逐条计入 failed |
| 官网岗位已删除 | 不删除本机记录，仅统计新增/跳过（导入不改动现有岗位） |

---

## 6. 前端架构

### 6.1 目录结构

```
frontend/
  vite.config.ts          # proxy /api → http://127.0.0.1:8000
  index.html
  src/
    main.ts
    App.vue
    router/index.ts
    stores/
      jobs.ts             # 岗位列表/筛选/CRUD/状态流转
      companies.ts        # 公司库 + probe/fetch 任务轮询
      resumes.ts          # 简历 CRUD
      ui.ts               # 视图模式、筛选偏好、主题（localStorage 瞬时状态）
    api/
      http.ts             # axios 实例 + token 注入 + 错误处理
      boot.ts / jobs.ts / resumes.ts / companies.ts / tasks.ts / backup.ts / stats.ts
    types/index.ts        # TS 接口（Job/JobEvent/Company/Resume/...）
    views/
      BoardView.vue       # 看板
      ListView.vue        # 列表
      CompanyView.vue     # 公司库
      ResumeListView.vue  # 简历列表
      ResumeEditView.vue  # 简历编辑
      ResumePreviewView.vue # 简历预览/打印
      StatsView.vue       # 统计（M2）
      SettingsView.vue    # 设置
    components/
      JobCard.vue / JobFormModal.vue / StatusBadge.vue / KanbanColumn.vue
      FilterBar.vue / TimelinePanel.vue / ImportPreviewModal.vue
      ProbeResultPanel.vue / FetchPreviewModal.vue / ConfirmDialog.vue
      ResumeRenderer.vue  # A4 简历渲染（供预览/打印复用）
    utils/
      date.ts / normalize.ts / download.ts
```

### 6.2 路由与页面

| 路径 | 页面 | 说明 |
|---|---|---|
| `/` | BoardView | 看板（默认不展示终态，含「含已结束」开关） |
| `/jobs` | ListView | 列表（排序、筛选、批量操作） |
| `/companies` | CompanyView | 公司库 + 探测/抓取 |
| `/resumes` | ResumeListView | 简历列表 |
| `/resumes/:id` | ResumeEditView | 简历编辑 |
| `/resumes/:id/preview` | ResumePreviewView | 预览 + window.print() 打印/PDF |
| `/stats` | StatsView | 统计（M2） |
| `/settings` | SettingsView | 备份、通知授权、关于 |

### 6.3 Pinia store 划分

- **jobsStore**：`items/total/filters` 状态；`fetchJobs()`（带筛选参数）、`createJob()`、`updateJob()`、`deleteJob()`、`batchDelete()`、`changeStatus(id, status, note)`、`importJobs(payload)`；`changeStatus` 成功后用返回的 job 与 event 就地更新（列表替换 + 时间线追加）。
- **companiesStore**：`items`；`fetchCompanies()`、`createCompany()`、`updateCompany()`、`deleteCompany()`、`probe(id)`、`fetchJobs(id, careerUrl?)`；probe/fetch 后启动 `pollTask(jobId, onDone)` 轮询（每 1~2s，超时上限如 90s）。
- **resumesStore**：`items`；`fetchResumes()`、`create/update/delete`、`referencedBy(id)`。
- **uiStore**：`viewMode`、`filters`、`includeEnded`、`theme`——用 localStorage 持久化瞬时偏好（非业务数据，符合 PRD 4.6）。

### 6.4 API 封装（含 token）

`http.ts`：创建 axios 实例 `baseURL='/api'`，请求拦截器注入 `X-Auth-Token`（内存变量 + sessionStorage 兜底）；响应拦截器统一处理错误结构，401 时重新 `GET /boot` 刷新 token 并重试一次。应用启动流程：`main.ts` → `boot()` 获取 token 与 schema_version → 存入 http 实例 → 再加载各 store 数据。

### 6.5 关键交互

- **状态流转**：看板列拖拽（vuedraggable 跨列 group）与详情下拉改状态等价，均调 `POST /api/jobs/{id}/status`；拖到同一列不调用。成功后本地更新，卡顿规避：先乐观更新 UI，失败回滚。
- **拖拽**：看板列 = 状态全集（终态列默认收起在「含已结束」开关下）；拖拽结束事件 `@end` 触发 `changeStatus`。
- **抓取预览导入**：CompanyView 选公司 → `probe` → 轮询 → 候选列表人工择一（或手填 career_url）→ `fetch` → 轮询 → FetchPreviewModal 展示岗位列表 → 勾选/全选 → `POST /api/jobs/import` → 展示「新增 N、跳过 M、失败 K」。
- **简历打印**：ResumePreviewView 用 ResumeRenderer 按 A4 版式渲染，`@media print` + `@page { size: A4; margin: 0 }` 样式，点击导出调 `window.print()` 由用户另存 PDF。
- **备份**：SettingsView 导出按钮调 `GET /api/backup/export` 后用 `download.ts` 生成 JSON 文件；导入选文件解析后选 merge/overwrite（overwrite 弹二次确认）调 `POST /api/backup/import`。

---

## 7. 安全与隐私实现要点

| 项 | 具体做法 |
|---|---|
| 仅监听本机 | uvicorn `host="127.0.0.1"`，不绑定 0.0.0.0；启动日志明确提示本机范围 |
| CORS 白名单 | `CORSMiddleware` 仅允许 `http://127.0.0.1:5173`、`http://localhost:5173`（前端 dev 来源）；`allow_credentials` 关闭、`allow_methods` 仅所需 |
| Host 头校验 | 自定义中间件：校验 `request.headers["host"]` 主机部分 ∈ `{127.0.0.1, localhost}`（含端口），否则返回 403 FORBIDDEN。防 DNS rebinding 攻击（外部域名解析到 127.0.0.1 携带恶意 Host 被拒） |
| 随机 token | 启动 `secrets.token_hex(32)` 生成一次性 token；`GET /api/boot` 下发（boot 本身受 Host + Origin 校验保护）；后续所有接口校验 `X-Auth-Token` 等于该 token，否则 401。token 存内存，重启重新生成 |
| 数据不出本机 | 所有业务数据仅写本地 SQLite；无第三方统计脚本、无遥测；抓取仅访问目标公司官网公开招聘页 |
| 抓取合规 | 抓取前查 robots.txt（Disallow 跳过）、低频限速（串行/同域 ≥1.5s/全局 ≤30 req/min）、固定 UA 标识个人工具；不绕过登录/验证码/付费墙 |
| 隐私 | 简历等敏感材料仅文字存本机；导出文件仅由用户主动触发下载 |

> 无登录信任边界说明：本机 `127.0.0.1` 范围内视为可信（同一 OS 用户可访问本地进程）；token + Host 校验的作用是阻止「浏览器被诱导访问本机服务」类的跨站/DNS rebinding 攻击，而非多用户鉴权。后续部署服务器时需升级为真实鉴权（见 9 章预留）。

---

## 8. M1 任务拆解

> 顺序 P0（核心投递管理）→ P1（简历）→ P2（抓取）。P0 完成即可先行使用；P1、P2 依赖 P0 的基础设施（后端骨架/前端骨架/API 封装）。标注 [P] 可并行、[D] 依赖。

### P0 核心投递管理（后端 0.5–1 天 + 前端 1.5–2 天）

| # | 子任务 | 估时 | 依赖 |
|---|---|---|---|
| P0-1 | 后端骨架：FastAPI 应用、uvicorn 启动、配置、日志 | 0.5d | — |
| P0-2 | 数据层：连接工厂 + WAL/外键 PRAGMA + 迁移执行器 + `001_init.sql` | 0.5d | P0-1 |
| P0-3 | jobs DAO + service：CRUD、筛选（状态/公司/城市/行业/渠道/关键词）、排序 | 0.5d | P0-2 |
| P0-4 | 状态流转接口 + job_events 写入 + 终态 ended_at 逻辑 | 0.5d | P0-3 |
| P0-5 | 安全中间件：CORS 白名单 + Host 校验 + token + `/api/boot` | 0.5d | P0-1 [P 与 P0-3 并行] |
| P0-6 | 前端骨架：Vite + Vue3 + TS + Router + Pinia + axios 封装（token） | 0.5d | P0-1 [P 与 P0-2 并行] |
| P0-7 | 看板视图（状态列 + 卡片 + 拖拽流转） | 1d | P0-6, P0-4 |
| P0-8 | 列表视图（排序/筛选/批量删除/编辑表单/删除二次确认） | 1d | P0-6, P0-3 |
| P0-9 | 筛选栏 + 搜索 + 时间线面板（events 展示） | 0.5d | P0-7, P0-8 |
| P0-10 | 联调 + P0 自测（录入/流转/筛选/持久化） | 0.5d | P0-7..P0-9 |

### P1 简历（后端 0.5 天 + 前端 1–1.5 天）

| # | 子任务 | 估时 | 依赖 |
|---|---|---|---|
| P1-1 | resumes DAO + service + CRUD + 引用计数 | 0.5d | P0-2 |
| P1-2 | 岗位 resume_id/resume_name 绑定（编辑表单 + 快照） | 0.5d | P0-3, P1-1 |
| P1-3 | 简历列表页 + 编辑页（结构化区块表单） | 1d | P0-6, P1-1 |
| P1-4 | A4 简历渲染 + 预览 + window.print 打印/PDF | 0.5d | P1-3 |
| P1-5 | 简历删除引用提示 + 置空联动 | 0.25d | P1-1, P0-8 |
| P1-6 | 联调 + 简历自测 | 0.25d | P1-2..P1-5 |

### P2 抓取（后端 1–1.5 天 + 前端 1 天）

| # | 子任务 | 估时 | 依赖 |
|---|---|---|---|
| P2-1 | 抓取基础设施：httpx 客户端（UA/超时）、限速器、robots 检查 | 0.5d | P0-1 |
| P2-2 | 异步任务表 + 后台工作线程 + `/api/tasks` | 0.5d | P2-1, P0-1 |
| P2-3 | probe 分层（首页扫描/sitemap/子域候选） | 0.5d | P2-1 |
| P2-4 | ATS 适配器：Greenhouse + Lever + 飞书 + JSON-LD 兜底 + 识别注册表 | 1d | P2-1 |
| P2-5 | companies CRUD + probe/fetch 接口 + 抓取结果落库（含 probe_status/ats_type/last_fetch_result） | 0.5d | P2-2, P2-3, P2-4 |
| P2-6 | `/api/jobs/import` 去重（规范化 + source_job_id 优先） | 0.5d | P0-3, P2-5 |
| P2-7 | 前端公司库页 + probe/fetch 轮询 + 预览导入 UI | 1d | P0-6, P2-5, P2-6 |
| P2-8 | 联调 + 抓取自测（含降级/失败路径） | 0.5d | P2-5..P2-7 |

### 交叉交付项（贯穿 M1）

| # | 子任务 | 估时 | 依赖 |
|---|---|---|---|
| X-1 | `/api/backup/export|import`（含 schema_version 校验、merge/overwrite） | 0.5d | P0-2, P1-1, P2-5 |
| X-2 | `/api/stats` 基础契约（数据就绪后实现，M2 出界面） | 0.5d | P0-3 |
| X-3 | 启动备份提醒（距上次导出 >7 天提示） | 0.25d | X-1 |
| X-4 | M1 全量回归 + 冒烟（含备份恢复、抓取降级） | 1d | 全部 |

合计估算：约 8–10 人天（含 2 天 buffer 与测试，符合 PRD「2–2.5 周」且无硬节点）。

---

## 9. 开放风险与后续演进

### 9.1 风险与缓解（施工提醒）

| 风险 | 缓解（落到实现） |
|---|---|
| 飞书/动态站点解析失败 | 飞书适配器尝试多注入点提取，失败即降级手动录入；不阻塞其他功能 |
| 抓取触发反爬 | 严格限速 + robots 遵守 + 固定 UA；被限时人工浏览后手动录入 |
| SQLite 文件损坏 | WAL + 定期导出 JSON 为主备份 + 启动 >7 天提醒 |
| 简历打印分页差异 | 默认 window.print()；A4 版式为人工验收项，必要时评估 html2pdf.js（Q6 后备） |
| 端口占用/多实例 | 启动探测可用端口 + 明确错误提示；SQLite busy_timeout 降低并发冲突 |
| 提醒在页面关闭后失效 | 站内为主、浏览器通知为辅；M3 可选后端定时任务 |

### 9.2 M2 抓取适配扩展点

- 新增 ATS：在 `ats/` 下新增实现 `ATSAdapter` 的类并注册到 `ats/__init__.py` 注册表即可，业务层与前端零改动。
- M2 计划适配：北森（beisen）、Moka、大易（dayee）——各自实现 `detect` + `extract_jobs`（优先找其公开 JSON 接口或页面内嵌 JSON，无则 JSON-LD 兜底/降级）。
- 去重规范化函数 `normalize.py` 独立，新增站点时复用。

### 9.3 M3 可选项

- 导出 Excel/CSV（字段投影，不含时间线）；暗色模式；收藏/加急置顶（后续可加 `priority` 字段）。
- 本机「双击即用」：`vite build` 产物由 FastAPI `StaticFiles` 托管，前端路由用 SPA fallback。
- 后端定时任务提醒（应用开着时准时提醒，Q2 增强）。
- 简历多模板渲染（Q7，默认 1 套 A4）。

### 9.4 未来部署服务器鉴权预留

- 现状 token/Host 校验只针对本机；若部署到个人服务器（Q1），需升级：
  1. Host 校验白名单放开为域名，CORS 白名单改为正式前端域名。
  2. token 升级为真实登录（如单一用户口令 → 会话 token，或反向代理 Basic Auth/Cloudflare Access）。
  3. 传输强制 HTTPS；SQLite 备份与端口暴露需重新评估。
- 架构上已预留：鉴权集中在中间件一处，升级不改业务代码；数据层/接口契约不变，迁移成本低。
