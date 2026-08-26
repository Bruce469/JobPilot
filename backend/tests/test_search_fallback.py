"""搜索兜底单测：cn.bing 主端点 / 回退 / 重试 + 黑名单过滤 + 官网三态校验（high/medium/mismatch）+ 摘要元数据提取。

全部 mock，不访问真实网络。回归背景：Bing 对长中文公司名存在搜索碎片化，
旧逻辑取首个非黑名单结果会把知乎专栏/政府网站/字典等错误页面当作官网写入公司库。
"""
from app.fetcher import resolve as resolve_mod
from app.fetcher.errors import FetchError


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
    """知乎结果被黑名单排除且不被抓取；官方站首页包含公司名才被接受（high）。"""
    calls = []

    def fake_fetch_text(url, deadline=None):
        calls.append(url)
        if "cn.bing.com/search" in url:
            return _bing_html(
                ("https://zhuanlan.zhihu.com/p/123", "如何看待成都农商银行", "避坑"),
                ("https://www.cdrcb.com/", "成都农商银行", "银行存贷款业务"),
            )
        if "cdrcb.com" in url:
            return "<html><head><title>成都农村商业银行股份有限公司</title></head>" \
                   "<body>欢迎访问成都农村商业银行股份有限公司官网</body></html>"
        raise AssertionError(f"不应请求被排除域名: {url}")

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    result = resolve_mod.search_fallback("成都农村商业银行股份有限公司")
    assert result["website"] == "https://www.cdrcb.com"
    assert result["industry"] == "金融"
    assert result["confidence"] == "high"
    assert not any("zhihu.com" in u for u in calls)


def test_rejects_verified_but_mismatch_candidate_then_fails(monkeypatch):
    """候选首页可访问但不含公司名核心串 → 坚决拒绝（不降级为中置信）；全部拒绝 → website=None。"""

    def fake_fetch_text(url, deadline=None):
        if "cn.bing.com/search" in url:
            return _bing_html(
                ("https://www.other1.com/", "某未知公司X 介绍", ""),
                ("https://www.other2.com/", "某未知公司X 新闻", ""),
            )
        return "<html><head><title>完全无关的网站</title></head><body>完全无关的内容</body></html>"

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    result = resolve_mod.search_fallback("某未知公司X")
    assert result["website"] is None
    assert result["confidence"] is None


def test_medium_confidence_accepted_when_homepage_unreachable(monkeypatch):
    """首页抓取失败（网络/超时）但搜索结果标题/摘要含完整公司名核心串 → 中置信接受。"""

    def fake_fetch_text(url, deadline=None):
        if "cn.bing.com/search" in url:
            return _bing_html(
                ("https://www.spa-site.com/", "某未知公司X 官网", "某未知公司X 成立于 2005 年"),
            )
        raise FetchError("TIMEOUT", "请求超时")

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    result = resolve_mod.search_fallback("某未知公司X")
    assert result["website"] == "https://www.spa-site.com"
    assert result["confidence"] == "medium"


def test_medium_confidence_rejected_when_snippet_lacks_name(monkeypatch):
    """首页抓取失败且搜索结果上下文不含核心串 → 拒绝（防误配）。"""

    def fake_fetch_text(url, deadline=None):
        if "cn.bing.com/search" in url:
            return _bing_html(
                ("https://www.random.com/", "某某集团 发布新闻", "内容与公司业务无关"),
            )
        raise FetchError("TIMEOUT", "请求超时")

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    result = resolve_mod.search_fallback("某未知公司X")
    assert result["website"] is None


def test_meta_tags_verify_spa_homepage(monkeypatch):
    """SPA 首页正文为空但 meta/OG 标签含公司名 → 校验通过（high）。"""

    def fake_fetch_text(url, deadline=None):
        if "cn.bing.com/search" in url:
            return _bing_html(("https://www.spa-corp.com/", "某科技公司 官网", "产品与解决方案"))
        return '<html><head><meta name="description" content="某科技公司（SPA）致力于企业级服务"></head><body></body></html>'

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    result = resolve_mod.search_fallback("某科技公司")
    assert result["website"] == "https://www.spa-corp.com"
    assert result["confidence"] == "high"


def test_cn_bing_primary_endpoint_used(monkeypatch):
    """默认请求 cn.bing.com（国内可达、免跳转）。"""
    calls = []

    def fake_fetch_text(url, deadline=None):
        calls.append(url)
        if "cn.bing.com/search" in url:
            return _bing_html(("https://www.example.com/", "某公司 官网", ""))
        if "example.com" in url:
            return "<html><head><title>某公司</title></head><body>某公司官网</body></html>"
        raise AssertionError(f"不应请求: {url}")

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    result = resolve_mod.search_fallback("某公司")
    assert result["website"] == "https://www.example.com"
    assert calls[0].startswith("https://cn.bing.com/search")


def test_endpoint_fallback_to_www_on_cn_failure(monkeypatch):
    """cn.bing 全部重试失败后回退 www.bing.com。"""

    def fake_fetch_text(url, deadline=None):
        if "cn.bing.com/search" in url:
            raise FetchError("FETCH_ERROR", "连接被重置")
        if "www.bing.com/search" in url:
            return _bing_html(("https://www.example.com/", "某公司 官网", ""))
        if "example.com" in url:
            return "<html><head><title>某公司</title></head><body>某公司官网</body></html>"
        raise AssertionError(f"不应请求: {url}")

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    result = resolve_mod.search_fallback("某公司")
    assert result["website"] == "https://www.example.com"
    assert result["confidence"] == "high"


