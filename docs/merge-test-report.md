# 「秋招投递助手 + 市场情报」合并项目 上线前全量回归测试报告

- 报告日期：2026-08-25
- 测试执行人：测试工程师
- 回归范围：A（投递管理）+ B（市场情报，原 JobPulse）合并为单进程应用后的全量回归
- 被测版本：backend `run.py`（A 的 `app/` + B 迁入的 `market/`，共用 SQLite `data/app.db`）；frontend TS 工程 + `/market/*` 三页 + P2 协同点

---

## 一、测试环境

| 项 | 值 |
|---|---|
| 操作系统 | Windows 10 22621 x64（Git Bash） |
| 后端服务地址 | http://127.0.0.1:8000（已运行，`/api/boot` 返回 schema_version=2） |
| 后端依赖 | Python 3.13.9、FastAPI 0.115.6、uvicorn 0.34.0、SQLAlchemy 2.0.52、pandas 2.2.3、httpx 0.28.1、pytest 9.1.1 |
| 数据库 | SQLite `data/app.db`（WAL），已应用迁移 001_init、002_market_jobs |
| 市场数据 | `market_jobs` 10,114 条（其中 is_valid=1 有效 7,387 条）、`market_job_snapshots` 10,114 条 |
| 薪资模型 | `market/output/model/jobpulse_xgb.joblib` 已存在，predict 可用 |
| 前端 | Node/Vite 工程，vitest 2.1.9 |
| 测试方式 | 自动化单测（pytest / vitest）+ 真实服务接口冒烟（仅读为主 + 创建即清理） |

---

## 二、自动化测试套件结果

| 套件 | 命令 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| A 投递域单测 | `python -m pytest tests/ -q` | 61 passed | **61 passed**（5.13s） | 通过 |
| B 市场域单测（排除 live） | `python -m pytest tests_market/ -q -m "not live"` | 125 passed | **125 passed**（24.20s，26 deselected） | 通过 |
| 后端冒烟 | `python scripts/smoke.py` | 41 通过 | **41 通过 / 0 失败** | 通过 |
| 前端类型检查 | `npm run typecheck`（vue-tsc --noEmit） | 零错误 | **零错误** | 通过 |
| 前端单测 | `npm run test`（vitest run） | 53 通过 | **53 passed**（4 个 spec 文件） | 通过 |
| 前端构建 | `npm run build` | 成功 | **成功**（25.19s，仅有 chunk >500kB 体积告警，非错误） | 通过 |

说明：
- B 套件 `-m "not live"` 排除的 26 个为联网采集用例（live adapters），属预期跳过。
- 前端 `npm run test` 通过的文件：`txt.spec.ts`(10)、`date.spec.ts`(19)、`market.spec.ts`(16)、`normalize.spec.ts`(8)。

---

## 三、集成验证清单（真实服务 http://127.0.0.1:8000）

鉴权方式：`GET /api/boot` 获取 token，后续请求带 `X-Auth-Token` 头。中文参数使用 httpx `params` 自动编码或 `-d @file` JSON 文件传递，规避 Git Bash 编码问题。

### 3.1 A 域（投递管理）

| # | 验证项 | 结果 | 说明 |
|---|---|---|---|
| A1 | GET /api/boot | 通过 | 返回 token、schema_version=2、app 信息、backup 字段 |
| A2 | GET /api/jobs 列表 | 通过 | 200，`{"items":[],"total":0}` |
| A3 | POST /api/jobs 创建 | 通过 | 201，company="回归测试临时公司" 创建成功 |
| A4 | GET /api/jobs/{id} 详情 | 通过 | 200，字段完整（含 company/position/city/status 等） |
| A5 | POST /api/jobs/{id}/status 状态流转 | 通过 | 按中文状态枚举（已投递→笔试→一面→已Offer）依次 200；非法状态返回 400 VALIDATION_ERROR；applied_at/ended_at 正确落库；timeline 事件 4 条完整 |
| A6 | GET /api/jobs 筛选 | 通过 | keyword=公司名（LIKE）、status=已Offer、company 字段均正确命中；`include_ended=true` 生效 |
| A7 | POST /api/jobs/batch-delete | 通过 | 200，`{"deleted":2}` |
| A8 | DELETE /api/jobs/{id} | 通过 | 204，删除后 GET 返回 404 |
| A9 | GET /api/companies | 通过 | 200，total=146 |
| A10 | GET /api/resumes | 通过 | 200，结构正常 |
| A11 | GET /api/stats | 通过 | 200，含 total_applied/active/offered/funnel/channel_dist/weekly_trend 等口径字段 |
| A12 | GET /api/backup/export | 通过 | 200 JSON，含 schema_version=2、jobs/companies/resumes 三集合（仅确认结构，未下载大文件） |
| A13 | 测试数据清理 | 通过 | 全部测试岗位已删除，DB 中"回归测试"残留为 0 |

### 3.2 市场域（/api/market/*）

