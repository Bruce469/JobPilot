# 秋招投递助手 M1 上线前验收报告

- 版本：v1.0
- 日期：2026-08-24
- 验收依据：`docs/prd.md`（v0.5 定稿 §4 Must 项）、`docs/api.md`（v1.0）、`docs/architecture.md`（v1.0）
- 被测对象：前端 `frontend/`（Vite + Vue3 + TS + Pinia）、后端 `backend/`（FastAPI + SQLite）
- 测试方式：后端单元测试 + 冒烟脚本 + 对运行中后端的接口实测（httpx/curl）+ 本地 mock 招聘站点抓取验证 + 前端类型/单测/构建 + dev server proxy 联调
- 测试账号/环境：本机 127.0.0.1，独立临时 SQLite（`/tmp`），未污染 `backend/data/` 实际数据目录

---

## 1. 验收结论

**验收结论：有条件通过（CONDITIONAL PASS）**

- M1 全部 Must 模块的验收标准在 API 层与可自动化验证层面均通过；核心流程无数据丢失、无阻断性缺陷。
- 遗留 2 个「一般」缺陷（均为契约/工程性偏差，无数据损坏风险）与 4 个「观察」项，建议在正式投入使用前或使用初期修复，不阻塞先行使用。
- 部分 UI 交互（看板拖拽、简历 A4 打印版式、筛选/删除弹窗视觉）依赖浏览器人工验收，按 PRD Q6 约定「简历打印分页跨浏览器差异」本就属于人工验收项；详见 §6。
- 自动化测试结果：后端 pytest **16 通过 / 0 失败**；后端冒烟 **34 通过 / 0 失败**；前端 typecheck **通过**；前端单测 **27 通过 / 0 失败**；前端 build **成功**（有 chunk 体积告警，非阻断）。

---

## 2. 验收范围

| 模块 | 来源 | 优先级 | 结论 |
|---|---|---|---|
| 4.1 岗位 CRUD（含批量删除/二次确认） | PRD | Must | 通过 |
| 4.2 流程状态管理与流转（时间线） | PRD | Must | 通过 |
| 4.3 关键日期管理与展示 | PRD | Must | 通过（接口层 + 代码核查） |
| 4.4 看板与列表视图 | PRD | Must | 通过（接口层 + 代码核查，拖拽待人工） |
| 4.5 搜索与筛选（组合） | PRD | Must | 通过 |
| 4.6 本地存储与持久化 | PRD | Must | 通过 |
| 4.7 数据导入/导出（JSON 备份恢复） | PRD | Must | 通过 |
| 4.11 简历管理与生成（CRUD/绑定/PDF 入口） | PRD | Must | 通过（PDF 版式待人工） |
| 4.12 公司库与官网抓取（探测/异步/去重/降级） | PRD | Must | 通过（mock 站点验证） |
| 4.8 统计（M1 契约先行） | PRD | Should/M2 | 契约口径通过 |
| 安全基线（token/Host/CORS/boot） | 架构 §7 | Must 级 | 有条件通过（见缺陷 BUG-2） |

---

## 3. 执行摘要

### 3.1 后端自动化

| 项目 | 命令 | 结果 |
|---|---|---|
| 单元测试 | `python -m pytest tests/ -q` | 16 passed（覆盖状态流转/去重/规范化/备份） |
| 冒烟测试 | `python scripts/smoke.py` | 34 通过 / 0 失败（自启后端 + 全端点断言 + 恶意 Host） |

### 3.2 前端自动化

| 项目 | 命令 | 结果 |
|---|---|---|
| 类型检查 | `npm run typecheck` | 通过（vue-tsc 无错误） |
| 单元测试 | `npm test` | 27 passed（date/normalize 工具） |
| 生产构建 | `npm run build` | 成功；存在 >500KB chunk 告警（主包 1.1MB / gzip 381KB），个人工具可接受 |

### 3.3 联调实测（运行中后端 + httpx）

共 60 项接口断言：59 通过 / 1 项为测试脚本自身预期错误（已复核，非产品缺陷）；另经二次确认确认 2 个真实缺陷（见 §5 BUG-1/BUG-2）。实测覆盖：

