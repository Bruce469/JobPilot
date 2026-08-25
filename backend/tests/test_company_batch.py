"""公司库批量操作单测：批量删除（解绑岗位）+ 批量探测任务 + 批量任务提交。

探测通过 monkeypatch 注入，不访问真实网络。
"""
import pytest

from app import dao, services
from app.fetcher import probe as probe_mod
from app.fetcher import tasks as fetcher_tasks
from app.fetcher.tasks import _run_probe_batch


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


# ---------------- 批量探测任务（_run_probe_batch） ----------------

def _company(name, website="https://x.example.com", **kw):
    data = {"name": name, "website": website}
    data.update(kw)
    return dao.create_company(data)


def test_probe_batch_all_success(app_db, monkeypatch):
    c1 = _company("甲公司")
    c2 = _company("乙公司")

    def fake_probe(website, deadline=None):
        return ([{"url": f"{website}/careers", "confidence": "high", "source": "link", "reason": ""}], None, None)

    monkeypatch.setattr(probe_mod, "probe_company", fake_probe)
    task = {"progress": ""}
    result = _run_probe_batch({"company_ids": [c1["id"], c2["id"]]}, None, task)

    assert result["ok"] == 2 and result["manual"] == 0 and result["failed"] == 0
    assert all(r["status"] == "成功" for r in result["results"])
    assert dao.get_company(c1["id"])["probe_status"] == "成功"
    assert dao.get_company(c1["id"])["career_url"] == "https://x.example.com/careers"
    assert task["progress"] == "已探测 2/2"


def test_probe_batch_no_candidates_manual(app_db, monkeypatch):
    c = _company("甲公司")
    monkeypatch.setattr(probe_mod, "probe_company", lambda website, deadline=None: ([], None, None))
    result = _run_probe_batch({"company_ids": [c["id"]]}, None, {})
    assert result["ok"] == 0 and result["manual"] == 1 and result["failed"] == 0
    assert result["results"][0]["status"] == "需人工"
    assert dao.get_company(c["id"])["probe_status"] == "需人工"
    assert dao.get_company(c["id"])["career_url"] is None


def test_probe_batch_keeps_existing_career_url(app_db, monkeypatch):
    c = _company("甲公司", career_url="https://manual.example.com/careers")
    monkeypatch.setattr(probe_mod, "probe_company",
                        lambda website, deadline=None: ([{"url": "https://auto.example.com", "confidence": "high", "source": "link", "reason": ""}], None, None))
    _run_probe_batch({"company_ids": [c["id"]]}, None, {})
    assert dao.get_company(c["id"])["career_url"] == "https://manual.example.com/careers"


def test_probe_batch_missing_company(app_db):
    result = _run_probe_batch({"company_ids": ["no-such-id"]}, None, {})
    assert result["failed"] == 1
    assert result["results"][0]["error"] == "公司不存在"
    assert result["results"][0]["name"] is None


def test_probe_batch_exception_isolated(app_db, monkeypatch):
    c1 = _company("甲公司")
    c2 = _company("乙公司", website="https://y.example.com")

    def fake_probe(website, deadline=None):
        if website == c1["website"]:
            raise RuntimeError("boom")
        return ([{"url": f"{website}/careers", "confidence": "high", "source": "link", "reason": ""}], None, None)

    monkeypatch.setattr(probe_mod, "probe_company", fake_probe)
    result = _run_probe_batch({"company_ids": [c1["id"], c2["id"]]}, None, {})
    assert result["ok"] == 1 and result["failed"] == 1
    assert result["results"][0]["status"] == "failed" and "boom" in result["results"][0]["error"]
    assert result["results"][1]["status"] == "成功"
    # 失败的公司标记为需人工
    assert dao.get_company(c1["id"])["probe_status"] == "需人工"
    assert dao.get_company(c2["id"])["probe_status"] == "成功"


def test_probe_batch_progress_text(app_db, monkeypatch):
    c1 = _company("甲公司")
    c2 = _company("乙公司")
    c3 = _company("丙公司")
    monkeypatch.setattr(probe_mod, "probe_company", lambda website, deadline=None: ([], None, None))
    task = {"progress": ""}
    _run_probe_batch({"company_ids": [c1["id"], c2["id"], c3["id"]]}, None, task)
    assert task["progress"] == "已探测 3/3"


def test_probe_batch_skips_already_success(app_db, monkeypatch):
    c1 = _company("甲公司", probe_status="成功", career_url="https://x.example.com/careers")
    c2 = _company("乙公司")
    calls = []

    def fake_probe(website, deadline=None):
        calls.append(website)
        return ([], None, None)

    monkeypatch.setattr(probe_mod, "probe_company", fake_probe)
    result = _run_probe_batch({"company_ids": [c1["id"], c2["id"]]}, None, {})
    assert result["skipped"] == 1 and result["manual"] == 1 and result["ok"] == 0
    assert result["results"][0]["status"] == "skipped"
    assert calls == [c2["website"]]  # 已探测成功的公司不再发请求


def test_resolve_batch_skips_complete_company(app_db, monkeypatch):
    c1 = dao.create_company({"name": "甲公司", "website": "https://a.example.com",
                             "industry": "互联网", "career_url": "https://a.example.com/careers"})
    c2 = dao.create_company({"name": "乙公司", "website": ""})
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

def test_submit_batch_probe_empty_ids(app_db):
    from app.errors import APIError
    with pytest.raises(APIError) as exc_info:
        services.submit_batch_probe([])
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_submit_batch_probe_queues_task(app_db):
    job_id = services.submit_batch_probe(["c1"])
    task = fetcher_tasks.get(job_id)
    assert task is not None
    assert task["type"] == "probe_batch"
    assert task["status"] == "queued"


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
