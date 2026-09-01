"""公司批量导入单测（PRD 4.12 v0.6）：去空行、批内去重、跳过已存在（归一化）。"""
import pytest

from app.dao import create_company
from app.errors import APIError
from app.services import import_companies


def test_import_skip_existing_and_inbatch_dups(app_db):
    create_company({"name": "字节跳动", "website": "https://x.com"})
    result = import_companies(["字节跳动", "字节跳动有限公司", "美团", " 美团 ", "", "腾讯"])
    assert result["added"] == 2              # 美团、腾讯
    assert result["skipped"] == 3            # 字节跳动（已存在）、字节跳动有限公司（批内归一化重名）、美团（重复）
    assert set(result["skipped_names"]) == {"字节跳动", "字节跳动有限公司", "美团"}
    assert len(result["added_ids"]) == 2
    assert "job_id" not in result


def test_import_creates_with_empty_website(app_db):
    result = import_companies(["美团"])
    assert result["added"] == 1
    from app.dao import get_company
    company = get_company(result["added_ids"][0])
    assert company["name"] == "美团"
    assert company["website"] == ""           # 待补全，防错配不自动写入
    assert company["probe_status"] == "未探测"


def test_import_resolve_true_returns_job_id(app_db):
    result = import_companies(["蚂蚁集团"], resolve=True)
    assert result["added"] == 1
    assert result["job_id"]
    # 已存在的公司不产生补全任务
    result2 = import_companies(["蚂蚁集团"], resolve=True)
    assert result2["added"] == 0
    assert "job_id" not in result2


def test_import_all_blank_raises(app_db):
    with pytest.raises(APIError) as exc_info:
        import_companies(["  ", "", " ", ""])
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_import_idempotent_second_run_skips_all(app_db):
    result = import_companies(["腾讯", "美团"])
    assert result["added"] == 2
    result2 = import_companies(["腾讯", "美团"])
    assert result2["added"] == 0 and result2["skipped"] == 2


def test_import_structured_rows_with_fields(app_db):
    """结构化导入：名称+城市/行业/性质/官网 一并落库。"""
    rows = [
        {"name": "字节跳动", "city": "北京", "industry": "互联网", "nature": "民营企业",
         "website": "https://www.bytedance.com"},
        {"name": "国家电网", "city": "北京", "industry": "能源", "nature": "国企", "website": ""},
    ]
    result = import_companies(rows)
    assert result["added"] == 2
    from app.dao import get_company
    bytedance = get_company(result["added_ids"][0])
    assert bytedance["city"] == "北京"
    assert bytedance["industry"] == "互联网"
    assert bytedance["nature"] == "民营企业"
    assert bytedance["website"] == "https://www.bytedance.com"
    grid = get_company(result["added_ids"][1])
    assert grid["nature"] == "国企"
    assert grid["website"] == ""


def test_import_structured_placeholder_values_become_empty(app_db):
    """占位内容（官网未公开 / 无 / - 等）导入时置空。"""
    rows = [
        {"name": "某公司", "city": "官网未公开", "industry": "无", "nature": "-", "website": "未知"},
        {"name": "  空格公司  ", "city": None, "industry": "", "nature": "/", "website": "N/A"},
    ]
    result = import_companies(rows)
    assert result["added"] == 2
    from app.dao import get_company
    for cid in result["added_ids"]:
        company = get_company(cid)
        assert company["city"] is None
        assert company["industry"] is None
        assert company["nature"] is None
        assert company["website"] == ""