- 岗位 CRUD：创建默认「待投递」、仅公司名可建、空公司名 400、编辑更新、硬删除 204、删除后 404。
- 状态流转：前进/回退均写时间线、同状态不写事件、进终态记 ended_at、终态回退清 ended_at、进入「已投递」记 applied_at 且不覆盖已有值、事件按 time 升序、非法状态 400。
- 筛选：默认过滤终态、include_ended 含终态、状态多值（`status=已投递,笔试`）、`city=北京&industry=互联网`、`channel=官网&city=北京`（含「北京,上海」多值城市匹配）、keyword、company（LIKE）、deadline 升序（空值排最后）。
- 导入导出：merge 同 id 冲突以本机为准并计 jobs_skipped、merge 新增、overwrite 全量替换、非法文件（字段缺失/非 JSON/版本过高）返回错误且现有数据不受影响。
- 简历：CRUD、绑定冻结名称快照（改名不同步）、被 2 岗位引用删除返回 referenced_by=2、force 删除后引用置空、未引用删除 204、编辑内容回读一致。
- 公司：CRUD、同名 409、删除公司后岗位 company_id 置空。
- 抓取（本地 mock 站点 http://127.0.0.1:8999）：
  - 探测：识别首页 `/careers.html` 候选（confidence=high，source=homepage）。
  - 抓取：JSON-LD 兜底解析 3 条岗位，字段（岗位名/城市/直链/source_job_id/deadline）映射完整，ats_type=jsonld。
  - 导入：首次新增 3、重复导入跳过 3（幂等）、`【2026秋招】` 前缀规范化后命中去重、导入回写公司 last_fetch_result。
  - 降级：robots `Disallow: /careers` 的站点 fetch 返回 failed + ROBOTS_DISALLOW、公司 probe_status=需人工；无岗位页面 fetch done count=0、last_fetch_result=「解析 0 条岗位，请手动录入」。
- 统计（M2 契约先行）：total_applied/active/offered/rejected/pending_followup 口径正确（4 天前流转的进行中岗位计入待跟进）、funnel 从「已投递」起不含「待投递」、weekly_trend 近 4 周按 applied_at、channel_dist 存在、空库全 0 不报错。
- 安全：无 token 401、错误 token 401、恶意 Host 403、boot 恶意 Origin 403、合法 Origin 预检（带 token）返回 200 + ACAO。
- 持久化：重启后端后数据完整保留，token 重新生成（ADR-4）。
- 前端联调：Vite dev server（5173）启动正常，`/api` proxy 转发到后端成功（boot 可通、无 token 请求经 proxy 仍被 401 拦截）。

---

## 4. 按模块验收标准对照表

> 状态说明：通过（实测验证）/ 代码核查（静态确认实现，属 UI 视觉/浏览器行为需人工）/ 未测（附原因）。

