# 秋招投递助手 API 契约（M1）

版本：v1.1（对应架构文档 v1.0 / PRD v0.6）
> v1.1 修订（PRD v0.6 §4.12）：新增公司批量导入、按公司名自动补全（映射表 + 搜索兜底）三个端点及 resolve 异步任务。
Base URL：`http://127.0.0.1:<port>/api`；Content-Type `application/json`（UTF-8）。

## 通用约定

- 鉴权：除 `GET /api/boot` 外，所有请求携带 `X-Auth-Token: <token>`（token 来自 boot，重启后重新生成）。
- 列表响应统一：`{ "items": [...], "total": n }`；单资源响应直接返回对象。
- 统一错误结构（HTTP 4xx/5xx）：

```json
{ "error": { "code": "NOT_FOUND", "message": "岗位不存在", "details": { "id": "..." } } }
```

| HTTP | code | 含义 |
|---|---|---|
| 400 | VALIDATION_ERROR | 请求体/参数校验失败 |
| 401 | UNAUTHORIZED | token 缺失或错误 |
| 403 | FORBIDDEN | Host/Origin 校验失败 |
| 404 | NOT_FOUND | 资源不存在 |
| 409 | CONFLICT | 冲突（公司名重复等） |
| 422 | IMPORT_ERROR | 导入文件非法（字段缺失/版本过高） |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

时间格式：`YYYY-MM-DD`（date 字段）/ `YYYY-MM-DDTHH:MM:SS`（datetime 字段，本地时区）。

---

## 系统

### GET /api/boot
无 token。返回：

```json
{
  "token": "hex64",
  "schema_version": 1,
  "app": { "name": "秋招投递助手", "version": "0.1.0" },
  "backup": { "last_exported_at": null, "days_since": null, "need_backup": false }
}
```

`backup` 为启动备份提醒（距上次导出 >7 天提示，X-3）。

---

## 岗位 jobs

### GET /api/jobs
查询参数（均可选）：`status`（多值逗号分隔）、`company`、`city`、`industry`、`channel`、`keyword`（匹配 company/position，LIKE）、`include_ended`（bool，默认 false 过滤终态）、`sort`（默认 `updated_at desc`，白名单：company/updated_at/deadline/applied_at/created_at/status/position）、`sort_dir`。
响应 `{items, total}`，item 不含 events。

### POST /api/jobs
请求体（仅 `company` 必填）：`company, company_id, position, job_type, degree, city, industry, channel, job_url, source_job_id, publish_date, deadline, resume_id`。
响应 201 + 完整 job（status 默认 `待投递`，含 created_at/updated_at）。

### GET /api/jobs/{id}
详情：job 对象 + `events` 数组（时间线，按 time 升序）。

### PUT /api/jobs/{id}
部分更新，仅更新传入字段并刷新 `updated_at`；`status`/`ended_at` 不经此接口（走流转接口）。返回完整 job。

### DELETE /api/jobs/{id}
硬删除（级联删 job_events），响应 204。

### POST /api/jobs/batch-delete
请求体 `{ "ids": ["..."] }`，响应 `{ "deleted": n }`。

### POST /api/jobs/{id}/status
请求体：`{ "status": "笔试", "note": "...", "time": "2026-08-24T10:00:00" }`（time 可选，默认服务端当前时间）。
响应 200：`{ "job": {...}, "event": {...} }`。
业务规则：同状态流转 `event` 为 null 且不写事件；进终态写 `ended_at`，回退清 `ended_at`；进入「已投递」记 `applied_at`（不覆盖已有值）；非法状态 400。

### POST /api/jobs/import
抓取/批量导入岗位（去重）。请求体：

```json
{ "company_id": "uuid", "jobs": [ { "position": "...", "city": "...", "job_url": "...",
  "source_job_id": "...", "deadline": null, "degree": "本科", "job_type": "校招" } ] }
```

响应 200：`{ "added": n, "skipped": m, "failed": k, "added_ids": [...], "failures": [...] }`。
去重规则：先按 `source_job_id`（限定同一公司）命中跳过；无 source_job_id 时按 公司 + 规范化岗位名 + city 判定（规范化：去【】批次前缀、去「急聘/热招」后缀、去空格与全半角差异）。导入成功后回写公司 `last_fetched_at` / `last_fetch_result`（"新增 N 条，跳过 M 条，失败 K 条"）。

