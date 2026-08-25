"""导入去重单测：source_job_id 优先 + 规范化岗位名+city。"""
from app.dao import create_company
from app.services import import_jobs


def test_import_dedupe(app_db):
    company = create_company({"name": "示例科技", "website": "https://example.com"})
    res = import_jobs(company["id"], [
        {"position": "算法工程师", "city": "北京", "source_job_id": "a1"},
        {"position": "算法工程师", "city": "北京", "source_job_id": "a1"},      # source_job_id 重复
        {"position": "前端开发", "city": "上海"},
        {"position": "【2026秋招】前端开发", "city": "上海"},                    # 规范化后重复
        {"position": "", "city": "北京"},                                       # 缺岗位名
    ])
    assert res["added"] == 2 and res["skipped"] == 2 and res["failed"] == 1
    assert len(res["added_ids"]) == 2


def test_import_second_run_skips_all(app_db):
    company = create_company({"name": "示例科技", "website": "https://example.com"})
    items = [{"position": "后端开发", "city": "北京", "source_job_id": "b1"}]
    res1 = import_jobs(company["id"], items)
    assert res1["added"] == 1 and res1["skipped"] == 0
    res2 = import_jobs(company["id"], items)
    assert res2["added"] == 0 and res2["skipped"] == 1   # 幂等，不重复写入


def test_import_company_required(app_db):
    company = create_company({"name": "示例科技", "website": "https://example.com"})
    res = import_jobs(company["id"], [{"position": "岗位A", "city": "北京"}])
    assert res["added"] == 1
    job = res["added_ids"][0]
    from app.dao import get_job
    row = get_job(job)
    assert row["company"] == "示例科技"
    assert row["company_id"] == company["id"]
    assert row["channel"] == "官网"
    assert row["status"] == "待投递"