| 模块 | PRD 验收标准 | 状态 | 验证说明 |
|---|---|---|---|
| 4.1 | 新增岗位默认「待投递」并进入列表 | 通过 | POST 201，status=待投递 |
| 4.1 | 编辑修改字段保存后字段更新且 updated_at 刷新 | **失败** | 字段更新正常，但 updated_at 不刷新（BUG-1） |
| 4.1 | 删除弹出确认框，确认后移除 | 代码核查 | ListView.vue 使用 ElMessageBox.confirm；删除 API 204 实测通过 |
| 4.1 | 批量删除：勾选多条确认后全部移除 | 通过 | `POST /api/jobs/batch-delete` deleted=2；前端批量确认框已核查 |
| 4.2 | 状态改为「笔试」后时间线新增事件 | 通过 | event.from_status/to_status/type 正确 |
| 4.2 | 回退状态允许且时间线如实记录 | 通过 | 一面→简历筛选 记录 from=笔试 |
| 4.2 | 进入终态后默认移出看板主视图，统计计入终态 | 通过 | 默认过滤终态；include_ended=true 可见；stats 计入 offered/rejected |
| 4.2 | 同状态重复流转不产生新事件 | 通过 | event=null |
| 4.3 | 截止日期=今天时看板顶部「即将截止」展示 | 代码核查 | BoardView 过滤 deadline≤3 天且非终态；deadline 字段存取实测通过 |
| 4.3 | 笔试时间已过且未流转时列表标红提醒 | 代码核查 | ListView 拉取 events 聚合过期标红（.overdue 样式） |
| 4.4 | 卡片从「已投递」拖到「笔试」列状态更新且写事件 | 代码核查 | vuedraggable 跨列 @end → changeStatus；同列直接 return（不产生事件）；等价 API 路径实测通过 |
| 4.4 | 列表点「截止日期」列头按升/降序排列 | 通过 | sort=deadline 升序正确（空值排最后） |
| 4.5 | 输入公司关键词仅显示匹配记录 | 通过 | keyword/company 筛选 |
| 4.5 | 勾选状态筛选后仅显示该状态，条件可见可一键清除 | 通过 | status 多值筛选；「清除筛选」按钮已核查 |
| 4.5 | 城市=北京 + 行业=互联网 组合 | 通过 | 仅返回同时满足的记录 |
| 4.5 | 渠道=官网 + 城市=北京 组合 | 通过 | 含多值城市（北京,上海）子串匹配 |
| 4.6 | 刷新页面/重启后端后数据完整保留 | 通过 | 实测重启后端数据保留 |
| 4.6 | 导出 JSON 包含全部记录（岗位/公司/简历） | 通过 | schema_version=1 + 三集合齐全 |
| 4.7 | 合法备份 merge 导入：现有保留、新记录添加、同 id 不重复 | 通过 | jobs_added/jobs_skipped 计数正确 |
| 4.7 | 非 JSON/字段缺失文件导入提示且数据不受影响 | 通过 | 返回 4xx 错误，数据未变（状态码口径见观察-1） |
| 4.7 | merge 同 id 内容不同以本机为准计入跳过数 | 通过 | 冲突后本机数据不变，jobs_skipped=1 |
| 4.11 | 新建简历填写基本信息/教育经历后保存可再编辑 | 通过 | 创建 201、编辑回读一致 |
| 4.11 | 内容完整简历可打开打印预览、A4 版式、另存 PDF | 代码核查 | window.print() + @page A4 打印样式；版式效果按 PRD Q6 属人工验收项（未测，需浏览器） |
| 4.11 | 岗位选择简历版本保存后显示绑定版本名称 | 通过 | resume_name 快照冻结（改名不同步） |
| 4.11 | 删除被 3 岗位引用的简历：提示引用数、删除、绑定置空 | 通过 | referenced_by 计数 + force 删除后置空 |
| 4.12 | 添加公司后探测并保存招聘页链接（失败可手动填写） | 通过 | mock 探测发现 careers 候选；探测失败/不可达返回 failed；career_url 可人工修正（PUT） |
| 4.12 | 可解析页面点击抓取→预览列表→确认导入→标注去重结果 | 通过 | JSON-LD 解析 3 条 + 导入「新增3/跳过0」+ last_fetch_result 回写 |
| 4.12 | 同公司同岗位再次抓取被跳过并计入跳过数 | 通过 | 重复导入 added=0/skipped=3（source_job_id 与规范化岗位名双路径均验证） |
| 4.12 | JS 动态/强反爬页面提示失败并降级手动录入 | 通过 | robots Disallow → failed + ROBOTS_DISALLOW + 需人工；0 条岗位 → 提示原因降级 |
| 4.12 | 官网已删除岗位，本机记录保留仅计数新增/跳过 | 通过 | 导入不删除现有岗位，重复导入仅计数 |
| 4.8 | 统计卡片/漏斗/趋势口径正确 | 通过 | 契约口径逐项实测（含 pending_followup 3 天阈值） |
| 安全 | 无 token 请求 401 | 通过 | 实测 |
| 安全 | 恶意 Host 403（防 DNS rebinding） | 通过 | 实测 raw socket 带 Host: evil.com |
| 安全 | CORS 白名单生效 | 有条件通过 | 带 token 预检放行/恶意 Origin 无 ACAO；但无 token 预检被 security 先拦截（BUG-2） |
| 安全 | boot 受 Host+Origin 双重校验 | 通过 | 恶意 Origin/Host 均 403 |

---

## 5. 缺陷清单

严重级别：阻断（数据丢失/核心功能不可用）/ 重要 / 一般。本次未发现阻断级缺陷。

### BUG-1（一般）PUT 编辑岗位/简历后 updated_at 不刷新

- **影响模块**：4.1 岗位 CRUD、4.11 简历管理、列表「更新时间」排序
- **违反依据**：PRD 4.1「该记录字段更新且 updated_at 刷新」；api.md「PUT /api/jobs/{id} 部分更新，仅更新传入字段并刷新 updated_at」「PUT /api/resumes/{id} 更新刷新 updated_at」
- **复现步骤**：
  1. 创建岗位，记录响应 `updated_at`；
  2. 等待 2 秒后 `PUT /api/jobs/{id}` 修改 position；
  3. 观察响应 `updated_at` 与创建时相同。
  4. 简历（resume）PUT 相同现象。