---

## 简历 resumes

### GET /api/resumes
响应 `{items, total}`。

### POST /api/resumes
请求体：`name`（必填）、`basic`（必填：name/phone/email/target_position/city）、`education`、`experience`、`projects`、`skills`、`summary`。
响应 201 + resume。

### GET /api/resumes/{id} / PUT /api/resumes/{id}
详情 / 部分更新（刷新 updated_at）。

### DELETE /api/resumes/{id}
若被岗位引用且未 `?force=true`：返回 `{ "referenced_by": n, "deleted": false }` 供二次确认；
`?force=true` 后删除并将引用岗位的 resume_id/resume_name 置空，响应 204。

---

## 公司 companies

### GET /api/companies
查询公司库（支持筛选，参数均可选，组合生效）：
`?city=北京`（城市 LIKE 模糊）、`?industry=互联网`（行业精确）、`?nature=国企`（公司性质精确）、`?keyword=字节`（公司名 LIKE 模糊）。
响应 `{items, total}`，item 含 `city`（城市）、`nature`（公司性质：国企/央企/私企/外企/合资/事业单位/其他，可自定义）。

### POST /api/companies
请求体 `{ "name": "...", "website": "...", "industry": null, "city": null, "nature": null, "notes": null }`；`name` 重复返回 409 CONFLICT。响应 201 + company。

### POST /api/companies/import
公司批量导入（PRD 4.12，txt 每行一个公司名由前端拆行后传入）。请求体：

```json
{ "names": ["字节跳动", "美团", "美团"], "resolve": false }
```

规则：忽略空行与首尾空格；批内按公司名归一化（去「有限公司/股份/（中国）」后缀）去重；与已有公司归一化重名则跳过并计数。创建的公司 `website` 为空（待补全）。

- `resolve=false`：响应 200：
  ```json
  { "added": 2, "skipped": 1, "skipped_names": ["美团"], "added_ids": ["uuid", "uuid"] }
  ```
- `resolve=true`：同步创建后启动异步批量补全任务（type=`resolve`），响应 200 在上一结构基础上附加 `"job_id": "uuid"`；若全部跳过则不产生任务（无 `job_id` 字段）。补全结果自动写入缺失字段（仅填充 `website/industry/career_url` 为空的字段，不覆盖已有值，防误配覆盖手填数据）。

### POST /api/companies/batch-delete
批量删除公司。请求体 `{ "ids": ["uuid", "..."] }`。响应 200 `{ "deleted": n }`。先解除关联岗位（岗位保留、`company_id` 置空），再物理删除；不存在的 id 忽略。

### POST /api/companies/batch-probe
批量探测招聘入口（与单条 probe 语义一致）。请求体 `{ "ids": ["uuid", "..."] }`。响应 202 `{ "job_id": "uuid", "type": "probe_batch" }`。逐公司写 `probe_status`（有候选「成功」/ 无候选「需人工」），`career_url` 仅在公司缺失时写入最高置信度候选；单公司失败不阻塞其余。空 ids 返回 400 VALIDATION_ERROR。

### POST /api/companies/batch-resolve
批量补全已存公司（与 import 的 resolve 任务同一实现）。请求体 `{ "ids": ["uuid", "..."] }`。响应 202 `{ "job_id": "uuid", "type": "resolve" }`。结果自动写入缺失字段（不覆盖已有值）；单公司失败不阻塞其余。空 ids 返回 400 VALIDATION_ERROR。

### POST /api/companies/resolve
仅凭公司名称自动补全（PRD 4.12，不落库）。请求体 `{ "name": "字节跳动" }`。响应 200：

```json
{ "name": "字节跳动", "website": "https://www.bytedance.com",
  "industry": "互联网", "city": "北京", "nature": "私企",
  "career_url": "https://jobs.bytedance.com/",
  "source": "mapping", "confidence": "high" }
```

