"""按公司名称自动补全（PRD 4.12）：内置映射表优先 + Bing 搜索兜底 + 复用 probe 探测 career_url。

分层：
1. 映射表命中 → 直接返回 website / career_url / industry（source=mapping）
2. 未命中 → Bing 搜索「<公司名> 官网」取首个「官网首页包含公司名」的外站自然结果
   （过滤搜索引擎/内容平台/政府/字典等非官网域名；Bing 对长中文公司名有搜索碎片化，
   必须校验首页标题/文本包含公司名核心串，防误配），行业从结果标题/摘要或官网首页文本匹配（source=search）
3. 搜索失败或未找到可靠官网 → source=failed + error（批量场景下不写入任何字段，留待人工）

限速：统一走 app/fetcher/http.py（固定 UA、单请求 10s 超时、rate_limiter 同域 ≥1.5s / 全局 ≤30 req/min）。
"""
import logging
import re
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup

from . import company_map, probe as probe_mod
from .errors import FetchError, TaskTimeout
from .http import fetch_text
from .normalize import normalize_company

logger = logging.getLogger("app.fetcher.resolve")

# 非官网域名黑名单：搜索引擎/内容平台/政府/字典/工商查询/招聘站等，公司官网不会在这些域名上。
# 匹配规则：host == 域名 或 host 以「.域名」结尾（覆盖子域名，如 zhuanlan.zhihu.com）。
EXCLUDED_DOMAINS = {
    # 搜索引擎 / 广告
    "bing.com", "bing.com.cn", "bingj.com", "bing.net",
    "microsoft.com", "msn.com",
    "baidu.com", "google.com", "google.com.hk", "googleusercontent.com",
    "googlesyndication.com", "doubleclick.net",
    "sogou.com", "so.com", "360.cn", "yandex.com", "duckduckgo.com",
    "ecosia.org", "qwant.com", "search.yahoo.com", "yahoo.com",
    # 内容平台 / 问答 / 知识库 / 自媒体
    "zhihu.com", "wikipedia.org", "baike.com", "hudong.com",
    "360doc.com", "docin.com", "doc88.com", "book118.com", "renrendoc.com",
    "jianshu.com", "csdn.net", "cnblogs.com", "juejin.cn", "segmentfault.com",
    "infoq.cn", "oschina.net", "github.com", "medium.com", "wordpress.com", "blogspot.com",
    "xiaohongshu.com", "bilibili.com", "weibo.com", "douyin.com", "mp.weixin.qq.com",
    "36kr.com", "huxiu.com", "ithome.com", "geekpark.net", "ifanr.com", "sspai.com",
    "tmtpost.com", "leiphone.com", "pingwest.com", "jiemian.com", "thepaper.cn",
    "xueqiu.com", "gelonghui.com", "eastmoney.com", "10jqka.com.cn", "cninfo.com.cn",
    "sina.com.cn", "sohu.com", "163.com", "qq.com", "ifeng.com", "caixin.com",
    "yicai.com", "stcn.com", "chinanews.com.cn", "people.com.cn", "xinhuanet.com",
    "china.com.cn", "cctv.com",
    # 字典 / 国学 / 工具书
    "zdic.net", "hanyuguoxue.com", "guoxue.com", "dict.cn", "iciba.com", "mbalib.com",
    "gushici.com", "gushici.net", "chagushici.com", "hgcha.com",
    # 企业信息 / 工商查询
    "qcc.com", "tianyancha.com", "qixin.com", "aiqicha.baidu.com", "11467.com",
    # 招聘平台 / 职场社区
    "zhipin.com", "liepin.com", "lagou.com", "51job.com", "zhaopin.com", "jobui.com",
    "yingjiesheng.com", "nowcoder.com", "maimai.cn", "linkedin.com", "kanzhun.com",
    "shixiseng.com", "dajie.com",
    # 电商市场 / B2B 平台
    "taobao.com", "tmall.com", "1688.com", "b2b168.com", "pinduoduo.com",
    # 政府 / 事业单位 / 高校 / 协会
    "gov.cn", "edu.cn", "org.cn", "ac.cn",
}

# 行业关键词词表（优先级从高到低；命中即取该行业，全部未命中留空）
INDUSTRY_KEYWORDS = [
    ("半导体", ["半导体", "芯片", "集成电路", "晶圆", "semiconductor", "chip", "gpu"]),
    ("通信", ["5g", "通信", "通讯", "telecom"]),
    ("汽车", ["汽车", "整车", "智能驾驶", "新能源车", "电动车", "自动驾驶", "autopilot", "vehicle"]),
    ("金融", ["银行", "证券", "保险", "基金", "投资", "投行", "券商", "金融", "资管", "bank", "investment"]),
    ("能源", ["石油", "石化", "电力", "电网", "光伏", "风电", "储能", "能源", "新能源", "energy", "oil"]),
    ("快消", ["快消", "日化", "食品", "饮料", "消费品", "consumer"]),
    ("医药", ["医药", "制药", "生物", "医疗", "健康", "pharma", "biotech", "medical"]),
    ("教育", ["教育", "培训", "在线教育", "edu"]),
    ("地产", ["地产", "房地产", "置业", "real estate"]),
    ("物流", ["物流", "快递", "供应链", "货运", "logistics"]),
    ("咨询", ["咨询", "顾问", "consulting", "strategy"]),
    ("互联网", ["互联网", "移动互联网", "电商", "游戏", "internet", "e-commerce"]),
    ("科技", ["科技", "人工智能", "云计算", "大数据", "机器人", "software", "tech", "ai"]),
    ("制造", ["制造", "工业", "机械", "装备", "家电", "manufacturing"]),
]


