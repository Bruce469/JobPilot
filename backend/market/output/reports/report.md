# JobPulse 招聘情报站 — 分析报告

- 生成时间：2026-08-21 13:42:17
- 数据量：jobs 总 10114 条 / 有效 7387 条 / 快照 30342 条
- 数据源：GitHub 开源数据集（Rayair019/Job-posting-data，2025 中国平台岗位，10,114 条）

## 1. 核心结论（可写入简历）

### 1.1 北京是数据分析/数据科学岗位最集中的城市

北京有效岗位 3270 条，占全部有效记录 44.3%（样本 N=7387，口径：10 城有效岗位）

### 1.2 城市薪资差异明显：上海 中位数最高、西安 最低

上海 月薪中位数 25,000 元 vs 西安 11,375 元，差距 2.2 倍（口径：全职岗位 salary_avg 中位数，样本 N=7387）

### 1.3 大数据 岗薪资中位数最高

大数据 月薪中位数 22,500 元（样本 807 条），高于最低的 数据科学（16,000 元）41%（口径：全职岗位中位数）

### 1.4 硕士学历薪资显著高于本科

硕士月薪中位数 22,500 元 vs 本科 18,083 元，硕士溢价 24%（口径：全职岗位中位数，样本 本科 2269 / 硕士 845）

### 1.5 经验积累带来薪资跃升

5-10 年经验月薪中位数 38,750 元，是 1-3 年（18,812 元）的 2.1 倍（口径：全职岗位中位数）

### 1.6 实习薪资：算法岗最高

实习岗位 177 条（薪资可解析），月薪中位数 17,500 元；算法类实习中位数 24,000 元（口径：实习岗日薪×20 折月薪，4.3 规则 7）

## 2. 图表

- [城市岗位量分布](output\charts\eda_city_job_count.png)
- [岗位大类分布](output\charts\eda_category_dist.png)
- [行业 Top15](output\charts\eda_industry_top.png)
- [学历×薪资](output\charts\eda_edu_salary.png)
- [经验×薪资](output\charts\eda_exp_salary.png)
- [城市×薪资](output\charts\eda_city_salary.png)
- [岗位类别×薪资（全职 vs 实习）](output\charts\eda_category_salary.png)
- [城市×大类热力图](output\charts\eda_city_category_heatmap.png)

## 3. 技能图谱

- 技能词表：`config/skill_words.json`（89 个核心技能词）
- 高频技能 Top30 统计口径：命中该技能的岗位数 / 有效岗位总数
- 图表：`output/charts/nlp_top_skills.png`（Top30 排名）、`output/charts/nlp_skill_diff.png`（差异对比）、`output/charts/nlp_wordcloud.png`（词云）
- 特征产物：`output/analysis/features.parquet`（skills_hit / skills_count，REQ-NLP-05）

## 4. 薪资预测模型

- 模型：XGBoost 回归（log 目标变换），预测 salary_avg
- 建模集：总 7387 条 → 去重后 7387（剔除 0 重复）→ 剔除实习 177 → 可建模 7210 条
- 评估（测试集）：**R² = 0.5144**，MAE = 8733.0，RMSE = 12508.3
- 验收：R² ≥ 0.50 → ✅ 达标
- 基线对比：线性回归 R²=0.4652，均值基线 R²=-0.0002
- 特征重要性 Top10 图：`output\charts\model_feature_importance.png`
- 实习岗默认剔除出建模集（REQ-ML-02）；目标编码无（one-hot，无泄漏风险）

## 5. 数据质量

- 数据质量报告：`output/reports/data_quality_report.md`（缺失率/面议/异常薪资/实习单列）

## 6. 时间趋势说明（REQ-EDA-04）

- 快照批次数：3（≥2，满足产出条件）。
- 趋势图：![批次趋势](output\charts\trend_snapshots.png)
- 当前各批次为同一数据源重复采集，岗位量与薪资保持稳定属预期；
- 随增量采集批次积累（不同时间点数据源），可观察市场真实变化。

## 7. 限制与声明

- 南京(190)/西安(143)/苏州(110) 单城样本 <200，属数据集覆盖限制（需求 4.4 弹性标准，报告中声明）。
- 数据为 2025 年中国主流招聘平台公开岗位文本，分析结论为市场趋势参考（3.2）。
- 数据集无明确开源许可证，仅限个人学习使用，不二次分发（README 声明）。