def test_retry_on_transient_error(monkeypatch):
    """同一端点瞬时网络错误后重试成功。"""
    calls = []

    def fake_fetch_text(url, deadline=None):
        calls.append(url)
        if "cn.bing.com/search" in url and len([c for c in calls if "cn.bing.com" in c]) == 1:
            raise FetchError("FETCH_ERROR", "连接被重置")
        if "cn.bing.com/search" in url:
            return _bing_html(("https://www.example.com/", "某公司 官网", ""))
        if "example.com" in url:
            return "<html><head><title>某公司</title></head><body>某公司官网</body></html>"
        raise AssertionError(url)

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    result = resolve_mod.search_fallback("某公司")
    assert result["website"] == "https://www.example.com"
    assert sum(1 for c in calls if "cn.bing.com/search" in c) == 2  # 首次失败 + 重试成功


def test_all_results_excluded_fails_without_fetching(monkeypatch):
    """结果全是被排除域名 → 失败，且不抓取任何候选首页。"""
    calls = []

    def fake_fetch_text(url, deadline=None):
        calls.append(url)
        if "cn.bing.com/search" in url:
            return _bing_html(
                ("https://zhuanlan.zhihu.com/p/1", "成都 旅游", ""),
                ("https://www.sc.gov.cn/", "四川省人民政府", ""),
                ("https://www.hanyuguoxue.com/", "蓝 的意思", ""),
            )
        raise AssertionError(f"不应请求被排除域名: {url}")

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    assert resolve_mod.search_fallback("蓝润集团有限公司")["website"] is None
    # 完整名与去后缀名两种查询都会尝试，但不会抓取任何被排除域名的首页
    assert calls and all("bing.com" in u for u in calls)


def test_blacklist_rejected_even_when_snippet_has_name(monkeypatch):
    """黑名单域名即使标题/摘要含公司名也拒绝（防回归：知乎专栏误配官网）。"""
    calls = []

    def fake_fetch_text(url, deadline=None):
        calls.append(url)
        if "cn.bing.com/search" in url:
            return _bing_html(
                ("https://zhuanlan.zhihu.com/p/999", "某未知公司X 完全解读", "某未知公司X 的前世今生"),
                ("https://www.biaoxing.com/", "某未知公司X 官网", ""),
            )
        if "biaoxing.com" in url:
            return "<html><head><title>完全无关的网站</title></head><body>完全无关的内容</body></html>"
        raise AssertionError(f"不应请求: {url}")

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    result = resolve_mod.search_fallback("某未知公司X")
    # 知乎被黑名单排除；biaoxing.com 可访问但不含公司名 → mismatch 拒绝
    assert result["website"] is None
    assert not any("zhihu.com" in u for u in calls)


def test_industry_matched_from_verified_homepage(monkeypatch):
    """摘要未命中行业时，从通过校验的官网首页文本匹配。"""
    def fake_fetch_text(url, deadline=None):
        if "cn.bing.com/search" in url:
            return _bing_html(
                ("https://www.chipco.com/", "某半导体公司", "欢迎访问"),
            )
        if "chipco.com" in url:
            return "<html><head><title>某半导体公司</title></head>" \
                   "<body>我们专注半导体芯片设计与制造</body></html>"
        raise AssertionError(url)

    monkeypatch.setattr(resolve_mod, "fetch_text", fake_fetch_text)
    result = resolve_mod.search_fallback("某半导体公司")
    assert result["website"] == "https://www.chipco.com"
    assert result["industry"] == "半导体"
    assert result["confidence"] == "high"


def test_core_name_strips_suffixes_and_parens():
    assert resolve_mod._core_name("成都市公共交通集团有限公司") == "成都市公共交通集团"
    assert resolve_mod._core_name("纬创资通（成都）有限公司") == "纬创资通"
    assert resolve_mod._core_name("成都云图控股股份有限公司") == "成都云图控股"


# ---------------- 摘要元数据提取（城市 / 性质 / 行业） ----------------

def test_extract_city_hint_context():
    assert resolve_mod.extract_city("某公司总部位于成都，成立于2005年") == "成都"
    assert resolve_mod.extract_city("某公司注册地在北京") == "北京"


def test_extract_city_first_occurrence_fallback():
    # 公司名自带地名（成都xx科技）时取最早出现的城市
    assert resolve_mod.extract_city("成都中科奥格生物科技有限公司官网") == "成都"


def test_extract_city_missing():
    assert resolve_mod.extract_city("没有城市信息的文本") is None


def test_extract_nature_priority():
    assert resolve_mod.extract_nature("某公司是央企，隶属于国务院国资委") == "央企"
    assert resolve_mod.extract_nature("这是一家国有企业") == "国企"
    assert resolve_mod.extract_nature("民营企业") == "私企"
    assert resolve_mod.extract_nature("外商独资企业") == "外企"


def test_extract_meta_combined():
    meta = resolve_mod.extract_meta("四川某生物科技公司 官网", "公司总部位于成都，是一家民营企业，专注生物医药研发")
    assert meta["city"] == "成都"
    assert meta["nature"] == "私企"
    assert meta["industry"] == "医药"