| # | 验证项 | 结果 | 说明 |
|---|---|---|---|
| M1 | GET /api/market/health | 通过 | 200，`{"status":"ok","jobs":7387,"snapshots":10114,"db":"sqlite"}` |
| M2 | GET /api/market/meta | 通过 | 200，total=7387、cities/categories/educations/sources 齐全 |
| M3 | GET /api/market/jobs 分页 | 通过 | 200，page/page_size/total_pages/items 结构正确；total=10114（含无效记录，见缺陷 D1） |
| M4 | GET /api/market/jobs 城市/类别筛选 | 通过 | city=北京&category=数据分析 → 897 条；keyword 搜索 job_id 能命中 |
| M5 | GET /api/market/jobs/summary | 通过 | 200，summary+filtered+charts(5 图表)+sources；city=上海、category=算法 筛选联动正确（filtered.total 变化） |
| M6 | POST /api/market/predict | 通过 | 中文 JSON 请求体正常；响应 `{predicted_salary_avg, salary_band, note}` 结构完整；模型已加载（非 404） |

### 3.3 安全验证

| # | 验证项 | 结果 | 说明 |
|---|---|---|---|
| S1 | 无 token 访问 /api/jobs | 通过 | 401 `UNAUTHORIZED` |
| S2 | 无 token 访问 /api/market/jobs | 通过 | 401 `UNAUTHORIZED` |
| S3 | 错误 Host 头访问 /api/jobs | 通过 | 403 `FORBIDDEN` "Host 校验失败，拒绝访问" |
| S4 | 错误 Host 头访问 /api/market/jobs | 通过 | 403 `FORBIDDEN` |
| S5 | 错误 token 访问 /api/jobs | 通过 | 401 `UNAUTHORIZED` |

### 3.4 迁移验证（002_market_jobs）

| # | 验证项 | 结果 | 说明 |
|---|---|---|---|
| T1 | schema_migrations 记录 | 通过 | `(1,'001_init.sql')`、`(2,'002_market_jobs.sql')` 均在 |
| T2 | market_jobs 表存在 | 通过 | 10,114 行，字段与模型一致（job_id/job_title/job_category/.../is_valid/source）；is_valid=1 共 7,387 |
| T3 | market_job_snapshots 表存在 | 通过 | 10,114 行 |
| T4 | A 域四表数据完好 | 通过 | jobs(0)/companies(146)/resumes(0)/job_events(0) 结构与数据完好，未受合并影响 |
| T5 | 无脏数据残留 | 通过 | 回归测试岗位全部清理（jobs 残留 0） |

### 3.5 前端打包产物

| # | 验证项 | 结果 | 说明 |
|---|---|---|---|
| F1 | dist 产物完整性 | 通过 | index.html + assets（JS/CSS 全部生成） |
| F2 | 静态加载 | 通过 | 用 http.server 托管 dist，index.html(200)/index js(200)/market 相关 js(200) 均可访问；未做真实浏览器自动化（环境限制） |

---

## 四、P2 协同点专项验证

### 4.1 市场岗位导入投递（P2b）

按前端映射规则（`src/utils/market.ts` 的 `buildMarketJobPayload` + `marketChannelOf` + `blankOrNaToNull`）模拟：

1. 取 `/api/market/jobs` 一条有效记录（job_id=`backup_10112`，company=杭州七剑网络科技，source=backup）；
2. 映射构造 POST /api/jobs：company/position/city/industry/job_type/degree→null、channel=其他、job_url、source_job_id、publish_date；
3. 创建成功（201）；
4. 用同一 source_job_id 再次导入前置查重：`GET /api/jobs?keyword=杭州七剑网络科技&include_ended=true` 返回 total=1，`source_job_id` 命中 → 前端 `duplicated=true`，二次确认逻辑成立；
5. 测试岗位已删除（204），无残留。

结论：**通过**。前端对 `company='nan'`/空值的拦截（`isBlankCompany`）逻辑正确，脏公司不会写入 A 库。

### 4.2 薪资参考（P2a）

按前端 `buildPredictRequest` 规则构造（含中文），POST /api/market/predict：

- 场景1：行业=数据分析（白名单），返回 200，`predicted_salary_avg=23418.0`，band="19,000 - 28,000 元"；
- 场景2：行业=互联网（非白名单，前端归一为"数据分析"），返回 200，`predicted_salary_avg=18010.0`；
- 响应结构均含 `predicted_salary_avg/salary_band/note` 三字段。

结论：**通过**。

---

## 五、缺陷清单

### D1【一般】/api/market/jobs 列表含无效记录，total 口径与 summary/meta 不一致

- 标题：市场岗位列表返回 is_valid=0 的无效记录，total=10114 与看板口径 7387 不一致
- 严重级别：一般（数据口径问题，不影响功能可用性）
- 复现步骤：
  1. `GET /api/market/jobs?page=1&page_size=100`（带 token）
  2. 观察 `total=10114`，翻页可检索到 `is_valid=0` 的 job（如 `backup_6`，公司 IGG，产品经理岗）
  3. 对比 `GET /api/market/jobs/summary` / `GET /api/market/meta` 的 `total=7387`
