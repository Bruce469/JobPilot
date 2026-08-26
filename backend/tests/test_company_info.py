"""A股上市公司离线库（company_info）单测：别名/归一化查找、空索引优雅降级。"""
from app.fetcher import company_info


def test_lookup_empty_index_returns_none():
    """索引为空（未构建/被隔离）→ lookup 恒 None，不抛错。"""
    assert company_info.lookup("平安银行") is None
    assert company_info.lookup("") is None


def test_lookup_with_injected_index(monkeypatch):
    monkeypatch.setattr(company_info, "_INDEX", {
        "平安银行": {"name": "平安银行", "website": "https://bank.pingan.com",
                     "industry": "金融", "city": "深圳", "nature": None},
        "宁德时代": {"name": "宁德时代", "website": "https://www.catl.com",
                     "industry": "能源", "city": "宁德", "nature": None},
    })
    # 简称 / 全称（归一化去「股份/有限公司」后缀）都能命中
    e = company_info.lookup("平安银行")
    assert e["website"] == "https://bank.pingan.com"
    e2 = company_info.lookup("平安银行股份有限公司")
    assert e2["website"] == "https://bank.pingan.com"
    e3 = company_info.lookup("宁德时代有限公司")
    assert e3["industry"] == "能源"
    assert company_info.lookup("某不存在公司") is None
    assert company_info.lookup("") is None