四级流水线，`source` 依次判定：
1. `mapping`：内置映射表（233 家 = 101 家手工精选 + guoyang-pro 央企国企名录 132 家，数据来源见文末），含官网/行业/城市/性质/招聘站，`confidence: "high"`；名录条目缺官网时继续走搜索补官网（元数据以名录为准，source 仍标 `search` 供核对）。
2. `info`：A股上市公司离线库（巨潮资讯 cninfo 导出，`app/fetcher/company_info_data.json`），提供官网/行业/注册城市（无招聘站与性质），离线命中 `confidence: "high"`。
3. `icp`：ICP 备案反查（需自建 ICP_Query 服务并配置环境变量 `ICP_API_URL`，未配置自动跳过），按公司名返回官方域名，`confidence: "high"`；结果缓存进 SQLite `icp_cache` 表 90 天。
4. `search`：Bing 搜索兜底（cn.bing.com 主用、www.bing.com 兜底，瞬时网络错误自动重试；复用抓取限速：固定 UA、单请求 10s、同域 ≥1.5s、全局 ≤30 请求/分钟），附加 `confidence`：
   - `high`：候选官网首页标题/描述/OG 标签/正文含公司名核心串（过滤搜索引擎/内容平台/政府/字典/工商查询/招聘站等非官网域名；SPA 站点兼容 meta/OG 标签校验）；
   - `medium`：首页抓取失败/超时/无文本（SPA、反爬、网络问题），但搜索结果标题/摘要已含完整公司名核心串 → 接受但需人工核对（前端红色警示）；首页「可访问但不含公司名」坚决拒绝，不降级为中置信。
   - `website` 为通过校验的主域名，`career_url` 为 probe 最高置信度候选或 null；`industry` 从搜索结果摘要/官网文本按关键词计数评分（优先短文本，整页兜底）；`city`/`nature` 从摘要/官网文本尽力提取（「总部/注册地/位于」上下文或公司名自带地名；性质关键词 央企/国企/外企/合资/私企），提取不到为 null。
- 搜索失败或未找到可靠官网 → `source: "failed"`，附加 `"error": "未找到可靠官网，请手动填写"`，website/industry/career_url/city/nature 为 null（**不写入任何字段**，防误配）。
- 空 `name` 返回 400 VALIDATION_ERROR。

### POST /api/companies/{id}/resolve
对已有公司执行同样补全（不落库）。响应同构（含 `company_id`）：

```json
{ "company_id": "uuid", "name": "腾讯", "website": "https://www.tencent.com",
  "industry": "互联网", "city": "深圳", "nature": "私企",
  "career_url": "https://careers.tencent.com/", "source": "mapping" }
```

公司不存在返回 404 NOT_FOUND。

### GET/PUT/DELETE /api/companies/{id}
详情 / 更新（可人工修正 `career_url` 等）/ 删除（不删岗位，岗位 company_id 置空），删除 204。

### POST /api/companies/{id}/probe
异步探测招聘入口。响应 202 `{ "job_id": "uuid", "type": "probe" }`。

### POST /api/companies/{id}/fetch
异步抓取岗位。请求体可选 `{ "career_url": "https://..." }`（不传用公司已存 career_url）。响应 202 `{ "job_id": "uuid", "type": "fetch" }`。

---

## 任务 tasks

### GET /api/tasks/{job_id}
轮询：`{ "job_id", "type", "status": "queued|running|done|failed", "progress", "result", "error" }`。

- probe 的 result：`{ "candidates": [ { "url", "confidence": "high|medium|low", "source": "homepage|sitemap|subdomain|existing", "reason" } ] }`
- fetch 的 result：`{ "ats_type": "greenhouse|lever|feishu|jsonld", "career_url", "job_candidates": [ { "position", "city", "job_url", "source_job_id", "deadline", "degree", "job_type" } ], "count" }`
- resolve 的 result（批量自动补全，结果自动写入缺失字段）：`{ "results": [ { "company_id", "name", "website", "industry", "city", "nature", "career_url", "source": "mapping|search|failed|skipped", "confidence?", "error?" } ], "resolved": n, "total": m }`；progress 为「已补全 x/m」。仅填充缺失字段（website/industry/career_url/city/nature），不覆盖已有值；非映射公司主体信息已完整、仅缺城市/性质时跳过（避免无意义网络搜索，搜索兜底对这两项只能尽力提取）。
- probe_batch 的 result：`{ "results": [ { "company_id", "name", "status": "成功|需人工|failed", "career_url?", "error?" } ], "ok": n, "manual": n, "failed": n, "total": m }`；progress 为「已探测 x/m」。
- error：`{ "code": "ROBOTS_DISALLOW|TIMEOUT|NO_CAREER_URL|HTTP_ERROR|...", "message" }`