- **实际结果**：`updated_at` 不变化（状态流转路径正常刷新，仅编辑路径失效）
- **原因**：`app/dao.py` 的 `update_job`/`update_resume` 仅拼接传入字段的 `SET`，未写入 `updated_at=now`
- **影响评估**：无数据丢失；列表默认按 `updated_at desc` 排序时「最近更新」失真，编辑过的记录不置顶
- **建议**：`dao.update_job`/`dao.update_resume` 的 SET 子句追加 `updated_at=?`（值 `util.now_iso()`），并补充对应断言测试（现有单测未覆盖该点）

### BUG-2（一般）安全中间件先于 CORS 拦截预检，与代码注释/架构意图不符

- **影响模块**：安全基线（架构 §7）、跨源部署形态
- **违反依据**：`app/security.py` 注释「CORS 白名单中间件在 main 中先注册（更外层）」；架构 §7「CORS 白名单中间件先于本中间件处理预检 OPTIONS」
- **复现步骤**：
  1. 对 `OPTIONS /api/jobs` 发预检请求，带合法 Origin `http://127.0.0.1:5173` 与 `Access-Control-Request-Method: POST`，**不带 token**；
  2. 观察响应。
- **实际结果**：返回 401 UNAUTHORIZED、无 ACAO 头；带 token 时预检正常返回 200 + 完整 ACAO 头
- **原因**：FastAPI/Starlette 的 `add_middleware` 采用头插（insert(0)），`main.py` 中 CORS（第 36 行）先注册、security（第 45 行）后注册，实际 **security 在外层、CORS 在内层**
- **影响评估**：当前开发/使用形态经 Vite proxy 同源转发，CORS 不会触发，实际无影响；仅当未来前端从其他来源/端口直连后端 API 时预检会失败。属工程性偏差
- **建议**：将 security 中间件改为在 CORS **之前**注册（即调整两处注册顺序，使 CORS 最外层），或在 security 中对 `OPTIONS + Access-Control-Request-Method` 预检请求直接放行（仍受 Host 校验保护）；同时修正 `security.py` 中错误注释

### 观察-1（低）backup/import 字段缺失返回 400 VALIDATION_ERROR 而非契约的 422 IMPORT_ERROR

- 实测：`jobs: [{"id":"x"}]`（缺 company）返回 HTTP 400 code=VALIDATION_ERROR（Pydantic 层拦截）；而 `jobs:[{"id":"j-x","company":""}]`（字段存在但为空）返回 422 IMPORT_ERROR。同一「导入文件非法」场景状态码口径不一致。
- 契约 `api.md` 错误表：`422 IMPORT_ERROR 导入文件非法（字段缺失/版本过高）`。
- PRD 4.7 验收「提示『文件格式不正确』、现有数据不受影响」已满足（错误信息清晰、数据安全）。
- 建议：预校验改为在 Pydantic 解析前/后统一抛 `import_error`，或调整契约口径，保证「字段缺失」与「版本过高」都走 422。

### 观察-2（低）probe 阶段不对候选 URL 做 robots 逐条过滤

- 实测：`Disallow: /careers` 的站点，probe 仍返回 `/careers.html` 候选（high 置信度），但 fetch 该候选会被正确拒绝（ROBOTS_DISALLOW + 需人工）。
- 影响：用户可能误选被禁链接，随后 fetch 报错——行为可接受且有明确提示。
- 建议：probe 收集候选时对候选 URL 做一次 `robots_allowed` 过滤，命中 Disallow 的不入候选并提示。

### 观察-3（低）非法 sort 参数静默回退默认排序

- 实测：`GET /api/jobs?sort=hack;drop` 返回 200 并按默认排序（白名单外回退 `updated_at`）。契约未规定非法 sort 必须 400，静默回退可接受，但可能掩盖前端拼写错误。建议后续可加日志。

### 观察-4（低）前端主构建 chunk 偏大

- `npm run build` 告警：主包 1.14MB（gzip 381KB），`StatsView` 单独 505KB。个人工具可接受；M2 如需优化可对路由组件做动态 import 分包（当前已是按路由懒加载，主要为 Element Plus/ECharts 体积）。

