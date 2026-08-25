# -*- coding: utf-8 -*-
"""ECharts 交互看板（REQ-VIZ-01~04）：
- 单 HTML 文件，数据以 JS 对象内嵌（无 fetch，file:// 双击可开）
- 筛选联动：城市 / 岗位类别 / 学历 → 薪资分布与技能 Top 联动更新
- ≥4 个可视化模块：薪资分布、城市薪资对比、技能 Top、岗位量占比、城市×类别热力图
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from market.config import Config
from market.storage import fetch_jobs_for_analysis

logger = logging.getLogger(__name__)

CITY_ORDER = ["北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉", "西安", "苏州"]
CATEGORY_ORDER = ["数据分析", "数据科学", "大数据", "算法", "BI数仓"]
EDUCATION_ORDER = ["不限", "大专", "本科", "硕士", "博士"]


def _load_features(cfg: Config) -> Optional[pd.DataFrame]:
    feat_path = Path(cfg.raw["paths"]["features_path"])
    if feat_path.exists():
        return pd.read_parquet(feat_path)
    return None


def build_dashboard_data(df: pd.DataFrame, features_df: Optional[pd.DataFrame]) -> dict:
    """构建看板内嵌数据（明细轻量投影 + 概览统计）。"""
    if features_df is not None:
        df = df.copy()
        key_cols = [c for c in ["job_id", "crawl_date"] if c in df.columns and c in features_df.columns]
        if key_cols:
            for k in key_cols:
                df[k] = df[k].astype(str)
                features_df[k] = features_df[k].astype(str)
            df = df.merge(features_df[key_cols + ["skills_hit"]], on=key_cols, how="left")
    else:
        df["skills_hit"] = [[]] * len(df)

    # 压缩字段名减小体积
    records = []
    for r in df.itertuples(index=False):
        sk = getattr(r, "skills_hit", None)
        if sk is None:
            sk = []
        elif hasattr(sk, "tolist"):   # numpy 数组 → list
            sk = sk.tolist()
        records.append({
            "c": r.city, "g": r.job_category, "e": r.education_req,
            "s": int(r.salary_avg) if pd.notna(r.salary_avg) else None,
            "sk": [str(x) for x in sk] if isinstance(sk, list) else [],
            "src": getattr(r, "source", ""),
        })

    sal = df["salary_avg"].dropna()
    summary = {
        "total": int(len(df)),
        "mean_salary": int(round(float(sal.mean()))) if len(sal) else 0,
        "median_salary": int(round(float(sal.median()))) if len(sal) else 0,
        "cities": sorted(df["city"].unique().tolist()),
        "categories": [c for c in CATEGORY_ORDER if c in df["job_category"].unique()],
        "educations": [e for e in EDUCATION_ORDER if e in df["education_req"].unique()],
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
    }
    return {"summary": summary, "records": records}


def _echarts_js() -> str:
    path = Path(__file__).parent / "echarts.min.js"
    return path.read_text(encoding="utf-8")


def render_html(data: dict) -> str:
    """渲染单 HTML（数据内嵌 + echarts 内嵌）。

    注意：不能使用 str.format()（echarts.min.js 含大量 {} 字面量），改用占位符替换；
    内嵌 JSON 转义 < > &（防 </script> 注入 / XSS，安全审查项）。
    """
    payload = json.dumps(data, ensure_ascii=False)
    payload = (payload.replace("<", "\\u003c").replace(">", "\\u003e")
               .replace("&", "\\u0026"))
    js = _echarts_js()
    return (_HTML_TEMPLATE
            .replace("__ECHARTS_JS__", js)
            .replace("__PAYLOAD__", payload))


def generate_dashboard(cfg: Config, df: Optional[pd.DataFrame] = None,
                       features_df: Optional[pd.DataFrame] = None) -> str:
    """一键生成看板 HTML（REQ-VIZ-04），返回文件路径。"""
    if df is None:
        df = fetch_jobs_for_analysis(cfg, valid_only=True)
    if features_df is None:
        features_df = _load_features(cfg)
    data = build_dashboard_data(df, features_df)
    html = render_html(data)
    out = Path(cfg.raw["viz"]["dashboard_output"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    logger.info("看板已生成: %s (%.0f KB)", out, out.stat().st_size / 1024)
    return str(out)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>JobPulse 招聘情报站 · 数据分析/数据科学岗位看板</title>
<style>
  body { font-family: "Microsoft YaHei", sans-serif; margin: 0; background: #f5f7fa; color: #333; }
  .header { background: linear-gradient(135deg, #2b5876, #4e4376); color: #fff; padding: 18px 28px; }
  .header h1 { margin: 0; font-size: 22px; }
  .header p { margin: 6px 0 0; opacity: .85; font-size: 13px; }
  .cards { display: flex; gap: 14px; padding: 16px 28px; flex-wrap: wrap; }
  .card { background: #fff; border-radius: 8px; padding: 14px 20px; box-shadow: 0 1px 4px rgba(0,0,0,.08); min-width: 150px; }
  .card .num { font-size: 26px; font-weight: 700; color: #2b5876; }
  .card .lbl { font-size: 12px; color: #888; margin-top: 2px; }
  .filters { padding: 0 28px 8px; display: flex; gap: 18px; flex-wrap: wrap; align-items: center; background:#fff; padding-top: 14px; }
  .filters label { font-size: 13px; color: #555; }
  .filters select { padding: 6px 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 13px; }
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px 28px; }
  .panel { background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.08); padding: 10px; }
  .panel h3 { margin: 6px 10px; font-size: 14px; color: #2b5876; }
  .chart { width: 100%; height: 320px; }
  .full { grid-column: 1 / -1; }
  .foot { text-align: center; color: #999; font-size: 12px; padding: 10px 0 20px; }
</style>
</head>
<body>
<div class="header">
  <h1>📊 JobPulse 招聘情报站 — 数据分析 / 数据科学岗位市场看板</h1>
  <p>数据来源：GitHub 开源数据集（Rayair019/Job-posting-data，2025 中国平台岗位） · 数据内嵌 · 双击即可打开</p>
</div>

<div class="cards">
  <div class="card"><div class="num" id="stat_total">-</div><div class="lbl">有效岗位数</div></div>
  <div class="card"><div class="num" id="stat_mean">-</div><div class="lbl">平均月薪（元）</div></div>
  <div class="card"><div class="num" id="stat_median">-</div><div class="lbl">月薪中位数（元）</div></div>
  <div class="card"><div class="num" id="stat_city">-</div><div class="lbl">覆盖城市</div></div>
</div>

<div class="filters">
  <label>城市 <select id="f_city"></select></label>
  <label>岗位类别 <select id="f_cat"></select></label>
  <label>学历 <select id="f_edu"></select></label>
  <span id="filter_note" style="font-size:12px;color:#999;"></span>
</div>

<div class="charts">
  <div class="panel"><h3>① 薪资分布（筛选后）</h3><div id="c_salary" class="chart"></div></div>
  <div class="panel"><h3>② 城市薪资对比（月薪中位数）</h3><div id="c_city" class="chart"></div></div>
  <div class="panel"><h3>③ 技能需求 Top15（命中岗位占比）</h3><div id="c_skills" class="chart"></div></div>
  <div class="panel"><h3>④ 岗位量占比（按类别）</h3><div id="c_cat" class="chart"></div></div>
  <div class="panel full"><h3>⑤ 城市 × 岗位类别 岗位量热力图</h3><div id="c_heat" class="chart" style="height:360px;"></div></div>
</div>

<div class="foot">JobPulse v0.2 · 生成时间 <span id="gen_time"></span></div>

<script>__ECHARTS_JS__</script>
<script>
const DATA = __PAYLOAD__;
const SUMMARY = DATA.summary;
const RECORDS = DATA.records;

let charts = {};
function init_charts() {
  charts.salary = echarts.init(document.getElementById('c_salary'));
  charts.city = echarts.init(document.getElementById('c_city'));
  charts.skills = echarts.init(document.getElementById('c_skills'));
  charts.cat = echarts.init(document.getElementById('c_cat'));
  charts.heat = echarts.init(document.getElementById('c_heat'));
  window.addEventListener('resize', () => Object.values(charts).forEach(c => c.resize()));
}

function setup_filters() {
  const citySel = document.getElementById('f_city');
  const catSel = document.getElementById('f_cat');
  const eduSel = document.getElementById('f_edu');
  const addOpt = (sel, val, label) => {
    const o = document.createElement('option'); o.value = val; o.text = label; sel.appendChild(o);
  };
  addOpt(citySel, '', '全部城市'); SUMMARY.cities.forEach(c => addOpt(citySel, c, c));
  addOpt(catSel, '', '全部类别'); SUMMARY.categories.forEach(c => addOpt(catSel, c, c));
  addOpt(eduSel, '', '全部学历'); SUMMARY.educations.forEach(e => addOpt(eduSel, e, e));
  [citySel, catSel, eduSel].forEach(s => s.addEventListener('change', render));
}

function filtered() {
  const city = document.getElementById('f_city').value;
  const cat = document.getElementById('f_cat').value;
  const edu = document.getElementById('f_edu').value;
  return RECORDS.filter(r =>
    (!city || r.c === city) && (!cat || r.g === cat) && (!edu || r.e === edu));
}

function stats(rows) {
  const total = rows.length;
  const sals = rows.map(r => r.s).filter(x => x != null).sort((a, b) => a - b);
  const mean = sals.length ? Math.round(sals.reduce((a, b) => a + b, 0) / sals.length) : 0;
  const median = sals.length ? sals[Math.floor(sals.length / 2)] : 0;
  return { total, mean, median };
}

function salaryHist(rows) {
  const sals = rows.map(r => r.s).filter(x => x != null);
  if (!sals.length) return { bins: [], counts: [] };
  const max = Math.max(...sals), min = Math.min(...sals);
  const nBins = 15, step = Math.max(1, Math.ceil((max - min) / nBins));
  const bins = [], counts = new Array(nBins).fill(0);
  for (let i = 0; i < nBins; i++) bins.push(min + i * step);
  sals.forEach(s => {
    let idx = Math.min(nBins - 1, Math.floor((s - min) / step));
    counts[idx]++;
  });
  return { bins, counts, step };
}

function skillTop(rows, k = 15) {
  const cnt = {};
  rows.forEach(r => (r.sk || []).forEach(sk => { cnt[sk] = (cnt[sk] || 0) + 1; }));
  const arr = Object.entries(cnt).map(([s, n]) => ({ s, n })).sort((a, b) => b.n - a.n).slice(0, k);
  const total = rows.length || 1;
  return arr.map(x => ({ ...x, ratio: x.n / total }));
}

function render() {
  const rows = filtered();
  const st = stats(rows);
  document.getElementById('stat_total').textContent = st.total;
  document.getElementById('stat_mean').textContent = st.mean ? st.mean.toLocaleString() : '-';
  document.getElementById('stat_median').textContent = st.median ? st.median.toLocaleString() : '-';
  document.getElementById('stat_city').textContent = new Set(rows.map(r => r.c)).size;
  document.getElementById('filter_note').textContent = `当前筛选：${st.total} 条岗位`;

  // ① 薪资分布
  const h = salaryHist(rows);
  charts.salary.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: h.bins.map((b, i) => `${Math.round(b/1000)}-${Math.round((b+h.step)/1000)}k`) },
    yAxis: { type: 'value', name: '岗位数' },
    series: [{ type: 'bar', data: h.counts, itemStyle: { color: '#4C72B0' } }]
  }, true);

  // ② 城市薪资对比
  const cityAgg = {};
  rows.forEach(r => { if (r.s == null) return; (cityAgg[r.c] = cityAgg[r.c] || []).push(r.s); });
  const cities = Object.keys(cityAgg).sort();
  const meds = cities.map(c => {
    const a = cityAgg[c].sort((x, y) => x - y); return a[Math.floor(a.length / 2)];
  });
  charts.city.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: cities },
    yAxis: { type: 'value', name: '月薪中位数（元）' },
    series: [{ type: 'bar', data: meds, itemStyle: { color: '#55A868' } }]
  }, true);

  // ③ 技能 Top
  const top = skillTop(rows);
  charts.skills.setOption({
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}：${p[0].value.toFixed(1)}%` },
    xAxis: { type: 'value', name: '占比', axisLabel: { formatter: v => v + '%' } },
    yAxis: { type: 'category', data: top.map(t => t.s).reverse() },
    series: [{ type: 'bar', data: top.map(t => +(t.ratio * 100).toFixed(1)).reverse(), itemStyle: { color: '#C44E52' } }]
  }, true);

  // ④ 岗位量占比
  const catAgg = {};
  rows.forEach(r => { catAgg[r.g] = (catAgg[r.g] || 0) + 1; });
  const cats = Object.keys(catAgg).sort((a, b) => catAgg[b] - catAgg[a]);
  charts.cat.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie', radius: ['40%', '68%'],
      data: cats.map(c => ({ name: c, value: catAgg[c] })),
      label: { formatter: '{b}\\n{d}%' }
    }]
  }, true);

  // ⑤ 热力图
  const gmap = SUMMARY.categories, cms = SUMMARY.cities;
  const heat = [];
  cms.forEach((ci, i) => gmap.forEach((gj, j) => {
    heat.push([j, i, rows.filter(r => r.c === ci && r.g === gj).length]);
  }));
  charts.heat.setOption({
    tooltip: { position: 'top', formatter: p => `${cms[p.value[1]]}×${gmap[p.value[0]]}：${p.value[2]} 条` },
    grid: { left: 80, top: 20, right: 40, bottom: 60 },
    xAxis: { type: 'category', data: gmap, splitArea: { show: true } },
    yAxis: { type: 'category', data: cms, splitArea: { show: true } },
    visualMap: { min: 0, max: Math.max(...heat.map(x => x[2]), 1), calculable: true, orient: 'horizontal', left: 'center', bottom: 0 },
    series: [{
      type: 'heatmap', data: heat,
      label: { show: true, fontSize: 9 },
      emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.4)' } }
    }]
  }, true);
}

document.getElementById('gen_time').textContent = SUMMARY.generated_at;
init_charts();
setup_filters();
render();
</script>
</body>
</html>
"""