def _contains(blob: str, kw: str) -> bool:
    """英文纯字母数字关键词按整词匹配（避免 ai/app 命中 apple/said 等），中文按子串。"""
    if kw and kw.isascii() and kw.isalnum():
        return re.search(rf"\b{re.escape(kw)}\b", blob) is not None
    return kw in blob


def match_industry(*texts) -> str | None:
    blob = " ".join(t for t in texts if t).lower()
    for industry, keywords in INDUSTRY_KEYWORDS:
        if any(_contains(blob, k) for k in keywords):
            return industry
    return None


def _host_of(url: str) -> str | None:
    try:
        netloc = urlparse(url).netloc
    except ValueError:
        return None
    if not netloc:
        return None
    return netloc.split(":")[0].lower()


def _excluded(host: str) -> bool:
    for d in EXCLUDED_DOMAINS:
        if host == d or host.endswith("." + d):
            return True
    return False


def _origin_of(url: str) -> str | None:
    p = urlparse(url)
    if p.scheme in ("http", "https") and p.netloc:
        return f"{p.scheme}://{p.netloc}"
    return None


def _core_name(name: str) -> str:
    """官网校验用的公司名核心串：去「有限公司/股份」等后缀、去括号内容（（成都）等）与空白。"""
    core = normalize_company(name)
    core = re.sub(r"[（(].*?[）)]", "", core)
    core = re.sub(r"[\s·\-_]", "", core)
    return core


def _verify_site(name: str, url: str, deadline=None) -> str | None:
    """抓取候选官网首页，确认首页标题/文本包含公司名核心串；通过则返回首页文本（可复用做行业匹配）。"""
    core = _core_name(name)
    if not core:
        return None
    try:
        html = fetch_text(url + "/", deadline)
    except (FetchError, TaskTimeout):
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        text = soup.get_text(" ", strip=True)[:30000]
    except Exception:
        return None
    blob = re.sub(r"\s+", "", title + " " + text)
    return f"{title}\n{text}" if core in blob else None


def _parse_bing_results(html: str, limit: int = 8) -> list[dict]:
    """解析 Bing 自然结果（li.b_algo），过滤无链接/脚本链接/黑名单域名，返回 [{url,title,snippet}]。"""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for li in soup.select("li.b_algo"):
        anchor = None
        for h in li.find_all("h2"):
            anchor = h.find("a", href=True)
            if anchor:
                break
        if not anchor:
            continue
        href = (anchor.get("href") or "").strip()
        if not href or href.lower().startswith(("javascript:", "#", "mailto:")):
            continue
        host = _host_of(href)
        if not host or _excluded(host):
            continue
        snippet = ""
        cap = li.select_one(".b_caption, .b_snippet, .b_lineclamp")
        if cap:
            snippet = cap.get_text(" ", strip=True)
        results.append({"url": href, "title": anchor.get_text(" ", strip=True), "snippet": snippet})
        if len(results) >= limit:
            break
    return results


def search_fallback(name: str, deadline=None) -> tuple[str | None, str | None]:
    """Bing 搜索兜底：返回 (website 主域名, industry)；未找到可靠官网返回 (None, None)。

    只接受「官网首页标题/文本包含公司名核心串」的候选（Bing 对长中文公司名存在搜索碎片化，
    不校验会匹配到知乎专栏、政府网站、字典等错误页面）；按候选顺序逐家校验，全部不通过则失败。
    """
    queries = [f"{name} 官网"]
    stripped = normalize_company(name)
    if stripped and stripped != name:
        queries.append(f"{stripped} 官网")
    for query in queries:
        url = "https://www.bing.com/search?q=" + quote(query)
        try:
            html = fetch_text(url, deadline)
        except (FetchError, TaskTimeout) as exc:
            logger.info("搜索兜底请求失败 name=%s %s", name, exc)
            return None, None
        for candidate in _parse_bing_results(html):
            website = _origin_of(candidate["url"])
            if not website:
                continue
            homepage = _verify_site(name, website, deadline)
            if homepage is None:
                continue
            industry = match_industry(candidate["title"], candidate["snippet"])
            if not industry:
                industry = match_industry(homepage)
            return website, industry
    return None, None


def probe_career_url(website: str, deadline=None, light: bool = True) -> str | None:
    """复用 probe 分层探测招聘页，返回置信度最高的候选 URL；失败/无候选返回 None。

    light=True 只做首页链接扫描（默认，用于搜索兜底场景）；light=False 走全量探测。
    """
    try:
        candidates, code, _ = probe_mod.probe_company(website, deadline, light=light)
    except Exception:
        logger.exception("探测招聘页失败 website=%s", website)
        return None
    if code or not candidates:
        return None
    return candidates[0]["url"]


def resolve_company(name: str, deadline=None) -> dict:
    """单公司自动补全（不落库）。返回 {name, website, industry, career_url, source, error?}。"""
    name = str(name or "").strip()
    if not name:
        return {"name": name, "website": None, "industry": None, "career_url": None,
                "source": "failed", "error": "公司名为空"}
    entry = company_map.lookup(name)
    if entry:
        return {"name": name, "website": entry["website"], "industry": entry["industry"],
                "career_url": entry.get("career_url") or None, "source": "mapping"}
    website, industry = search_fallback(name, deadline)
    if not website:
        return {"name": name, "website": None, "industry": None, "career_url": None,
                "source": "failed", "error": "未找到可靠官网，请手动填写"}
    career_url = probe_career_url(website, deadline)
    return {"name": name, "website": website, "industry": industry,
            "career_url": career_url, "source": "search"}