任务失败时公司 `probe_status=需人工`；抓取超时 `last_fetch_result="超时，请手动录入"`。

---

## 备份 backup

### GET /api/backup/export
全量备份：`{ "schema_version": 1, "exported_at": "...", "jobs": [...], "companies": [...], "resumes": [...] }`。
导出后记录上次导出时间（供启动备份提醒）。

### POST /api/backup/import
请求体：`{ "schema_version": 1, "mode": "merge|overwrite", "jobs": [...], "companies": [...], "resumes": [...] }`。
响应 200：`{ "mode", "jobs_added", "jobs_skipped", "companies_added", "resumes_added", "errors": [] }`。
规则：
- 校验 schema_version（高于当前支持版本 → 422）、必填字段（job: id/company；company: id/name/website；resume: id/name/basic.name），非法 422 且不改动现有数据。
- merge：同 id 以本机为准跳过并计 skipped；公司名冲突跳过记入 errors。
- overwrite：全量替换（前端二次确认）；备份内不存在的公司/简历引用置空（不违反外键）；同 id 岗位保留本机时间线（备份不含 events）。

---

## 统计 stats

### GET /api/stats
口径按 PRD 4.8：

```json
{
  "total_applied": 40, "active": 20, "offered": 2, "rejected": 5, "pending_followup": 3,
  "funnel": [ { "status": "已投递", "count": 40 } ],
  "channel_dist": [ { "channel": "官网", "count": 30 } ],
  "weekly_trend": [ { "week_start": "2026-08-17", "count": 8 } ]
}
```

- total_applied = 已投递及之后状态（不含「待投递」）
- active = 已投递 ~ 三面/HR面（非终态）
- offered = 已Offer；rejected = 已拒绝 + 已放弃
- pending_followup = 进行中且距上次流转 >3 天
- funnel 从「已投递」起、不含「待投递」；weekly_trend 近 4 周按 applied_at（周一为周起点）

---

## 数据来源与扩展（自动补全）

- **内置映射表** `backend/app/fetcher/company_map_data.json`（233 家）：101 家手工精选（主流大厂/国企/外企，含官网/招聘站/行业/城市/性质）+ guoyang-pro 央企国企名录 132 家（`https://github.com/HA7CH/guoyang-pro`，MIT；按监管单位判央企/国企，行业按 sector 映射，招聘站取自 recruit_site，官网留空由搜索补全）。合并脚本：`backend/scripts/merge_roster.py`（幂等，可重跑）。
- **A股上市公司离线库** `backend/app/fetcher/company_info_data.json`（约 5000 家，巨潮资讯 cninfo 经 akshare 导出）：官网/行业/注册城市。构建脚本：`backend/scripts/build_akshare_company_db.py`（断点续跑），重跑命令：`cd backend && python scripts/build_akshare_company_db.py`。
- **ICP 备案反查（可选）**：公司全称 → 官方域名，权威覆盖非上市中小企业。部署 HG-ha/ICP_Query（`https://github.com/HG-ha/ICP_Query`，Python/Docker 一键，见 `backend/scripts/icp_query/`），并设置环境变量 `ICP_API_URL`（如 `http://127.0.0.1:16181`）；模块查询路径为 `{ICP_API_URL}/query/web?search=公司名`，响应按「域名嗅探」解析（兼容 MIIT 字段变化）。未配置/服务不可达时自动跳过（走 Bing 兜底），结果缓存 90 天。注意：该项目未声明 LICENSE（仅供学习自用）；工信部平台对数据中心/境外 IP 常返回 521 拦截，被屏蔽时需在服务配置里启用代理。
