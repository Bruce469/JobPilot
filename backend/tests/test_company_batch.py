"""公司库批量操作单测：批量删除（解绑岗位）+ 批量补全任务 + 批量任务提交。"""
import pytest

from app import dao, services
from app.fetcher import tasks as fetcher_tasks


# ---------------- 批量删除 ----------------

def test_batch_delete_unlinks_jobs(app_db):
    c1 = dao.create_company({"name": "甲公司", "website": "https://a.example.com"})
    c2 = dao.create_company({"name": "乙公司", "website": "https://b.example.com"})
    j1 = dao.create_job({"company": "甲公司", "company_id": c1["id"], "position": "后端"})
    j2 = dao.create_job({"company": "甲公司", "company_id": c1["id"], "position": "前端"})
    j3 = dao.create_job({"company": "乙公司", "company_id": c2["id"], "position": "测试"})

    deleted = services.batch_delete_companies([c1["id"], c2["id"]])

    assert deleted == 2
    assert dao.get_company(c1["id"]) is None
    assert dao.get_company(c2["id"]) is None
    # 岗位保留，仅解除关联
    jobs = [dao.get_job(x) for x in (j1["id"], j2["id"], j3["id"])]
    assert all(j is not None and j["company_id"] is None for j in jobs)


def test_batch_delete_empty_ids(app_db):
    assert services.batch_delete_companies([]) == 0


def test_batch_delete_missing_ids_safe(app_db):
    c = dao.create_company({"name": "甲公司", "website": "https://a.example.com"})
    assert services.batch_delete_companies(["no-such-id", c["id"]]) == 1
    assert dao.get_company(c["id"]) is None


def test_resolve_batch_skips_complete_company(app_db, monkeypatch):
    c1 = dao.create_company({"name": "甲公司", "website": "https://a.example.com",
                             "industry": "互联网", "career_url": "https://a.example.com/careers"})
    c2 = dao.create_company({"name": "乙公司", "website": ""})
    from app.fetcher import probe as probe_mod
    monkeypatch.setattr(probe_mod, "probe_company",
                        lambda website, deadline=None: ([], None, None))
    from app.fetcher import resolve as resolve_mod
    monkeypatch.setattr(resolve_mod, "search_fallback",
                        lambda name, deadline=None: (None, None))
    task = {"progress": ""}
    result = fetcher_tasks._run_resolve({"company_ids": [c1["id"], c2["id"]]}, None, task)
    assert result["resolved"] == 0 and result["skipped"] == 1
    assert result["results"][0]["source"] == "skipped"
    assert result["results"][1]["source"] == "failed"


def test_task_get_includes_queue_length(app_db):
    fetcher_tasks.submit("resolve", {"company_ids": ["c1"]})
    job_id = fetcher_tasks.submit("resolve", {"company_ids": ["c2"]})
    task = fetcher_tasks.get(job_id)
    assert task is not None
    assert task["queue_length"] == 2  # 两个任务都还在排队


# ---------------- 批量任务提交（services） ----------------

def test_submit_batch_resolve_empty_ids(app_db):
    from app.errors import APIError
    with pytest.raises(APIError) as exc_info:
        services.submit_batch_resolve([])
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_submit_batch_resolve_queues_task(app_db):
    job_id = services.submit_batch_resolve(["c1"])
    task = fetcher_tasks.get(job_id)
    assert task is not None
    assert task["type"] == "resolve"
    assert task["status"] == "queued"
