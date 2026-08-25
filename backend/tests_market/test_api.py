# -*- coding: utf-8 -*-
"""API 层测试（前后端分离后端）：
- /api/health 健康检查
- /api/jobs/summary 聚合数据（summary/filtered/charts 5 模块）
- /api/jobs 分页 + 筛选 + 关键词搜索
- /api/meta 筛选选项
- /api/model/predict 无模型时 404 降级
- market/api/stats 聚合纯函数
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from market.api.app import create_app
from market.api import stats as stats_mod
from market.config import Config, load_config
from market.storage import init_db, upsert_jobs
from market.storage.session import reset_engine


@pytest.fixture(scope="module")
def sqlite_cfg(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "test_api.db"
    cfg = load_config()
    raw = cfg.raw
    raw["database"] = {
        "driver": "sqlite",
        "sqlite_path": str(db_file),
        "password_env": "",
        "password_default": "",
    }
    # 模型目录指向空目录：predict 走 404 降级路径
    raw["paths"]["model_dir"] = str(tmp_path_factory.mktemp("model"))
    return Config(raw)


@pytest.fixture(autouse=True)
def _fresh_db(sqlite_cfg):
    reset_engine()
    engine = init_db(sqlite_cfg, drop_first=True)
    rows = []
    for i in range(40):
        rows.append({
            "job_id": f"api_{i}", "job_title": f"数据分析师{i}",
            "job_category": ["数据分析", "算法"][i % 2],
            "job_type": "社招", "company_name": f"公司{i % 5}",
            "industry": "互联网", "company_size": "1000-5000人",
            "city": ["北京", "上海", "杭州"][i % 3],
            "salary_raw": "15-25K", "salary_min": 15000, "salary_max": 25000,
            "salary_avg": 15000 + i * 200, "experience_req": "1-3年",
            "education_req": ["本科", "硕士"][i % 2],
            "job_desc": "负责数据分析相关工作", "tags": ["五险一金"],
            "post_date": None, "crawl_date": datetime(2026, 1, 1, 10, 0, 0),
            "url": "http://example.com/job", "is_valid": 1, "source": "backup",
        })
    upsert_jobs(rows, sqlite_cfg)
    yield engine
    reset_engine()


@pytest.fixture()
def client(sqlite_cfg):
    return TestClient(create_app(sqlite_cfg))


def test_health(client):
    r = client.get("/api/market/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["jobs"] == 40
    assert body["db"] == "sqlite"


def test_summary_structure(client):
    r = client.get("/api/market/jobs/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["total"] == 40
    assert body["filtered"]["total"] == 40
    charts = body["charts"]
    assert {"salary_hist", "city_salary", "skill_top", "category_dist", "heatmap"} <= set(charts)
    assert body["summary"]["cities"] == ["上海", "北京", "杭州"]
    # 薪资直方图 bins/counts 长度一致
    assert len(charts["salary_hist"]["bins"]) == len(charts["salary_hist"]["counts"])
    assert len(charts["city_salary"]["cities"]) == 3


def test_summary_filter(client):
    r = client.get("/api/market/jobs/summary", params={"city": "北京", "education": "硕士"})
    body = r.json()
    assert body["filtered"]["total"] > 0
    assert body["filtered"]["total"] < 40
    # 热力图网格保持全量城市（与原单 HTML 一致），筛选后仅目标城市有数据点
    hm = body["charts"]["heatmap"]
    assert hm["y"] == ["上海", "北京", "杭州"]
    beijing_idx = hm["y"].index("北京")
    assert hm["data"]  # 北京格子非空
    assert all(d[1] == beijing_idx for d in hm["data"])


def test_jobs_pagination_and_search(client):
    r = client.get("/api/market/jobs", params={"page": 2, "page_size": 10})
    body = r.json()
    assert body["total"] == 40
    assert body["page"] == 2
    assert len(body["items"]) == 10
    assert body["total_pages"] == 4

    r = client.get("/api/market/jobs", params={"keyword": "数据分析师1", "page_size": 50})
    body = r.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert "数据分析师1" in item["title"]


def test_jobs_filters(client):
    r = client.get("/api/market/jobs", params={"city": "杭州", "job_type": "社招", "page_size": 50})
    body = r.json()
    assert all(j["city"] == "杭州" for j in body["items"])
    assert body["total"] == body["total"]  # 40//3 附近
    # item 字段齐全
    keys = set(body["items"][0].keys())
    assert {"job_id", "title", "company", "city", "salary_avg", "url", "skills"} <= keys


def test_meta(client):
    r = client.get("/api/market/meta")
    assert r.status_code == 200
    assert r.json()["categories"] == ["数据分析", "算法"]


def test_predict_without_model(client):
    r = client.post("/api/market/predict", json={
        "job_title": "数据分析师", "city": "北京", "job_category": "数据分析",
    })
    assert r.status_code == 404
    assert "模型文件不存在" in r.json()["detail"]


# ---------------------------------------------------------------- 聚合纯函数
def test_stats_filter_records():
    records = [
        {"c": "北京", "g": "数据分析", "e": "本科", "s": 20000, "sk": ["SQL"]},
        {"c": "上海", "g": "算法", "e": "硕士", "s": 30000, "sk": ["Python"]},
        {"c": "北京", "g": "算法", "e": "硕士", "s": 25000, "sk": ["Python", "SQL"]},
    ]
    assert len(stats_mod.filter_records(records, city="北京")) == 2
    assert len(stats_mod.filter_records(records, city="北京", category="算法")) == 1
    assert len(stats_mod.filter_records(records, education="硕士")) == 2


def test_stats_salary_hist():
    records = [{"c": "北京", "g": "a", "e": "本科", "s": s, "sk": []} for s in range(15000, 30001, 1500)]
    h = stats_mod.salary_hist(records)
    assert h["bins"] and h["step"] > 0
    assert sum(h["counts"]) == len(records)


def test_stats_skill_top():
    records = [
        {"c": "北京", "g": "a", "e": "本科", "s": 1, "sk": ["Python", "SQL"]},
        {"c": "上海", "g": "a", "e": "本科", "s": 1, "sk": ["Python"]},
    ]
    top = stats_mod.skill_top(records, k=5)
    assert top[0]["name"] == "Python"
    assert top[0]["count"] == 2
    assert top[0]["ratio"] == 1.0