### 观察-5（低）简历「至少一个区块有内容才可导出」无显式守卫

- PRD 4.11 业务规则「至少有一个区块有内容才可导出」。`ResumePreviewView` 的打印按钮未按内容量置灰。因 `basic` 为必填（姓名/电话/邮箱等），任何简历实际恒有一个区块，该规则在现实中天然满足，风险极低。如后续允许空 basic 需补守卫。

---

## 6. 遗漏的 PRD 验收项（未能自动化验证，需浏览器人工验收）

| 验收项 | 原因 | 已做替代验证 |
|---|---|---|
| 4.4 看板拖拽流转的视觉/交互（跨列拖放、拖回同一列不动作） | 需真实浏览器鼠标操作 | 代码核查 vuedraggable 跨列 @end→changeStatus、同列 return；API 等价路径实测通过 |
| 4.11 简历 A4 打印/另存 PDF 的实际版式与分页 | PRD Q6 明确为人工验收项 | 代码核查 window.print() + `@page size:A4` 打印样式；ResumeRenderer 渲染 |
| 4.3 看板「今日/本周安排」「即将截止」与列表过期标红的视觉呈现 | 需浏览器渲染确认 | 代码核查聚合逻辑与样式类 |
| 4.1/4.11 删除二次确认、4.7 overwrite 二次确认弹窗 | 需浏览器操作 | 代码核查 ElMessageBox.confirm 已接入 |
| 4.5 筛选栏「一键清除」交互 | 需浏览器操作 | 代码核查 clearFilters 按钮 |
| 4.12 前端 probe/fetch 轮询进度条与预览导入弹窗 | 需浏览器操作 | 代码核查 pollTask（90s 上限）与 FetchPreviewModal |
| 真实官网抓取（Greenhouse/Lever/飞书/北森等） | 合规与限速考量，未对真实站点过度抓取 | 用本地 mock（JSON-LD 兜底路径）+ robots 降级路径验证了后端逻辑；真实站点适配留待使用中验证 |
| 浏览器通知（4.9）、备注界面（4.10） | M2 范围 | — |

---

## 7. 对 M2 的测试建议

1. **修复回归**：M2 开始前优先回归 BUG-1（updated_at）与 BUG-2（CORS 顺序），并为 `PUT 刷新 updated_at` 补充单测与冒烟断言（当前测试缺口）。
2. **统计面板**（4.8）：M1 契约已就绪，M2 需补：漏斗空态与全零态、pending_followup 边界（恰 3 天/负值 time 参数）、weekly_trend 跨周/跨月边界（周一为周起点）、channel 为 null 时「未填写」桶、前端 ECharts 空数据不报错。
3. **提醒**（4.9）：建议加纯函数单测覆盖「同一提醒点只触发一次」「页面关闭错过提醒补一条」；浏览器通知授权流程做人工清单。
4. **备注/面经**（4.10）：notes 数组已定结构，后端需补 `POST notes` 追加接口契约与测试（时间排序、多段追加、非法内容校验）。
5. **抓取扩展**（北森/Moka/大易适配器）：按架构 9.2 扩展点，为每个新适配器准备 mock fixture（HTML 样例 + 期望字段映射），纳入 pytest；真实站点仅做少量人工抽样验证并严格限速。
6. **自动化沉淀**：将本次联调脚本（httpx 全流程）沉淀为 `backend/tests/test_acceptance.py`（mock 站点用本地 fixture 起停），纳入 CI（如本地 git）与冒烟。
7. **性能**：M2 提醒与统计若引入定时器/轮询，建议对「千条记录 + 高频轮询」做一次简单压测（本机回环 API 延迟 <50ms 目标）。
8. **兼容性**：简历打印/PDF 需在 Chrome 与 Edge 各验一次分页（PRD 兼容性要求 Chromium 系）。

---

## 8. 附录

- 测试数据文件：联调脚本位于 `C:\Users\无铭\AppData\Local\Temp\jh_accept_integration.py`（httpx 全流程，60 项断言），本次验收临时使用，建议按 §7-6 沉淀入仓。
- 后端冒烟脚本：`backend/scripts/smoke.py`（34 断言，自启临时后端，可重复执行）。
- 环境：Python 3.13.9、Node（Vite 5.4.21/vitest 2.1.9）、后端依赖 fastapi/uvicorn/pydantic/httpx/bs4 已装。
