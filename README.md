# JobPilot · 秋招投递与市场情报

个人秋招全流程工具：**投递管理**（自己的岗位进度、简历、公司库）与**市场情报**（数据岗位市场行情、薪资预测）合二为一。

## 功能

**投递管理**（Vue 3 + TS + FastAPI + SQLite，数据 100% 本机）
- 岗位记录 CRUD、状态机看板（拖拽流转 + 时间线）
- 简历管理：多份简历 CRUD、A4 版式打印/导出 PDF、岗位绑定简历版本
- 公司库：txt 批量导入、按公司名自动补全官网/招聘页/行业、官网招聘页探测与岗位抓取
- 看板/列表/统计/提醒/备份（JSON 导出导入）

**市场情报**（原 JobPulse：Python 采集→清洗→分析→建模→可视化）
- 招聘数据采集：国聘网/牛客网公开接口 + 兜底数据集（10,114 条数据科学岗位）
- 市场看板：薪资分布/城市对比/技能 Top15/岗位量占比/城市×类别热力图，多条件联动筛选
- 岗位库检索：10 城 × 5 类岗位，分页/搜索/排序
- XGBoost 薪资预测：测试集 R² = 0.514，在线预测接口

**协同能力**
- 市场岗位一键导入投递列表（发现 → 跟踪闭环）
- 岗位录入时一键参考市场薪资区间（决策辅助）

## 目录结构

```
backend/     FastAPI 后端（投递域 app/ + 市场域 market/，共用 SQLite）
frontend/    Vue 3 + TS 前端（看板/列表/公司库/简历/统计/设置 + 市场情报三页）
docs/        产品与设计文档（prd.md、architecture.md、review.md、test-report.md、market/）
```

## 启动

```bash
# 后端（127.0.0.1:8000，端口被占自动换随机端口）
cd backend && pip install -r requirements.txt -r requirements-market.txt
python run.py

# 前端（开发模式，/api 自动代理到后端）
cd frontend && npm install && npm run dev
```

首次使用建议：先 `python -m market.cli crawl --source backup` 导入市场数据集（需将数据集文件放至 `backend/market/data/raw/job_posting_data.xlsx`），再 `python -m market.cli model` 生成薪资预测模型。

详见 `backend/README.md`（后端/API/CLI 细节）、`docs/`（产品与架构文档）。
