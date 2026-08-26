"""ICP 备案反查模块单测：未配置降级、真实响应形状解析、SQLite 缓存（fetch_json 全部 mock）。"""
from app.fetcher import icp as icp_mod


def test_lookup_not_configured_returns_none(monkeypatch):
    monkeypatch.delenv("ICP_API_URL", raising=False)
    assert icp_mod.available() is False
    assert icp_mod.lookup("某公司") is None


def test_lookup_parses_standard_response_and_caches(app_db, monkeypatch):
    """ICP_Query 标准响应 {code, params:{list:[{serviceName,...}]}} → 提取域名并缓存。"""
    monkeypatch.setenv("ICP_API_URL", "http://127.0.0.1:16181")
    calls = []

    def fake_fetch_json(url, deadline=None):
        calls.append(url)
        assert url.startswith("http://127.0.0.1:16181/query/web?search=")
        return {"code": 200, "params": {"list": [
            {"serviceName": "moucompany.com", "unitName": "某公司", "nature": "企业"},
        ]}}

    monkeypatch.setattr(icp_mod, "fetch_json", fake_fetch_json)
    result = icp_mod.lookup("某公司")
    assert result == {"name": None, "domain": "moucompany.com", "website": "https://moucompany.com"}
    assert len(calls) == 1
    # 第二次命中缓存，不再发请求
    assert icp_mod.lookup("某公司")["website"] == "https://moucompany.com"
    assert len(calls) == 1


def test_lookup_skips_date_like_and_finds_domain(app_db, monkeypatch):
    """域名嗅探应跳过日期/许可证号等非域名值，命中真实域名。"""
    monkeypatch.setenv("ICP_API_URL", "http://127.0.0.1:16181")
    monkeypatch.setattr(icp_mod, "fetch_json",
                        lambda url, deadline=None: {"code": 200, "params": {"list": [
                            {"serviceLicence": "京ICP备2024000000号-1", "recordDate": "2024-01-01",
                             "unitName": "某公司", "serviceName": "www.example.com.cn"},
                        ]}})
    result = icp_mod.lookup("某公司")
    assert result["website"] == "https://www.example.com.cn"


def test_lookup_no_record_cached(app_db, monkeypatch):
    monkeypatch.setenv("ICP_API_URL", "http://127.0.0.1:16181")
    calls = []

    def fake_fetch_json(url, deadline=None):
        calls.append(url)
        return {"code": 404, "params": {"list": []}}

    monkeypatch.setattr(icp_mod, "fetch_json", fake_fetch_json)
    assert icp_mod.lookup("某公司") is None
    assert icp_mod.lookup("某公司") is None  # 无记录也缓存，不重复请求
    assert len(calls) == 1


def test_lookup_fetch_failure_degrades(app_db, monkeypatch):
    monkeypatch.setenv("ICP_API_URL", "http://127.0.0.1:16181")
    monkeypatch.setattr(icp_mod, "fetch_json",
                        lambda url, deadline=None: (_ for _ in ()).throw(RuntimeError("服务不可达")))
    assert icp_mod.lookup("某公司") is None