- 实际结果：`/api/market/jobs` 未过滤 `is_valid=0`（`_query_jobs` 直接 select Job 全表），列表页会展示 2,727 条无效记录，其中含 895 条（12%）公司名为 `nan`/空的脏数据；而 summary/meta 走 `fetch_jobs_for_analysis(valid_only=True)` 只统计有效记录。
- 预期结果：列表与看板口径一致，应过滤 `is_valid=1`（或在列表标注无效来源）。
- 影响：市场岗位列表总数与看板统计对不上；脏数据虽被前端导入拦截，但列表展示不友好。
- 环境：backend 合并后 `market/api/app.py::_query_jobs`（约第 53 行起）。

### D2【建议】市场看板 skill_top 图表为空

- 标题：`/api/market/jobs/summary` 的 charts.skill_top 恒为空列表
- 严重级别：建议
- 复现步骤：GET /api/market/jobs/summary → charts.skill_top = `[]`
- 原因分析：`features.parquet`（market/output/analysis/）中 `skills_hit` 列全空（7,387 行非空命中数为 0），即 NLP 技能图谱流水线未产出结果，非接口代码缺陷；当前为数据依赖问题。
- 影响：看板"技能 Top"模块无数据展示。
- 建议：上线前运行 `python -m market.cli nlp` 生成 skills_hit 后复验。

### D3【建议】市场数据质量：company='nan'/行业未标注占比较高

- 标题：market_jobs 有效记录中 12%（895/7387）公司名为 'nan' 或空、82%（6119/7387）行业为"未标注"
- 严重级别：建议
- 影响：前端已用 `isBlankCompany` 拦截脏公司导入，功能不阻断；但行业筛选/展示参考价值受限。
- 建议：ETL 阶段清理 `nan` 字符串、行业回填或标注"未标注"策略优化。

### D4【建议】前端构建产物 chunk 体积告警

- 标题：`npm run build` 存在 >500kB chunk（index js 1.15MB / EChart 546kB）
- 严重级别：建议
- 影响：非错误，首次加载体积偏大，本地应用可接受。
- 建议：后续对 ECharts 按需引入或做 manualChunks 拆分。

---

## 六、测试结论

### 验收结论：**有条件通过**

判定依据：
- 三套后端自动化全部通过（61 + 125 + 41），前端 typecheck/test/build 全部通过；
- 真实服务集成冒烟（A 域 13 项、市场域 6 项、安全 5 项、迁移 5 项）全部通过；
- P2 两个协同点（导入投递、薪资参考）接口级模拟全部通过；
- 无致命/严重缺陷；遗留问题均为一般/建议级别，不影响核心流程可用性。

有条件通过的前置条件（建议上线前处理）：
1. 修复 D1：`/api/market/jobs` 过滤 `is_valid=0`，统一列表与看板口径（一般级，影响市场列表数据可信度）；
2. 运行 NLP 流水线产出技能命中数据，使看板 skill_top 图表可用（D2，数据依赖项）；
3. 如需对外展示，建议清理市场数据中的 `nan` 公司名与"未标注"行业（D3）。

在上述条件满足（或业务方确认接受当前数据口径）后即可上线。

---

## 七、附：关键执行摘要

- 后端：`tests/` 61 passed；`tests_market/ -m "not live"` 125 passed；`scripts/smoke.py` 41 通过。
- 集成：A 域全闭环（建→查→流转→删）通过，状态机、筛选、批量删除、备份导出均正常；市场域 health/meta/jobs/summary/predict 通过；安全（401/403）通过。
- 迁移：002 已应用，market 两表存在，A 域四表完好。
- 前端：typecheck 0 错误、53 tests passed、build 成功、dist 可静态加载。
- P2：导入投递与薪资参考两条协同链路接口级模拟通过，测试数据全部清理。

---

## 八、回归后修复记录（2026-08-25）

验收后按缺陷清单与安全审查意见完成以下修复，均已复测通过：

| 编号 | 修复内容 | 验证结果 |
|---|---|---|
| D1 | `/api/market/jobs` 增加 `is_valid=1` 过滤，与 summary/meta 的 7,387 口径统一（`market/api/app.py::_query_jobs`） | 接口 total 10114 → **7387** ✅ |
| D2 | 运行 `python -m market.cli nlp` 生成技能命中数据（features.parquet 重建） | 看板 skill_top 空 → **15 条**（数据分析 32.7%/Python 30.9%/SQL 17.5%）✅ |
| 安全中危 | 移除 `market.cli api` 子命令与 `market/api/app.py` 模块级 `app`，消除绕过宿主安全中间件的独立 API 入口（仅保留测试用 `create_app`） | CLI 子命令列表已无 api；`uvicorn market.api.app:app` 不可再启动 ✅ |
| 安全低危 | 修正 `app/main.py` 中间件顺序注释（后注册者在外层，security 最先执行） | 注释与实际行为一致 ✅ |

修复后全量复测：`tests/` 61 passed、`tests_market/` 125 passed、`market/api` 10 passed、前端 typecheck/test/build 不受影响。
