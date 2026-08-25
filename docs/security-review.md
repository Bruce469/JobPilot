# 上线前安全审查报告：秋招投递助手 + 市场情报

- 审查对象：`E:\岗位投递\backend`（A 的 `app/` + B 迁入的 `market/`，单进程 FastAPI，监听 127.0.0.1:8000）
- 威胁模型：本机 127.0.0.1 单用户 + 防跨站诱导访问 / DNS rebinding + 抓取合规
- 审查方式：静态代码审查 + 运行时验证（curl，服务运行于 http://127.0.0.1:8000）
- 审查日期：2026-08-25
- 审查人：安全工程师

> 说明：本机个人工具安全基线为「防跨站诱导访问 + 防 DNS rebinding + 抓取合规」，不按公网多用户标准要求（无需 HTTPS、多租户鉴权、账户体系等）。

---

## 一、审查项清单与结论

| # | 审查项 | 结论 | 依据 |
|---|--------|------|------|
| 1 | CORS 白名单（仅 5173 dev 来源） | 通过 | `app/main.py` 使用 `config.ALLOWED_ORIGINS`（仅 `http://127.0.0.1:5173`、`http://localhost:5173`），`allow_credentials=False`；运行时验证见下 |
| 2 | Host 头校验（仅 127.0.0.1/localhost） | 通过 | `app/security.py` 对 Host 拆分端口、小写化后白名单匹配；运行时验证 evil.com/空 Host/后缀欺骗均 403 |
| 3 | token 校验中间件覆盖 `/api/market/*` | 通过 | 中间件为全局 `@app.middleware`，`market` 路由在 `include_router` 之后仍被中间件包裹；运行时验证无 token 访问 `/api/market/*` 均 401 |
| 4 | B 的 CORS 中间件已删除 | 通过 | 全仓 grep 仅 `app/main.py` 存在 `CORSMiddleware`，`market/` 无任何 CORS 引用 |
| 5 | B 无独立鉴权绕过（APIRouter 上无跳过依赖） | 通过 | `market/api/app.py` 的 `build_router()` 为无鉴权依赖的普通 `APIRouter`，鉴权完全依赖宿主 A 中间件；无 `dependencies=[]` 绕过 |
| 6 | config.yaml 无硬编码密码、driver 默认 sqlite | 通过 | 密码经 `password_env: DB_PASSWORD` 环境变量注入，`driver: sqlite`；MySQL 驱动下未配置密码会抛 ValueError 引导 |
| 7 | 抓取限速/UA/robots（market + A fetcher） | 通过（见合规说明） | market 随机 UA 池 + 2~5s 随机延时 + 3 次指数退避重试 + 403/429/验证码不重试；A fetcher 固定 UA + robots.txt 检查 + 同域 ≥1.5s / 全局 ≤30 req/min |
| 8 | 备份导入仅本机触发、无路径穿越 | 通过 | `POST /api/backup/import` 走全局 token 中间件；入参为 JSON（`BackupImportIn`），无文件路径输入，无路径穿越面；`mode` 白名单、`schema_version` 范围校验 |
| 9 | SQL 注入 | 通过 | market `_query_jobs` 全程 SQLAlchemy 参数化（`.where(==)`、`.like()` 绑定参数）；A 用标准库 `sqlite3` 参数化占位符，均无字符串拼接 SQL |
| 10 | 敏感信息/密钥硬编码 | 通过 | 全仓扫描无硬编码密码/API key；token 由 `secrets.token_hex(32)` 启动时生成，重启即失效 |

---

## 二、发现的问题

### 问题 1（中危）：`market.cli api` 调试入口绕过统一安全中间件

- **位置**：`market/cli.py` 的 `cmd_api()`（第 230~255 行）与 `market/api/app.py` 的 `create_app()`（第 262~271 行，含模块级 `app = create_app()`）
- **描述**：`python -m market.cli api` 会执行 `uvicorn.run("market.api.app:app")`，启动一个**独立** FastAPI 应用，仅挂载 `/api/market/*` 路由，**没有** A 的 Host 校验、token 校验、CORS 白名单中间件。默认虽监听 127.0.0.1:8000，但：
  - 无 Host 校验 → 无法防御 DNS rebinding（恶意域名解析到 127.0.0.1 后，浏览器视其为同源，可跨源读取岗位明细数据）；
  - 无 token 校验 → 任何本机进程/浏览器可直接读接口；
  - 无 CORS → 同源下的跨站读取不设防。
- **影响**：一旦用户（或自动化脚本）误用该入口而非 `run.py`，市场情报数据即暴露于 DNS rebinding / 跨站诱导读取，直接违反本项目「防 DNS rebinding」基线。
- **风险级别**：中危（非生产主入口 `run.py`，但属真实绕过面，且修复成本低）
- **修复建议**（二选一，推荐 A）：
  - A. 删除 `cmd_api` 及 `create_app()`（合并后统一入口只有 `run.py`，调试可临时用 `run.py` + 断点）；
  - B. 让 `create_app()` 复用 A 的防护：`app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, ...)` 并注册与 `app/security.py` 相同的 Host+token 中间件，使调试入口与生产入口同基线。

### 问题 2（低危/文档）：`app/main.py` 第 35 行中间件顺序注释与事实不符

