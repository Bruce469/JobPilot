# -*- coding: utf-8 -*-
"""实时源 adapter 单测：iguopin(国聘) / nowcoder(牛客)。

覆盖：
- 字段映射（对齐 market_jobs 表 Schema，附录 11.4）
- 薪资归一化（元/月、实习日薪×20、面议）
- 城市白名单有效性判定（REQ-4.4）
- fetch_page 请求构造与 BlockedError 容错
- stats.filter_records 按 source 过滤

合并决策：本文件整体标记 live（涉及真实数据源协议断言，默认排除）；
验收命令 python -m pytest tests_market/ -q -m "not live" 会跳过本文件。
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from market.api import stats as stats_mod
from market.crawler.iguopin import IguopinAdapter, transform_row as iguopin_row
from market.crawler.nowcoder import NowcoderAdapter, transform_row as nowcoder_row

pytestmark = pytest.mark.live   # 联网/真实数据源相关用例，默认跳过（-m "not live" 排除）

CRAWL_DATE = datetime(2026, 2, 1, 12, 0, 0)

# ---------------- 国聘样例（2026-02 接口实测结构） ----------------
IGUOPIN_ITEM = {
    "job_id": "214746080682968399",
    "job_name": "数据分析师（校招）",
    "company_name": "河北省物流产业集团有限公司",
    "nature_cn": "校招",
    "category_cn": "数据分析",
    "min_wage": 8000,
    "max_wage": 12000,
    "wage_unit_cn": "元/月",
    "is_negotiable": False,
    "education_cn": "本科",
    "experience_cn": "应届生",
    "district_list": [{"area_cn": "北京-朝阳区"}],
    "contents": "【岗位职责】负责数据报表开发与业务分析。<span>本科及以上</span>",
    "start_time": "2026-08-21 20:00:00",
}

NOWCODER_ITEM = {
    "id": 450101,
    "jobName": "数据分析-实习（J14768）",
    "recruitType": 2,
    "jobCity": "北京",
    "jobCityList": ["北京"],
    "salaryType": 1,
    "salaryMin": 220,
    "salaryMax": 250,
    "salaryMonth": 0,
    "eduLevel": 5000,
    "industryName": "企业服务",
    "refreshTime": 1787316388000,
    "user": {"identity": [{"companyName": "慧策（掌上先机）"}]},
    "ext": json.dumps({
        "infos": "【公司亮点】专注ToB SaaS业务。",
        "requirements": "本科及以上在读，每周至少实习3天，有数据分析经验者优先。",
    }, ensure_ascii=False),
}


# ---------------- 国聘 ----------------
class TestIguopinTransform:
    def test_字段映射完整(self):
        r = iguopin_row(0, IGUOPIN_ITEM, CRAWL_DATE)
        assert r["job_id"] == "iguopin_214746080682968399"
        assert r["job_title"] == "数据分析师（校招）"
        assert r["job_type"] == "校招"
        assert r["company_name"] == "河北省物流产业集团有限公司"
        assert r["city"] == "北京"
        assert r["experience_req"] == "1年以内"      # 应届生 → 1年以内
        assert r["education_req"] == "本科"
        assert r["url"].startswith("https://www.iguopin.com/job/detail?id=")
        assert r["source"] == "iguopin"
        assert r["post_date"].isoformat() == "2026-08-21"

    def test_薪资元每月(self):
        r = iguopin_row(0, IGUOPIN_ITEM, CRAWL_DATE)
        assert r["salary_raw"] == "8000-12000"
        assert r["salary_min"] == 8000
        assert r["salary_max"] == 12000
        assert r["salary_avg"] == 10000
        assert r["is_valid"] == 1

    def test_日薪换算(self):
        item = dict(IGUOPIN_ITEM)
        item.update({"min_wage": 200, "max_wage": 250, "wage_unit_cn": "元/天"})
        r = iguopin_row(0, item, CRAWL_DATE)
        assert r["salary_raw"] == "200-250元/天"
        assert r["salary_min"] == 200 * 21.75  # 校招非实习 → 21.75
        assert r["is_valid"] == 1

    def test_面议薪资保留记录(self):
        item = dict(IGUOPIN_ITEM, is_negotiable=True)
        r = iguopin_row(0, item, CRAWL_DATE)
        assert r["salary_raw"] == ""
        assert r["salary_min"] is None
        assert r["is_valid"] == 1  # 面议不算异常，保留（规则 5）

    def test_非白名单城市仍有效(self):
        # 国聘为国企央企、岗位遍布全国：城市口径放宽为"可解析即有效"
        item = dict(IGUOPIN_ITEM)
        item["district_list"] = [{"area_cn": "石家庄-正定县"}]
        r = iguopin_row(0, item, CRAWL_DATE)
        assert r["city"] == "石家庄"
        assert r["is_valid"] == 1

    def test_城市缺失无效(self):
        item = dict(IGUOPIN_ITEM)
        item["district_list"] = []
        r = iguopin_row(0, item, CRAWL_DATE)
        assert r["is_valid"] == 0

    def test_薪资脏数据不抛异常(self):
        # 上游字段类型漂移（字符串）→ 面议而非中断整批
        item = dict(IGUOPIN_ITEM)
        item.update({"min_wage": "未知", "max_wage": "未知"})
        r = iguopin_row(0, item, CRAWL_DATE)
        assert r["salary_min"] is None
        assert r["is_valid"] == 1

    def test_城市脏数据兜底(self):
        # district_list 元素非 dict（字符串）→ 直接取文本首段
        item = dict(IGUOPIN_ITEM)
        item["district_list"] = ["苏州-吴中区"]
        r = iguopin_row(0, item, CRAWL_DATE)
        assert r["city"] == "苏州"

    def test_区县城市提取(self):
        item = dict(IGUOPIN_ITEM)
        item["district_list"] = [{"area_cn": "上海"}]
        r = iguopin_row(0, item, CRAWL_DATE)
        assert r["city"] == "上海"


# ---------------- 牛客 ----------------
class TestNowcoderTransform:
    def test_字段映射完整(self):
        r = nowcoder_row(0, NOWCODER_ITEM, CRAWL_DATE)
        assert r["job_id"] == "nowcoder_450101"
        assert r["job_title"] == "数据分析-实习（J14768）"
        assert r["job_type"] == "实习"
        assert r["company_name"] == "慧策（掌上先机）"
        assert r["industry"] == "企业服务"
        assert r["city"] == "北京"
        assert r["url"].startswith("https://www.nowcoder.com/jobs/detail/")
        assert r["source"] == "nowcoder"

    def test_实习日薪换算(self):
        r = nowcoder_row(0, NOWCODER_ITEM, CRAWL_DATE)
        assert r["salary_raw"] == "220-250元/天"
        assert r["salary_min"] == 220 * 20      # 实习 ×20（规则 7）
        assert r["salary_max"] == 250 * 20
        assert r["is_valid"] == 1

    def test_千元区间含薪数(self):
        item = dict(NOWCODER_ITEM)
        item.update({"recruitType": 3, "salaryType": 2, "salaryMin": 20,
                     "salaryMax": 30, "salaryMonth": 15})
        r = nowcoder_row(0, item, CRAWL_DATE)
        assert r["salary_raw"] == "20-30K·15薪"
        assert r["salary_min"] == 20000 * 12 / 15
        assert r["job_type"] == "社招"

    def test_元每月区间(self):
        item = dict(NOWCODER_ITEM)
        item.update({"recruitType": 3, "salaryType": 2, "salaryMin": 17000,
                     "salaryMax": 28000, "salaryMonth": 12})
        r = nowcoder_row(0, item, CRAWL_DATE)
        assert r["salary_min"] == 17000
        assert r["salary_max"] == 28000

    def test_面议未知薪资(self):
        item = dict(NOWCODER_ITEM)
        item.update({"salaryMin": 0, "salaryMax": 9999999})
        r = nowcoder_row(0, item, CRAWL_DATE)
        assert r["salary_min"] is None
        assert r["is_valid"] == 1

    def test_学历从文本解析(self):
        item = dict(NOWCODER_ITEM)
        item["ext"] = json.dumps({
            "infos": "",
            "requirements": "硕士研究生及以上学历，熟悉SQL与Python。",
        }, ensure_ascii=False)
        r = nowcoder_row(0, item, CRAWL_DATE)
        assert r["education_req"] == "硕士"

    def test_无公司名兜底(self):
        item = dict(NOWCODER_ITEM)
        item["user"] = {"identity": []}
        r = nowcoder_row(0, item, CRAWL_DATE)
        assert r["company_name"] == "未知公司"

    def test_薪资脏数据不抛异常(self):
        # 上游字段类型漂移（字符串）→ 面议而非中断整批
        item = dict(NOWCODER_ITEM)
        item.update({"salaryMin": "未知", "salaryMax": "未知"})
        r = nowcoder_row(0, item, CRAWL_DATE)
        assert r["salary_min"] is None
        assert r["is_valid"] == 1

    def test_元每月含薪数折算(self):
        # 17000-28000 元/月·13薪 → 月薪 = 数值×12/13（与 parse_salary 规则 1/4 同口径）
        item = dict(NOWCODER_ITEM)
        item.update({"recruitType": 3, "salaryType": 2, "salaryMin": 17000,
                     "salaryMax": 28000, "salaryMonth": 13})
        r = nowcoder_row(0, item, CRAWL_DATE)
        assert r["salary_min"] == round(17000 * 12 / 13)
        assert r["salary_max"] == round(28000 * 12 / 13)
        assert r["salary_raw"] == "17000-28000元·13薪"


# ---------------- 请求构造与容错 ----------------
class FakeResponse:
    """模拟 requests.Response。"""

    def __init__(self, status_code=200, url="", payload=None):
        self.status_code = status_code
        self.url = url
        self._payload = payload

    def json(self):
        return self._payload


class TestFetchPage:
    def test_iguopin请求构造(self, monkeypatch):
        captured = {}

        def fake_request(url, method, headers, json, timeout):
            captured["url"] = url
            captured["json"] = json
            assert method == "POST"
            assert json == {"page": 1, "page_size": 50, "job_name": "数据分析"}
            assert headers["Origin"] == "https://www.iguopin.com"
            return FakeResponse(200, url, {"code": 200, "data": {"list": [IGUOPIN_ITEM]}})

        monkeypatch.setattr("market.crawler.iguopin.request_with_retry", fake_request)
        monkeypatch.setattr("market.crawler.iguopin.random_delay", lambda a, b: None)
        adapter = IguopinAdapter(keywords=["数据分析"], page_size=50, max_pages=1,
                                 delay_min=0, delay_max=0)
        items = adapter.fetch_page("数据分析", 1)
        assert len(items) == 1
        assert items[0]["job_id"] == IGUOPIN_ITEM["job_id"]

    def test_nowcoder请求构造(self, monkeypatch):
        captured = {}

        def fake_request(url, method, headers, data, timeout):
            captured["url"] = url
            captured["data"] = data
            assert method == "POST"
            assert data == {"page": 1, "pageSize": 20, "query": "数据分析"}
            assert headers["Origin"] == "https://www.nowcoder.com"
            return FakeResponse(200, url, {"code": 0, "data": {"datas": [NOWCODER_ITEM]}})

        monkeypatch.setattr("market.crawler.nowcoder.request_with_retry", fake_request)
        monkeypatch.setattr("market.crawler.nowcoder.random_delay", lambda a, b: None)
        adapter = NowcoderAdapter(keywords=["数据分析"], page_size=20, max_pages=1,
                                  delay_min=0, delay_max=0)
        items = adapter.fetch_page("数据分析", 1)
        assert len(items) == 1
        assert items[0]["id"] == NOWCODER_ITEM["id"]

    def test_iguopin接口异常码抛Blocked(self, monkeypatch):
        def fake_request(url, method, headers, json, timeout):
            return FakeResponse(200, url, {"code": 500, "msg": "服务繁忙"})

        monkeypatch.setattr("market.crawler.iguopin.request_with_retry", fake_request)
        monkeypatch.setattr("market.crawler.iguopin.random_delay", lambda a, b: None)
        adapter = IguopinAdapter(keywords=["数据分析"], delay_min=0, delay_max=0)
        from market.crawler.http import BlockedError
        with pytest.raises(BlockedError):
            adapter.fetch_page("数据分析", 1)

    def test_iguopin迭代去重与翻页停止(self, monkeypatch):
        calls = []

        def fake_fetch(kw, page):
            calls.append((kw, page))
            if page == 1:
                return [IGUOPIN_ITEM]
            return []

        adapter = IguopinAdapter(keywords=["数据分析", "数据分析"], max_pages=3,
                                 delay_min=0, delay_max=0)
        monkeypatch.setattr(adapter, "fetch_page", fake_fetch)
        rows = list(adapter.iter_rows(CRAWL_DATE))
        assert len(rows) == 1
        assert calls == [("数据分析", 1)]  # 去重 + 空页停止

    def test_iguopin主题过滤非数据标题(self, monkeypatch):
        noisy = dict(IGUOPIN_ITEM)
        noisy["job_name"] = "业务员-河北捷宗进出口有限公司"  # 标题不含数据关键词

        def fake_fetch(kw, page):
            return [noisy, IGUOPIN_ITEM]

        adapter = IguopinAdapter(keywords=["数据分析"], max_pages=1,
                                 delay_min=0, delay_max=0)
        monkeypatch.setattr(adapter, "fetch_page", fake_fetch)
        rows = list(adapter.iter_rows(CRAWL_DATE))
        assert len(rows) == 1                     # 噪声标题被过滤
        assert rows[0]["job_title"] == IGUOPIN_ITEM["job_name"]


# ---------------- 聚合筛选 ----------------
class TestSourceFilter:
    def test_filter_records按source(self):
        records = [
            {"c": "北京", "g": "数据分析", "e": "本科", "s": 10000, "sk": [], "src": "backup"},
            {"c": "北京", "g": "数据分析", "e": "本科", "s": 12000, "sk": [], "src": "nowcoder"},
            {"c": "上海", "g": "算法", "e": "硕士", "s": 20000, "sk": [], "src": "iguopin"},
        ]
        out = stats_mod.filter_records(records, source="nowcoder")
        assert len(out) == 1 and out[0]["src"] == "nowcoder"
        out2 = stats_mod.filter_records(records, city="北京")
        assert len(out2) == 2
        out3 = stats_mod.filter_records(records, source="iguopin", city="上海")
        assert len(out3) == 1


# ---------------- pipeline 容错 ----------------
class TestPipelineFaultTolerance:
    def test_实时源网络异常不中断(self, monkeypatch):
        """实时源采集网络异常 → 返回 warnings，不向上抛异常。"""
        from market.crawler import pipeline as pipeline_mod
        from market.crawler.pipeline import run_crawl
        from market.config import load_config
        import requests

        class _FailingAdapter:
            source_id = "iguopin"

            def iter_rows(self, crawl_date=None):
                raise requests.ConnectionError("network down")

        monkeypatch.setattr(pipeline_mod, "get_adapter",
                            lambda src, cfg: _FailingAdapter())
        result = run_crawl(load_config(), source="iguopin",
                           crawl_date=datetime(2026, 2, 1, 12, 0, 0))
        assert result.jobs_total == 0
        assert result.warnings and "采集失败" in result.warnings[0]

    def test_实时源脏数据不中断整批(self, monkeypatch):
        """单条脏数据（int 转换失败）→ 置空薪资，其余照常产出。"""
        from market.crawler import pipeline as pipeline_mod
        from market.crawler.pipeline import run_crawl
        from market.config import load_config

        class _AdapterWithDirty:
            source_id = "iguopin"

            def iter_rows(self, crawl_date=None):
                yield nowcoder_row(0, NOWCODER_ITEM, crawl_date)     # 正常
                dirty = dict(NOWCODER_ITEM)
                dirty.update({"salaryMin": "oops"})
                yield nowcoder_row(1, dirty, crawl_date)             # 脏薪资
                yield nowcoder_row(2, NOWCODER_ITEM, crawl_date)

        monkeypatch.setattr(pipeline_mod, "get_adapter",
                            lambda src, cfg: _AdapterWithDirty())
        # run_crawl 会尝试写库；异常发生在 iter_rows 阶段之前已全部产出，
        # 用 monkeypatch 跳过实际 DB 写入
        monkeypatch.setattr(pipeline_mod, "upsert_jobs",
                            lambda jobs, cfg: len(jobs))
        monkeypatch.setattr(pipeline_mod, "insert_snapshots",
                            lambda snaps, cfg: len(snaps))
        result = run_crawl(load_config(), source="nowcoder",
                           crawl_date=datetime(2026, 2, 1, 12, 0, 0))
        assert result.jobs_total == 3
        assert not result.warnings
