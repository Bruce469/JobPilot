# JobPilot · 秋招投递与市场情报平台

> 一个跑在个人电脑上的秋招全流程工具：**投递管理**（自己的岗位进度、简历、公司库）与 **市场情报**（数据岗位市场行情、薪资预测）合二为一。
> 前者是「管好自己的一亩三分地」，后者是「看清大盘再出手」，两者通过「市场岗位一键导入投递」和「录入岗位时参考市场薪资区间」打通闭环。

![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Vue](https://img.shields.io/badge/Vue-3.5-brightgreen)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178c6)
![SQLite](https://img.shields.io/badge/SQLite-WAL-orange)
![XGBoost R²](https://img.shields.io/badge/薪资模型%20R%C2%B2-0.5144-success)
![数据](https://img.shields.io/badge/市场数据-10%2C114%20条-blue)
![测试](https://img.shields.io/badge/自动化测试-249%20passed-brightgreen)

---

## 目录

- [功能总览](#功能总览)
  - [投递管理（JobPilot 宿主）](#投递管理jobpilot-宿主)
  - [市场情报（原 JobPulse 数据科学全流程项目）](#市场情报原-jobpulse-数据科学全流程项目)
  - [两大域的协同能力](#两大域的协同能力)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [技术难点与解决方法](#技术难点与解决方法) ⭐
- [项目成果](#项目成果)
- [快速开始](#快速开始)
- [API 一览](#api-一览)
- [目录结构](#目录结构)
- [测试](#测试)
- [Roadmap 与已知限制](#roadmap-与已知限制)
- [数据源与合规声明](#数据源与合规声明)

---

## 功能总览

### 投递管理（JobPilot 宿主）

Vue 3 + TypeScript + FastAPI + SQLite，所有业务数据 100% 存本机，不经过任何第三方。

| 模块 | 能力 |
|---|---|
| **岗位看板** | 10 状态流转看板（待投递 → 已投递 → 简历筛选 → 笔试 → 一面/二面/三面·HR面 → 已Offer/已拒绝/已放弃），跨列拖拽流转；每次流转自动写入时间线事件；终态默认收起 |
| **岗位列表** | 关键词搜索 + 状态/城市/行业/渠道多条件组合筛选、列排序、批量删除、行内流转；笔试/面试时间过期标红提醒；「今日/本周安排」「即将截止 ≤3 天」聚合 |
| **简历管理** | 多份简历 CRUD（结构化区块：基本信息/教育/实习/项目/技能/自我评价）；A4 版式渲染 + `window.print()` 打印/另存 PDF；岗位绑定简历版本（名称快照冻结）；删除被引用简历有引用计数保护 |
| **公司库** | txt 批量导入；输入公司名自动补全官网/招聘页/行业（四级数据流水线，见[难点 6](#难点-6公司名--官网自动补全的低误配率四级数据流水线)）；官网招聘页自动探测 + 一键抓取岗位并去重导入 |
| **统计** | 总投递/进行中/已Offer/已拒绝/待跟进卡片 + 漏斗图/渠道分布/近 4 周趋势（指标口径定义于 PRD） |
| **备份** | JSON 全量导出导入（merge 以本机为准 / overwrite 二次确认全替），schema_version 校验防版本错乱；距上次备份 >7 天启动提醒 |

### 市场情报（原 JobPulse 数据科学全流程项目）

爬取真实招聘数据 → 清洗建库 → 分析规律 → 预测薪资 → 可视化看板的数据科学全流程。

| 环节 | 实现 |
|---|---|
| **数据采集** | adapter 可插拔多数据源：国聘网 / 牛客网公开接口（低频实时拉取）+ GitHub 开源数据集兜底（10,114 条中国数据科学岗位，清洗后有效 7,387 条）；断点续爬 checkpoint、指数退避重试、采集健康监控 |
| **数据存储** | SQLAlchemy 2.x ORM：`market_jobs`（最新状态）+ `market_job_snapshots`（按批次快照，为时间趋势分析预留），幂等增量写入 |
| **ETL 清洗** | 薪资归一化纯函数（9 条规则）、城市/学历/经验/规模/行业枚举归一化、数据质量报告量化脏数据比例 |
| **EDA 分析** | matplotlib 8 图（分布/对比/热力图）+ 6 条量化洞察 |
| **文本挖掘** | jieba 分词 + 自定义词典 + 89 个技能词表 → 技能 Top15（数据分析 32.7%、Python 30.9%、SQL 17.5%…）、城市/类别技能差异对比、中文词云、建模特征输出（features.parquet） |
| **薪资预测** | XGBoost 回归 + log 目标变换 + 标题/JD 文本特征，测试集 **R² = 0.5144**，提供在线预测接口 |
| **可视化** | ECharts 交互看板：薪资分布 / 城市对比 / 技能 Top15 / 岗位量占比 / 城市×类别热力图，城市+类别+学历+数据源多维联动筛选；另有单 HTML 版本（数据内嵌，双击即开） |

### 两大域的协同能力

1. **发现 → 跟踪闭环**：市场岗位库里看到感兴趣的岗位，一键映射字段后导入投递列表开始跟踪（`source_job_id` 查重防止重复导入，脏公司名在源头拦截）。
2. **决策辅助**：手动录入岗位时，可一键将公司/岗位参数发给薪资模型，参考「预测月薪 + 常见薪资区间」填写期望薪资。

---

## 系统架构

单进程单库设计——两个业务域共用一个 FastAPI 进程和一个 SQLite 文件：

```
┌────────────────────────── 浏览器（127.0.0.1:5173） ──────────────────────────┐
│  前端 SPA（Vite + Vue 3 + TS + Pinia + Element Plus + ECharts）              │
│  ├─ 页面：看板 / 列表 / 公司库 / 简历×3 / 统计 / 设置 + 市场看板/岗位库/预测    │
│  ├─ Pinia store：jobs / companies / resumes / app / ui                       │
│  └─ axios 封装：X-Auth-Token 自动注入，401 自动重新 boot 重试                  │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │ HTTP（JSON REST，Vite proxy /api → 8000）
┌──────────────────────────────▼───────────────────────────────────────────────┐
│  后端（FastAPI 单进程，uvicorn 仅绑 127.0.0.1:8000）                           │
│  ├─ 安全中间件链：Host 头校验 → token 校验（CORS 白名单内层处理预检）           │
│  ├─ 投递域 app/：jobs / resumes / companies / tasks / backup / stats          │
│  │    └─ fetcher/：probe 探测分层 → ATS 适配器(Greenhouse/Lever/飞书) →        │
│  │       JSON-LD 兜底｜限速器｜内存任务表+后台线程｜公司补全四级流水线           │
│  ├─ 市场域 market/：crawl(adapter) → etl → analyze/nlp → model(XGBoost)       │
│  │    └─ APIRouter：health / jobs / summary / meta / predict                   │
│  └─ DAO 层：sqlite3 标准库参数化 SQL（投递域）+ SQLAlchemy 2.x（市场域）        │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │ WAL 模式
                        ┌──────▼──────┐
                        │ SQLite 文件  │ data/app.db（迁移脚本 schema_migrations 管理）
                        └─────────────┘
```

设计总原则：**个人工具、够用可靠、避免过度设计**——刻意不引入消息队列、重型 ORM（投递域）、容器编排、无头浏览器和第三方服务。每项技术选型都有 ADR 记录选入理由与被否决方案（见 `docs/architecture.md`）。

---

## 技术栈

**前端**

| 层 | 技术 | 说明 |
|---|---|---|
| 框架 | Vue 3.5 + TypeScript 5.6 | 组合式 API，全仓类型安全（vue-tsc 零错误） |
| 构建 | Vite 5 | dev proxy `/api` → 后端，规避 CORS |
| 状态/路由 | Pinia / Vue Router 4 | store 按资源域划分 |
| UI | Element Plus + 自研组件 | 看板列/卡片/时间线/A4 简历渲染等自绘 |
| 图表 | ECharts 5（按需引入） | 统计页 + 市场看板 |
| 拖拽 | vuedraggable (SortableJS) | 跨列拖拽流转 |
| 测试 | Vitest | 纯函数单测（日期/归一化/txt 解析/市场映射） |

**后端**

| 层 | 技术 | 说明 |
|---|---|---|
| 框架 | FastAPI + Pydantic v2 | 请求/响应 schema 单一事实源，统一错误结构 |
| 存储 | SQLite (WAL) | 投递域用标准库 `sqlite3` 参数化 SQL + 编号迁移脚本；市场域用 SQLAlchemy 2.x ORM |
| 抓取 | httpx + BeautifulSoup4 | 固定 UA、10s 超时、限速器令牌桶 |
| 异步任务 | 内存任务表 + threading 后台线程 | HTTP 202 + 前端轮询，替代 Celery/Redis |
| 数据科学 | pandas / numpy / XGBoost / scikit-learn | ETL、特征工程、薪资建模 |
| NLP | jieba + wordcloud + 自定义词典/停用词/89 技能词表 | 中文 JD 技能抽取 |
| 可视化(离线) | matplotlib + ECharts 单 HTML | EDA 出图 + 双击即开看板 |

---

## 技术难点与解决方法

> 以下均来自开发过程中的真实踩坑，按域归类。更详细的评审记录见 `docs/review.md`、`docs/security-review.md`、`docs/test-report.md`、`docs/merge-test-report.md`。

### 难点 1：不引入无头浏览器的前提下抓取官网招聘页

**问题**：目标页面千差万别——Greenhouse/Lever 托管的站点结构各异，国内大量招聘站（如飞书招聘）是 JS 渲染 SPA，静态 HTML 里根本没有岗位列表。

**解决**：
- 抽象 `ATSAdapter` 协议（`detect()` + `extract_jobs()`），实现注册表机制，新增 ATS 只加一个类、业务层零改动；
- Greenhouse/Lever 绕过 HTML 直接调其公开 board API（JSON 稳定字段），HTML 解析只做失败回退；
- 飞书这类无公开 API 的 SPA，抓取 HTML 后从 `__NEXT_DATA__` / `window.__INITIAL_STATE__` 等常见注入点提取内嵌 JSON，多注入点依次尝试；
- 通用兜底解析器解析 `<script type="application/ld+json">` 中 `@type=JobPosting` 的结构化数据，覆盖未来大量采用 SEO 结构化标注的官网；
- 全链路失败的降级路径是一等公民：任务标记失败原因（而非静默空结果），前端提示「保留链接+手动录入」。整体用本地 mock 招聘站做了探测/抓取/导入/降级四条路径的端到端验收。

### 难点 2：爬虫合规与反爬的现实边界

**问题**：主爬源 51job 全端点实测被阿里云 WAF 深度保护（JS 挑战）；直接硬刚既不可行也不合规。

**解决**：明确「不逆向、不绕过验证码/WAF」的项目边界：
- 51job adapter 保留骨架但实测结论记录在案，pipeline 直接标记该源不可用、不再发起请求；转向接入**公开免登录 JSON 接口**的国聘网/牛客网作为实时源，再以开源数据集兜底——最终数据规模不受影响；
- 公司官网抓取：请求前检查 robots.txt，Disallow 即停止并把公司标记「需人工」（有专门的单测验证此降级路径）；
- 双层限速器：全局令牌桶 ≤30 req/min + 同域名间隔 ≥1.5s，串行工作线程天然低并发；
- market 爬虫随机 UA 池 + 2~5s 随机延时 + 3 次指数退避，识别到 403/429/验证码/封禁标记后**不重试**、立即熔断告警。

### 难点 3：秒级～几十秒的抓取任务不能卡死 UI

**问题**：探测+抓取耗时远超一次正常 HTTP 请求的合理时长，同步接口会阻塞前后端交互；个人工具又扛不起 Celery + Redis broker 的重依赖。

**解决**：进程内的轻量异步方案——内存任务表（`dict + Lock`）+ 单个后台守护线程串行消费队列；提交接口立即返回 202 + `job_id`，前端每 1~2s 轮询进度直到 done/failed；任务超时（60s）强制置败并提示手动录入；保留最近 N 条防止内存增长。单用户场景下串行执行等价于天然限速，且重启丢任务可接受（操作本身幂等，重试即可）。

### 难点 4：Starlette 中间件的注册顺序陷阱

**问题**：集成测试发现「CORS 白名单先注册」的注释与实际行为不符——带合法 Origin 但不带 token 的预检请求被 401 拦截而不是由 CORS 放行。根因是 Starlette 的 `add_middleware` 采用头插法，**后注册的在最外层**，实际 security 中间件包住了 CORS。

**解决**：security 中间件对 `OPTIONS` 预检请求显式放行（预检仍受 Host 校验保护），交给内层 CORS 处理；修正误导性注释，并将「恶意 Host 403 / 无 token 401 / 白名单 Origin 预检返回 ACAO」全部固化为冒烟断言防回归。这个坑的价值在于：注释会撒谎，只有运行时断言不会。

### 难点 5：无登录体系下的安全信任边界

**问题**：纯本机工具不想引入登录，但仍要防御两类攻击——浏览器被恶意页面诱导访问本机服务（跨站诱导读取），以及 DNS rebinding（恶意域名解析到 127.0.0.1 绕过同源策略）。

**解决**（最小信任边界三件套，均经运行时验证）：
- uvicorn 仅绑定 127.0.0.1，不暴露公网；
- Host 头白名单校验中间件：`evil.com`、空 Host、`127.0.0.1.evil.com` 后缀欺骗一律 403（实测拒绝，端口/大小写归一放行）；
- 启动时 `secrets.token_hex(32)` 生成一次性 token 经 `/api/boot` 下发，后续请求校验 `X-Auth-Token`；配合 CORS 白名单（仅 dev 来源）。
- 上线前安全审查还揪出一个中危问题：`market.cli api` 调试入口能绕过宿主全部安全中间件独立起服——已删除该入口和模块级 `app` 实例，消除了唯一的防护绕过面。教训：**每一个独立的 uvicorn 入口都是一条独立的攻击面**。

### 难点 6：公司名 → 官网自动补全的低误配率（四级数据流水线）

**问题**：「按公司名自动找到它的官网和招聘页」听起来简单，实际极易误配——Bing 对长中文公司名的搜索结果高度碎片化，搜索引擎/知乎/CSDN/企查查/Boss直聘……几乎任何结果页都"包含"公司名，采信第一个结果就会张冠李戴。

**解决**：设计从权威到兜底的四级流水线，逐级降级：
1. **内置映射表**（233 家常用公司含中英文别名，归一化匹配）——命中即毫秒级返回；
2. **A股上市公司离线库**（5,448 家，经 akshare 从巨潮资讯构建，含全称/曾用简称别名，支持断点续跑增量构建）；
3. **ICP 备案反查**（Docker 自部署开源服务，公司全称→工信部备案域名权威映射，内置滑块验证码自动识别；查询结果缓存进 SQLite 90 天降低对备案平台的压力）；
4. **Bing 搜索兜底**——域名黑名单（100+ 域名覆盖搜索引擎/内容平台/工商查询/招聘站/B2B/政府高校域名）过滤自然结果后，仍须校验候选首页标题或正文包含公司名核心串才采信，行业从标题/摘要推断；
   - 全部失败则返回 failed 不写任何字段，批量导入场景下留待人工。
   - resolve 层完整复用了限速器，保证流水线自身也守规矩。

### 难点 7：招聘平台上薪资文本的脏乱差

**问题**：原始数据的薪资字段五花八门：「面议」「15-25K·14薪」「200-400元/天」「2万-3万」「15000以上」，单位混杂（k/万/元）、周期混杂（月/天/年），无法直接用于统计与建模。

**解决**：沉淀为 **9 条规则的薪资归一化纯函数**：区间取中位数、实习日薪 ×20 折算月薪、k/万 单位换算、「·14薪」年度薪折月、异常值检测剔除面议等。关键是做成无副作用纯函数——9 条规则全部有针对性单测，坏例子随 bug 永久进入测试集。清洗前后的质量差异固化为机器可读的数据质量报告（量化 nan 公司名占比、行业未标注占比），让「数据有多脏」成为可度量事实。

### 难点 8：小样本中文岗位文本上把 R² 做 ≥0.50

**问题**：仅约 7,200 条可用样本，主要信号却藏在非结构化的中文岗位标题/JD 文本里，线性回归基线只有 R² ≈ 0.34~0.47。

**解决**：
- 目标变量 log 变换，缓解薪资右偏长尾导致的平方损失失衡；
- jieba 分词 + 自定义词典 + 89 技能词表把 JD 文本结构化为技能命中特征；从岗位标题提取资历级别词（senior/ml/sci 等）独热特征；
- 行业/城市类别特征按城类别 8:2 分层划分 + 固定种子，保证对比可复现；
- 最终 XGBoost 达到 **R² = 0.5144 / MAE = 8,733 元**，显著优于线性回归基线（0.4652）与均值基线（≈0）。
- 同样重要的是诚实报告局限：特征重要性第一名是「行业未标注」（占 82% 的缺失桶），说明还有信息没挖干净；这决定了后续优化方向（行业回填）而不是继续堆树模型超参。

### 难点 9：两个独立项目合并成单进程单库应用

**问题**：投递助手（原生 sqlite3 + 自建 DAO）与 JobPulse（SQLAlchemy + MySQL/SQLite 双驱动）技术形态完全不同，要合并成一个用户只有一个数据库文件的应用，还不能破坏彼此的数据与安全模型。

**解决**：
- 收敛为**编号 SQL 迁移 + schema_migrations 表**的单一演进体系（001 建投递域四表、002 追加市场域两表、003/004 迭代增强），禁止修改已发布脚本；备份 JSON 带 `schema_version`，导入时高版本拒绝、低版本兼容；
- market 以普通 `APIRouter` 挂载进宿主应用，鉴权完全复用宿主中间件（并专门验证 `/api/market/*` 在无 token 时确实被 401 覆盖），同时删除 B 原 CORS 配置与独立 API 入口；
- 协同点走显式契约：市场岗位导入经过字段映射 + 查重 + 空值拦截三层转换，保证「脏的市场数据」永不污染「干净的投递库」。
- 合并后做了全量回归（见成果），而非假设"挂上去就能跑"。

### 难点 10：SQLite 的并发与可靠性细节

**问题**：后台抓取线程与请求线程会同时读写同一个文件库，埋着锁冲突和数据损坏风险。

**解决**：`PRAGMA journal_mode=WAL`（读写互不阻塞）+ `foreign_keys=ON` + `busy_timeout=5000`；DAO 层提供连接工厂、每操作短连接（`with closing(conn)`），线程间绝不共享连接；时间线事件拆独立表（而非 JSON 列）换取索引检索能力（ADR-2）。此外全库备份以 JSON 导出为主 WAL 为辅，启动 >7 天未备份主动提醒。

---

## 项目成果

### 质量验证（合并上线前全量回归，2026-08）

| 套件 | 结果 |
|---|---|
| 投递域 pytest | **61 passed** |
| 市场域 pytest（联网用例默认跳过） | **125 passed** |
| market/api pytest | **10 passed** |
| 后端冒烟（临时 DB + 全端点断言 + 安全用例） | **41 通过 / 0 失败** |
| 前端类型检查 vue-tsc | 零错误 |
| 前端 Vitest | **53 passed** |
| 前端生产构建 | 成功 |

真实服务集成冒烟：A 域 13 项（创建→查→流转→删全闭环）、市场域 6 项、安全 5 项（401/403）、迁移 5 项、协同点 2 项全部通过。两轮上线前评审（功能 + 安全）发现的缺陷（updated_at 不刷新、市场列表口径不一致、独立 API 入口绕过安全中间件等）均已修复并复测，过程完整记录在 `docs/test-report.md`、`docs/merge-test-report.md`、`docs/security-review.md`——包括每个缺陷的根因分析与回归方式。

### 数据与模型成果

- **市场数据规模**：10,114 条中国数据科学类岗位入库，清洗后有效 7,387 条，覆盖 10 城 × 5 类岗位 × 多数据源；
- **薪资预测模型**：XGBoost 测试集 R² = **0.5144**（达标线 0.50），MAE = 8,733 元，RMSE = 12,508 元；优于线性回归基线 R² = 0.4652；建模集 7,210 条、8:2 城市×类别分层划分、固定种子可一键复现；
- **市场洞察节选**（全部详见生成的分析报告）：
  - 北京岗位最集中：3,270 条有效岗，占 44.3%；
  - 城市薪资差距明显：上海月薪中位数 25,000 元 vs 西安 11,375 元（2.2 倍）；
  - 大数据岗薪资中位数 22,500 元，高于数据科学岗 41%；硕士学历溢价 24%；算法类实习月薪中位数 24,000 元；
- **技能 Top3 命中率**：数据分析 32.7% / Python 30.9% / SQL 17.5%（基于 89 词表全量 JD 命中统计）；
- **公司库离线资产**：233 家手维护映射 + 5,448 家 A股公司离线库，让高频公司补全零网络开销。

### 工程化产出

- 完整文档链：PRD → 架构设计（含 ADR）→ API 契约 → 两轮评审/安全审查 → 两份测试报告，需求到验收全程可追溯；
- 一键流水线 CLI：`crawl → etl → analyze → nlp → model → viz → report` 分步可控，亦可一键全链路；
- 断点续爬、幂等导入、schema_version 化备份恢复等让日常运维接近零负担。

---

## 快速开始

环境要求：Python ≥ 3.11（开发环境 3.13）、Node.js ≥ 18（开发环境 22）。

```bash
# 1. 后端（默认 127.0.0.1:8000，端口被占自动换随机端口）
cd backend
pip install -r requirements.txt -r requirements-market.txt   # 基础依赖 + 市场看板运行依赖
python run.py

# 2. 前端（dev server，/api 自动代理到后端）
cd frontend
npm install
npm run dev            # 打开 http://127.0.0.1:5173
```

可选：启用市场情报完整数据集与薪资模型（ML 依赖较重，按需安装）：

```bash
pip install -r requirements-ml.txt
# 将数据集放置至 backend/market/data/raw/job_posting_data.xlsx
python -m market.cli crawl --source backup   # 导入 10,114 条兜底数据集
python -m market.cli etl && python -m market.cli analyze && python -m market.cli nlp && python -m market.cli model
```

常用命令速查：

```bash
python run.py --port 9000                # 后端指定端口（或 APP_PORT 环境变量）
cd backend && python scripts/smoke.py    # 冒烟测试（临时 DB，不动真实数据）
python -m pytest tests_market/ -q -m "not live"   # 市场域单测（排除联网用例）
ICP_API_URL=http://127.0.0.1:16181 python run.py  # 启用 ICP 备案反查补全层（可选）
```

---

## API 一览

除 `GET /api/boot` 外，所有接口需要 `X-Auth-Token` 头；错误统一返回 `{"error": {code, message, details}}`。完整契约见 `docs/api.md`。

**投递管理**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/boot` | 下发随机 token、schema_version、备份提醒 |
| GET/POST | `/api/jobs` | 岗位列表（多维筛选/排序）/ 创建 |
| GET/PUT/DELETE | `/api/jobs/{id}` | 详情（含时间线）/ 更新 / 删除 |
| POST | `/api/jobs/batch-delete` · `/api/jobs/import` | 批量删除 / 抓取结果去重导入 |
| POST | `/api/jobs/{id}/status` | 状态流转（事务写 job_events，终态管理 ended_at） |
| GET/POST | `/api/resumes` 及 `/api/resumes/{id}` | 简历 CRUD（删除引用保护 `referenced_by`） |
| GET/POST | `/api/companies` · `/api/companies/import` · `/api/companies/resolve` | 公司 CRUD / txt 批量导入 / 名称自动补全（四级流水线） |
| POST | `/api/companies/{id}/probe` · `/fetch` | 异步探测招聘入口 / 抓取岗位 |
| GET | `/api/tasks/{job_id}` | 异步任务轮询 |
| GET/POST | `/api/backup/export` · `/import` | JSON 全量备份 / merge/overwrite 恢复 |
| GET | `/api/stats` | 投递漏斗/渠道/趋势统计 |

**市场情报（`/api/market/*`）**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/market/health` | 健康检查（表计数 + DB 驱动） |
| GET | `/api/market/jobs` | 岗位明细分页（筛选/搜索/排序） |
| GET | `/api/market/jobs/summary` | 看板聚合（summary + 5 图表模块，多维筛选联动） |
| GET | `/api/market/meta` | 筛选项元数据 |
| POST | `/api/market/predict` | XGBoost 薪资在线预测 |

---

## 目录结构

```
backend/
├── app/                    # 投递域（宿主）
│   ├── main.py             # FastAPI 应用 + 安全中间件链
│   ├── routes/schemas/services/dao/db/errors/config
│   └── fetcher/            # probe 探测 / ATS 适配器 / 限速器 / 任务队列
│       ├── ats/            # greenhouse / lever / feishu / jsonld 兜底
│       ├── icp.py resolve.py company_map*.json company_info_data.json   # 四级补全流水线
│       └── normalize.py rate_limiter.py tasks.py http.py
├── market/                 # 市场域（原 JobPulse）
│   ├── crawler/            # iguopin / nowcoder / backup adapters + checkpoint + 监控
│   ├── etl/ analysis/ nlp/ model/ viz/ storage/ scheduler/
│   ├── api/                # /api/market/* router
│   └── cli.py              # crawl/etl/analyze/nlp/model/viz/report 一键流水线
├── migrations/             # 编号 SQL 迁移（schema_migrations 表管理）
├── scripts/smoke.py        # 41 项冒烟断言
└── tests/ tests_market/    # 61 + 125 项单测
frontend/src/
├── views/                  # 看板/列表/公司库/简历×3/统计/设置 + 市场×3
├── components/             # KanbanColumn/JobCard/TimelinePanel/ResumeRenderer(A4)/...
├── stores/ api/ types/ utils/ composables/
docs/
├── prd.md architecture.md api.md
├── review.md security-review.md test-report.md merge-test-report.md
└── market/                 # JobPulse 需求与说明文档
```

---

## 测试

```bash
cd backend
python -m pytest tests/ -q                          # 投递域单测
python -m pytest tests_market/ -q -m "not live"     # 市场域单测（跳过联网用例）
python scripts/smoke.py                             # 端到端冒烟（临时 DB + 随机端口）

cd ../frontend
npm run typecheck && npm test && npm run build      # 类型检查 / 单测 / 构建
```

测试策略上的几个值得说的选择：
- 抓取逻辑用**本地 mock 招聘站**做端到端验收（含 robots Disallow 降级、0 结果降级路径），不对真实站点做高频回归；
- 薪资归一化等易碎函数以纯函数形式沉淀「坏例子即测试用例」；
- 每次评审发现的缺陷修复都补充了对应断言（如 PUT 刷新 updated_at、Host 校验矩阵）。

---

## Roadmap 与已知限制

**已完成**
- [x] M1 投递管理全功能（看板/列表/简历/公司库/统计/备份）
- [x] 市场情报全链路（采集→清洗→分析→NLP→建模→看板）+ 前后端分离版
- [x] 双域合并单进程 + 协同能力（市场导入投递 / 薪资参考）
- [x] 上线前功能/安全双评审及缺陷修复闭环

**规划中**
- [ ] 时间趋势图：快照表就绪，积累 ≥2 个采集批次后启用
- [ ] 抓取适配扩展：北森 / Moka / 大易 ATS 适配器（注册表机制已预留扩展点）
- [ ] 备注/面经界面与浏览器通知（数据结构已定）
- [ ] ECharts 按需分包（当前首包 ~1.1MB，本地应用可接受）
- [ ] 部署服务器时的真实鉴权升级（架构已预留：鉴权集中于中间件一处）

**已知限制**
- 简历打印分页效果因浏览器而异（Chromium 系最佳，属 PRD 明确接受范围）;
- 飞书等 JS 强渲染站点解析成功率不稳定，失败自动降级手动录入;
- 市场数据集中部分行业为「未标注」、少量公司名缺失（已在数据质量报告中量化）。

---

## 数据源与合规声明

- **实时源**：国聘网、牛客网公开免登录 JSON 接口，仅低频拉取公开职位列表（随机延时 2~5s、限量翻页），不逆向、不绕过任何验证机制；
- **公司官网抓取**：遵守 robots.txt（Disallow 即放弃），固定 UA 标识、串行低频访问，仅访问公开招聘页；
- **兜底数据集**：GitHub 开源仓库 `Rayair019/Job-posting-data`（2025 年 BOSS直聘/智联/猎聘数据科学岗位文本）。该数据集无明确许可证，本项目仅作个人学习展示、**不二次分发数据文件**（需自行下载放置），商用请自行评估或替换；
- **隐私**：简历等敏感材料仅存本机 SQLite，无遥测、无第三方统计脚本，备份导出仅在用户主动触发时生成。

## License

[MIT](LICENSE)。所引用的开源数据集与第三方服务版权归各自作者所有（ICP 反查服务仅学习交流用途）。
