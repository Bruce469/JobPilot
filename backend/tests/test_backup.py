"""备份导出/导入单测：merge 同 id 以本机为准；overwrite 悬空引用置空。"""
from app.dao import create_company, create_job, get_job
from app.services import export_backup, import_backup


def test_export_contains_collections(app_db):
    company = create_company({"name": "A公司", "website": "https://a.com"})
    create_job({"company": "A公司", "company_id": company["id"], "position": "后端"})
    data = export_backup()
    assert data["schema_version"] >= 1
    assert len(data["jobs"]) == 1 and len(data["companies"]) == 1
    assert isinstance(data["exported_at"], str)


def test_merge_same_id_keeps_local(app_db):
    company = create_company({"name": "A公司", "website": "https://a.com"})
    job = create_job({"company": "A公司", "company_id": company["id"], "position": "后端"})
    backup = export_backup()
    # 备份中同 id 记录：以本机为准跳过
    res = import_backup({"schema_version": 1, "mode": "merge",
                         "jobs": backup["jobs"], "companies": backup["companies"],
                         "resumes": backup["resumes"]})
    assert res["jobs_skipped"] == 1 and res["companies_added"] == 0
    assert get_job(job["id"])["position"] == "后端"


def test_merge_company_name_conflict_not_crash(app_db):
    create_company({"name": "同名公司", "website": "https://local.com"})
    # 备份公司 id 不同但 name 相同 → 跳过并记入 errors，不 500
    res = import_backup({"schema_version": 1, "mode": "merge",
                         "companies": [{"id": "c-other", "name": "同名公司", "website": "https://backup.com"}],
                         "jobs": [], "resumes": []})
    assert res["companies_added"] == 0
    assert res["errors"] and res["errors"][0]["id"] == "c-other"


def test_overwrite_dangling_refs_nulled(app_db):
    create_company({"name": "A公司", "website": "https://a.com"})
    create_job({"company": "A公司", "position": "将被替换"})
    # 备份岗位引用了备份内不存在的公司/简历 → 置空而不外键报错
    res = import_backup({"schema_version": 1, "mode": "overwrite",
                         "jobs": [{"id": "j-dangling", "company": "B公司",
                                   "company_id": "c-missing", "resume_id": "r-missing",
                                   "position": "后端"}],
                         "companies": [], "resumes": []})
    assert res["jobs_added"] == 1
    row = get_job("j-dangling")
    assert row["company_id"] is None and row["resume_id"] is None


def test_overwrite_replaces_all(app_db):
    create_company({"name": "A公司", "website": "https://a.com"})
    create_job({"company": "A公司", "position": "旧岗位"})
    import_backup({"schema_version": 1, "mode": "overwrite",
                   "jobs": [{"id": "j1", "company": "B公司", "position": "新岗位"}],
                   "companies": [{"id": "c1", "name": "B公司", "website": "https://b.com"}],
                   "resumes": []})
    from app.dao import all_jobs, list_companies
    assert [j["id"] for j in all_jobs()] == ["j1"]
    assert list_companies()[0]["name"] == "B公司"
