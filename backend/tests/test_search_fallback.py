"""Bing 搜索兜底单测：黑名单过滤 + 官网首页公司名校验（全部 mock，不访问真实网络）。

回归背景：Bing 对长中文公司名存在搜索碎片化，旧逻辑取首个非黑名单结果，
会把知乎专栏/政府网站/字典等错误页面当作官网写入公司库。
"""
from app.fetcher import resolve as resolve_mod


def _bing_html(*items):
    """构造 Bing 搜索结果 HTML，items 为 (href, title, snippet) 三元组。"""
    lis = []
    for href, title, snippet in items:
        cap = f'<div class="b_caption">{snippet}</div>' if snippet else ""
        lis.append(
            f'<li class="b_algo"><h2><a href="{href}">{title}</a></h2>{cap}</li>'
        )
    return f'<html><ol>{"".join(lis)}</ol></html>'


def test_skips_excluded_domains_and_verifies_official_site(monkeypatch):
    """知乎结果被黑名单排除且不被抓取；官方站首页包含公司名才被接受。"""
    calls = []

    def fake_fetch_text(url, deadline=None):
        calls.append(url)
        if "bing.com/search" in url:
            return _bing_html(
                ("https://zhuanlan.zhihu.com/p/123", "如何看待成都农商银行", "避坑"),
                ("https://www.cdrcb.com/", "成都农商银行", "银行存贷款业务"),
            )
        if "cdrcb.com" in url:
            return "<html><head><title>成都农村商业银行股份有限公司</title></head>" \
                   "<body>欢迎访问成都农村商业银行股份有限公司官网</body></html>"
        raise AssertionError(f"不应请求被排除域名: {url}")

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    website, industry = resolve_mod.search_fallback("成都农村商业银行股份有限公司")
    assert website == "https://www.cdrcb.com"
    assert industry == "金融"
    assert not any("zhihu.com" in u for u in calls)


def test_rejects_unverified_candidate_then_fails(monkeypatch):
    """候选首页不含公司名核心串 → 拒绝；全部拒绝 → (None, None)。"""
    def fake_fetch_text(url, deadline=None):
        if "bing.com/search" in url:
            return _bing_html(
                ("https://www.other1.com/", "某未知公司X 介绍", ""),
                ("https://www.other2.com/", "某未知公司X 新闻", ""),
            )
        return "<html><head><title>完全无关的网站</title></head><body>完全无关的内容</body></html>"

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    assert resolve_mod.search_fallback("某未知公司X") == (None, None)


def test_all_results_excluded_fails_without_fetching(monkeypatch):
    """结果全是被排除域名 → 失败，且不抓取任何候选首页。"""
    calls = []

    def fake_fetch_text(url, deadline=None):
        calls.append(url)
        if "bing.com/search" in url:
            return _bing_html(
                ("https://zhuanlan.zhihu.com/p/1", "成都 旅游", ""),
                ("https://www.sc.gov.cn/", "四川省人民政府", ""),
                ("https://www.hanyuguoxue.com/", "蓝 的意思", ""),
            )
        raise AssertionError(f"不应请求被排除域名: {url}")

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    assert resolve_mod.search_fallback("蓝润集团有限公司") == (None, None)
    # 完整名与去后缀名两种查询都会尝试，但不会抓取任何被排除域名的首页
    assert calls and all("bing.com" in u for u in calls)


def test_industry_matched_from_verified_homepage(monkeypatch):
    """摘要未命中行业时，从通过校验的官网首页文本匹配。"""
    def fake_fetch_text(url, deadline=None):
        if "bing.com/search" in url:
            return _bing_html(
                ("https://www.chipco.com/", "某半导体公司", "欢迎访问"),
            )
        if "chipco.com" in url:
            return "<html><head><title>某半导体公司</title></head>" \
                   "<body>我们专注半导体芯片设计与制造</body></html>"
        raise AssertionError(url)

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    website, industry = resolve_mod.search_fallback("某半导体公司")
    assert website == "https://www.chipco.com"
    assert industry == "半导体"


def test_core_name_strips_suffixes_and_parens():
    assert resolve_mod._core_name("成都市公共交通集团有限公司") == "成都市公共交通集团"
    assert resolve_mod._core_name("纬创资通（成都）有限公司") == "纬创资通"
    assert resolve_mod._core_name("成都云图控股股份有限公司") == "成都云图控股"
