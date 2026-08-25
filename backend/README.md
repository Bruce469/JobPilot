# 秋招投递助手 - 后端（含市场情报模块）

Python + FastAPI + SQLite 的本地轻量服务，融合两个业务域：

- **投递管理**（宿主）：岗位/简历/公司库 CRUD、状态机看板、官网招聘页探测与抓取。
- **市场情报**（`market/`，原 JobPulse）：招聘平台岗位数据采集、清洗、EDA、技能图谱、XGBoost 薪资预测、市场看板聚合。

## 环境

- Python >= 3.11（开发环境 3.13）
- 依赖安装（按需选择，均有独立文件）：

```bash
pip install -r requirements.txt          # 核心：投递管理 + market API 框架
pip install -r requirements-market.txt   # 市场看板/岗位接口运行必需（pandas/numpy/pyarrow）
pip install -r requirements-ml.txt       # CLI 建模/NLP 流水线（xgboost/jieba/wordcloud/matplotlib...）
pip install -r requirements-mysql.txt    # 可选：MySQL 驱动（默认 SQLite，无需安装）
```

## 启动

```bash
python run.py                 # 默认 127.0.0.1:8000，端口被占自动换随机端口
python run.py --port 9000     # 指定端口
```

环境变量（可选）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `APP_PORT` | `8000` | 端口 |
| `APP_HOST` | `127.0.0.1` | 仅监听本机 |
| `APP_DB_PATH` | `data/app.db` | SQLite 数据文件路径（投递域与市场域共用同一库文件） |

启动后：

- 首次访问 `GET /api/boot` 获取随机 token（无鉴权），后续所有请求带 `X-Auth-Token` 头。
- 数据库自动迁移（`migrations/`，WAL 模式）：`001_init` 建投递域四表，`002_market_jobs` 建市场域两表。
- 启动时若距上次导出备份 >7 天会提示；`/api/boot` 响应含 `backup` 字段。

## 市场情报模块（market/）

- 配置：`market/config/config.yaml`（存储统一 SQLite，与投递域共用 `data/app.db`）。
- 数据集兜底源：`market/data/raw/job_posting_data.xlsx`（10,114 条数据科学岗位，需自行放置）。
- CLI 流水线（与 A 的 `run.py` 独立运行，`cd backend` 后执行）：

```bash
python -m market.cli crawl --source backup   # 导入兜底数据集（或 --source iguopin/nowcoder 抓实时源）
python -m market.cli etl                      # 数据质量报告
python -m market.cli analyze                  # EDA 图表与洞察
python -m market.cli nlp                      # 技能图谱 + features.parquet
python -m market.cli model                    # 训练/导出 XGBoost 薪资模型
python -m market.cli viz                      # 生成单 HTML 看板
python -m market.cli report                   # 分析报告
python run_market.py                          # 一键链路（等价原 run_all.py）
```

## 测试

```bash
python -m pytest tests/ -q               # 投递域单元测试
python -m pytest tests_market/ -q -m "not live"   # 市场域单元测试（联网用例默认跳过）
python scripts/smoke.py                  # 冒烟测试（临时 DB + 随机端口，41 项断言）
```

## API 一览

统一错误结构：`{"error": {"code": "...", "message": "...", "details": {...}}}`；除 `GET /api/boot` 外全部需要 `X-Auth-Token`。

### 投递管理（原秋招投递助手）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/boot | 下发 token 与应用信息 |
| GET/POST | /api/jobs | 岗位列表（筛选/排序）/ 创建 |
| GET/PUT/DELETE | /api/jobs/{id} | 详情（含时间线）/ 更新 / 删除 |
| POST | /api/jobs/batch-delete | 批量删除 |
| POST | /api/jobs/{id}/status | 状态流转（写 job_events） |
| POST | /api/jobs/import | 抓取结果去重导入 |
| GET/POST | /api/resumes | 简历列表 / 创建 |
| GET/PUT/DELETE | /api/resumes/{id} | 简历 CRUD（删除引用保护） |
| GET/POST | /api/companies | 公司列表 / 创建 |
| POST | /api/companies/import | 公司批量导入（txt） |
| POST | /api/companies/resolve | 公司名自动补全 |
| GET/PUT/DELETE | /api/companies/{id} | 公司 CRUD |
| POST | /api/companies/{id}/probe \| fetch | 探测招聘入口 / 抓取岗位（异步） |
| GET | /api/tasks/{job_id} | 轮询异步任务 |
| GET/POST | /api/backup/export \| import | 全量备份 / 导入 |
| GET | /api/stats | 投递统计 |

### 市场情报（/api/market/*）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/market/health | 健康检查（market_jobs/market_job_snapshots 计数 + DB 驱动） |
| GET | /api/market/jobs | 市场岗位分页（筛选/搜索/排序） |
| GET | /api/market/jobs/summary | 看板聚合（summary + 5 图表模块，支持城市/类别/学历/数据源筛选） |
| GET | /api/market/meta | 筛选选项 |
| POST | /api/market/predict | 薪资预测（需先 `python -m market.cli model` 导出模型） |