- **描述**：注释写「CORS 白名单（先注册 → 最外层，先于 token 中间件处理预检 OPTIONS）」，但 Starlette 中间件**后注册者在外层**，实际是 `security` 中间件在最外层、CORS 在内层；功能上因 `security` 显式对 `OPTIONS` 放行才保证预检由 CORS 处理，行为正确，仅注释误导。
- **风险级别**：低（不影响安全性，仅影响维护）
- **修复建议**：将注释改为「security 中间件后注册、位于最外层；其对 OPTIONS 放行，预检交由内层 CORS 处理」。

---

## 三、运行时验证结果（http://127.0.0.1:8000）

| 用例 | 请求 | 期望 | 实测 |
|------|------|------|------|
| 无 token 访问 `/api/market/jobs` | GET | 401 | **401** ✓ |
| 无 token 访问 `/api/market/predict`（GET） | GET | 401 | **401** ✓ |
| 无 token 访问 `/api/market/predict`（POST） | POST | 401 | **401** ✓ |
| 伪造 Host `evil.com` | GET /api/boot, `Host: evil.com` | 403 | **403** ✓ |
| 伪造 Host + 合法 token 访问 market | GET /api/market/jobs, `Host: evil.com` + token | 403 | **403** ✓ |
| 空 Host | GET /api/boot, `Host:` | 403 | **403** ✓ |
| Host 后缀欺骗 | `Host: 127.0.0.1.evil.com` / `localhost.evil.com` | 403 | **403** ✓ |
| Host 端口/大小写归一 | `Host: 127.0.0.1:9999` / `LOCALHOST` | 200（放行） | **200** ✓ |
| 带 token 正常访问 | GET /api/market/jobs、/api/market/health | 200 | **200** ✓ |
| 带 token POST 预测 | POST /api/market/predict（合法体） | 200 | **200** ✓ |
| CORS 预检（恶意源） | OPTIONS + `Origin: http://evil.com` | 拒绝（无 ACAO） | **400，无 `access-control-allow-origin`** ✓ |
| CORS 预检（白名单源） | OPTIONS + `Origin: http://localhost:5173` | 200 + ACAO | **200 + ACAO** ✓ |
| 实际 GET 带恶意 Origin + token | GET /api/market/jobs, `Origin: http://evil.com` | 响应无 ACAO（浏览器不可读） | **200，但无 ACAO 头** ✓ |

结论：生产主入口 `run.py` 的「防跨站诱导访问 + 防 DNS rebinding」核心机制（token / Host 校验 / CORS 白名单）实测全部生效，`/api/market/*` 已被统一覆盖。

---

## 四、合规说明

### 4.1 抓取边界

- **A 的 fetcher（`app/fetcher/http.py`）**：固定 UA `JobHunter/1.0 (personal-use job tracker; +local)`；单请求超时 <10s；经 `rate_limiter`（同域 ≥1.5s、全局 ≤30 req/min）；抓取前执行 `robots.txt` 检查（拿不到 robots 视为允许）。行为与原架构 5.5 一致，维持原限速。
- **B 的 market crawler（`market/crawler/`）**：随机 UA 池；请求前随机延时 2~5s；重试 3 次、指数退避；`403/429/验证码/封禁/WAF` 识别后**不重试并立即停止该源告警**（`NO_RETRY_STATUS` + `NO_RETRY_MARKERS`）。
  - 实时源 `iguopin`（国聘 gp-api）与 `nowcoder`（牛客 nowpick）为**公开免登录 JSON 接口**，非 HTML 页面爬取，故未做 robots.txt（robots.txt 针对页面爬虫，对公开 API 不适用）；适配器注释明确「仅低频拉取公开职位列表，不逆向、不绕过验证码」。频率上每关键词 2~5s 延时 + 单关键词最多 3~5 页，符合限速要求。
  - `job51` 源已因 WAF 验证不可用，`adapter_factory` 保留接口但 `pipeline.run_crawl` 直接标记不可用不发起请求。

### 4.2 兜底数据集授权

- 兜底数据集 `market/data/raw/job_posting_data.xlsx` 来源为 GitHub `Rayair019/Job-posting-data`，**无开源许可证**。`config.yaml` 已标注「文件需自行放置」，代码未二次分发数据本身。
- 合规结论：仅个人本地学习/分析使用、不二次分发，符合「个人学习、不二次分发」的既定边界；**若未来对外分发或商用，须先取得该数据集明确授权或更换为有许可证的数据集**。

### 4.3 个人信息

- 应用为纯本机单用户工具，简历/投递数据存于本机 `data/app.db`（WAL），不上传第三方；无对外数据共享面。本机工具不涉及对外个人信息处理告知义务；对外分发前需另行评估。

---

## 五、放行结论

**结论：有条件放行。**

- 生产主入口（`python run.py`）的认证授权、Host 校验、CORS 白名单、抓取限速/robots 合规均通过静态与运行时双重验证，`/api/market/*` 已被统一安全中间件覆盖，未发现高危漏洞。
- **放行条件（建议限期关闭）**：修复「问题 1」——删除或加固 `market.cli api` 调试入口，消除其对 Host/token/CORS 防护的绕过（该入口为唯一直接违反「防 DNS rebinding」基线的绕过面）。
- 问题 2（注释误导）建议随下次提交一并修正，不阻塞放行。
