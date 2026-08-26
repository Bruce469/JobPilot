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

from . import company_info, company_map, icp as icp_mod, probe as probe_mod
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
    ("金融", ["银行", "证券", "保险", "基金", "投行", "券商", "金融", "资管",
              "投资公司", "投资管理", "投资控股", "bank"]),
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
    """按行业命中计数评分：同一文本里命中关键词数最多的行业胜出，平局按词表顺序取前。

    相比「首个命中即返回」，对整页正文（含投资/食品等噪声词）更稳；
    调用方应优先传标题/摘要等短文本，整页文本仅作兜底。
    """
    blob = " ".join(t for t in texts if t).lower()
    if not blob:
        return None
    best = None  # (命中数, 词表序号, 行业)
    for idx, (industry, keywords) in enumerate(INDUSTRY_KEYWORDS):
        hits = sum(1 for k in keywords if _contains(blob, k))
        if hits and (best is None or (hits, -idx) > (best[0], -best[1])):
            best = (hits, idx, industry)
    return best[2] if best else None


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


def _verify_site(name: str, url: str, deadline=None) -> tuple[str, str]:
    """抓取候选官网首页校验公司名核心串（兼容 SPA：正文可能为空，但 meta/OG 标签常服务端渲染了公司名）。

    返回 (status, 首页文本)：
    - ("ok", text)：标题/描述/OG 标签/正文含核心串，校验通过（可复用 text 做行业/城市/性质提取）；
    - ("unreachable", "")：抓取失败/超时/解析异常/无可校验文本（纯客户端渲染 SPA）→ 可走中置信通道；
    - ("mismatch", "")：页面可访问且有内容但整页不含核心串 → 坚决拒绝（不降级为中置信，防误配）。
    """
    core = _core_name(name)
    if not core:
        return "unreachable", ""
    try:
        html = fetch_text(url + "/", deadline)
    except (FetchError, TaskTimeout):
        return "unreachable", ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        parts = []
        if soup.title:
            parts.append(soup.title.get_text(" ", strip=True))
        for meta in soup.find_all("meta"):
            key = (meta.get("name") or meta.get("property") or "").lower()
            if key in ("description", "og:title", "og:description", "og:site_name",
                       "keywords", "application-name"):
                content = meta.get("content")
                if content:
                    parts.append(content)
        parts.append(soup.get_text(" ", strip=True)[:30000])
    except Exception:
        return "unreachable", ""
    text = " ".join(p for p in parts if p)
    if not text.strip():
        return "unreachable", ""
    blob = re.sub(r"\s+", "", text)
    return ("ok", text) if core in blob else ("mismatch", "")


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


# Bing 端点：cn 主用（国内可达、不跳转），www 兜底（实测 www 会 302 跳转且偶发连接被重置）。
BING_ENDPOINTS = ("https://cn.bing.com/search?q=", "https://www.bing.com/search?q=")
SEARCH_RETRY = 1  # 每个端点的瞬时网络错误重试次数


def _search(query: str, deadline=None) -> str | None:
    """遍历 Bing 端点取回搜索结果 HTML；瞬时网络错误每端点重试一次。全部失败返回 None。"""
    last_err = None
    for endpoint in BING_ENDPOINTS:
        for attempt in range(SEARCH_RETRY + 1):
            url = endpoint + quote(query)
            try:
                return fetch_text(url, deadline)
            except (FetchError, TaskTimeout) as exc:
                last_err = exc
                logger.info("搜索请求失败 query=%s endpoint=%s attempt=%d %s", query, endpoint, attempt + 1, exc)
    logger.info("搜索兜底请求全部失败 query=%s %s", query, last_err)
    return None


def search_fallback(name: str, deadline=None) -> dict:
    """Bing 搜索兜底。返回 {website, industry, confidence, snippet, homepage}；未找到可靠官网 website=None。

    - 只接受「搜索结果标题/摘要包含公司名核心串」的候选（Bing 对长中文公司名存在搜索碎片化，
      不校验会匹配到知乎专栏、政府网站、字典等错误页面——此类域名同时也在黑名单内）。
    - 首页校验通过（标题/描述/OG 标签/正文含核心串）→ confidence=high；
      首页抓取失败/超时/无文本（SPA、反爬、网络问题）但搜索结果上下文已含完整核心串 → confidence=medium，
      仍需人工核对（source 恒为 search，前端已有警示）。
    """
    core = _core_name(name)
    queries = []
    for q in (f"{name} 官网", f"{core} 官网", f"{core} 公司"):
        if q and q not in queries:
            queries.append(q)
    for query in queries:
        html = _search(query, deadline)
        if html is None:
            continue
        for candidate in _parse_bing_results(html):
            website = _origin_of(candidate["url"])
            if not website:
                continue
            host = _host_of(website)
            if not host or _excluded(host):
                continue
            snippet = f"{candidate['title']} {candidate['snippet']}".strip()
            status, homepage = _verify_site(name, website, deadline)
            if status == "ok":
                industry = match_industry(candidate["title"], candidate["snippet"])
                if not industry:
                    industry = match_industry(homepage)
                return {"website": website, "industry": industry, "confidence": "high",
                        "snippet": snippet, "homepage": homepage}
            if status == "unreachable" and core and core in re.sub(r"\s+", "", snippet):
                # 首页抓取不到（SPA/反爬/网络问题）但搜索结果上下文已含完整核心串 → 中置信接受
                return {"website": website, "industry": match_industry(candidate["title"], candidate["snippet"]),
                        "confidence": "medium", "snippet": snippet, "homepage": None}
            # status == "mismatch"：页面可访问但不含公司名 → 坚决拒绝，继续下一候选
    return {"website": None, "industry": None, "confidence": None, "snippet": None, "homepage": None}


# ---------------- 摘要/官网文本元数据提取（城市 / 公司性质） ----------------

CITIES = [
    "北京", "上海", "广州", "深圳", "天津", "重庆", "杭州", "南京", "苏州", "成都", "武汉", "西安",
    "郑州", "长沙", "沈阳", "青岛", "济南", "大连", "宁波", "厦门", "合肥", "福州", "昆明", "哈尔滨",
    "长春", "石家庄", "太原", "南昌", "贵阳", "南宁", "兰州", "海口", "乌鲁木齐", "呼和浩特", "银川",
    "西宁", "拉萨", "东莞", "佛山", "无锡", "常州", "南通", "温州", "嘉兴", "绍兴", "金华", "台州",
    "珠海", "惠州", "中山", "泉州", "烟台", "徐州", "保定", "临沂", "洛阳", "襄阳", "宜昌", "芜湖",
    "绵阳", "泸州", "宜宾", "德阳", "乐山", "南充", "达州", "遂宁", "眉山", "自贡", "内江", "攀枝花",
    "遵义", "桂林", "柳州", "唐山", "邯郸", "沧州", "廊坊", "大庆", "包头", "咸阳", "宝鸡",
    "潍坊", "淄博", "济宁", "泰安", "威海", "日照", "枣庄", "东营", "漳州", "莆田", "龙岩",
    "江门", "肇庆", "湛江", "茂名", "汕头", "清远", "韶关", "株洲", "湘潭", "衡阳", "荆州",
    "黄石", "九江", "赣州", "安庆", "芜湖", "马鞍山", "蚌埠", "宜昌", "襄阳", "洛阳", "徐州",
    "常州", "南通", "扬州", "镇江", "盐城", "淮安", "连云港", "泰州", "宿迁",
]
# 城市上下文指示词：其后的城市更可能是公司总部/注册地所在城市
CITY_HINT_BEFORE = ("总部", "注册地", "注册地址", "办公地址", "所在地", "位于", "坐落于", "设立于", "成立于", "诞生于")
NATURE_KEYWORDS = [
    ("央企", ["央企", "中央企业", "国务院国资委"]),
    ("国企", ["国企", "国有企业", "国有控股", "国有独资", "国企改革"]),
    ("事业单位", ["事业单位"]),
    ("合资", ["合资企业", "中外合资"]),
    ("外企", ["外企", "外资企业", "外商独资", "跨国公司"]),
    ("私企", ["民企", "私企", "民营企业", "私营企业", "股份制企业"]),
]


def extract_city(*texts: str) -> str | None:
    """从搜索摘要/官网文本尽力提取城市：优先「总部/注册地/位于」等上下文附近出现的城市；
    无上下文指示时取文本中最早出现的城市（公司名常自带地名，如「成都xx科技」）。"""
    blob = " ".join(t for t in texts if t)
    first: str | None = None
    for city in CITIES:
        idx = blob.find(city)
        if idx < 0:
            continue
        if any(h in blob[max(0, idx - 12):idx] for h in CITY_HINT_BEFORE):
            return city
        if first is None:
            first = city
    return first


def extract_nature(*texts: str) -> str | None:
    """从搜索摘要/官网文本按关键词匹配公司性质（央企 > 国企 > 事业单位 > 合资 > 外企 > 私企）。"""
    blob = " ".join(t for t in texts if t)
    for nature, keywords in NATURE_KEYWORDS:
        if any(k in blob for k in keywords):
            return nature
    return None


def extract_meta(*texts: str) -> dict:
    """综合提取 {industry, city, nature}；提取不到返回 null 对应键。"""
    return {"industry": match_industry(*texts), "city": extract_city(*texts), "nature": extract_nature(*texts)}


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


def resolve_from_mapping(name: str) -> dict | None:
    """仅查内置映射表返回补全结果（不发网络请求）；未命中返回 None。"""
    entry = company_map.lookup(name)
    if not entry:
        return None
    return {"name": name, "website": entry["website"], "industry": entry["industry"],
            "city": entry.get("city"), "nature": entry.get("nature"),
            "career_url": entry.get("career_url") or None, "source": "mapping"}


def resolve_from_info(name: str) -> dict | None:
    """A股上市公司离线库（cninfo，离线）：官网/行业/注册城市；无招聘站与性质。未命中返回 None。"""
    entry = company_info.lookup(name)
    if not entry:
        return None
    return {"name": name, "website": entry["website"], "industry": entry["industry"],
            "city": entry.get("city"), "nature": None, "career_url": None, "source": "info"}


def resolve_company(name: str, deadline=None) -> dict:
    """单公司自动补全（不落库）。返回 {name, website, industry, city, nature, career_url, source, confidence?, error?}。

    四级流水线（source 依次）：mapping（内置映射，含央企国企名录）→ info（A股离线库）→
    icp（ICP 备案反查，需配置 ICP_API_URL）→ search（Bing 兜底）。
    城市/公司性质：映射表精确给出；搜索路径从搜索结果摘要/官网文本尽力提取（无法确定时为 null，
    置信度 low，需人工核对）。
    - 映射命中且有官网 → 直接返回（最快路径）；
    - 映射命中但缺官网（如央企国企名录只给了招聘站/元数据）→ 继续搜索补官网，元数据以映射为准；
    - 未命中映射 → 依次走 A股离线库 / ICP 备案 / Bing 搜索。
    """
    name = str(name or "").strip()
    if not name:
        return {"name": name, "website": None, "industry": None, "city": None, "nature": None,
                "career_url": None, "source": "failed", "confidence": None, "error": "公司名为空"}
    mapped = resolve_from_mapping(name)
    if mapped and mapped.get("website"):
        mapped["confidence"] = "high"
        return mapped
    info = resolve_from_info(name)
    if info and info.get("website"):
        info["confidence"] = "high"
        return info
    if icp_mod.available():
        icp_hit = icp_mod.lookup(name)
        if icp_hit and icp_hit.get("website"):
            return {"name": name, "website": icp_hit["website"], "industry": None,
                    "city": None, "nature": None, "career_url": None,
                    "source": "icp", "confidence": "high"}
    found = search_fallback(name, deadline)
    website = found["website"]
    if website:
        meta = extract_meta(found["snippet"] or "", found["homepage"] or "")
        career_url = probe_career_url(website, deadline)
        # 映射（名录）命中但缺官网：行业/城市/性质/招聘站以映射为准，官网用搜索结果补。
        # source 仍标 search：官网未经映射确认（可能命中子公司站点），前端保留「请核对」警示。
        industry = found["industry"] or meta["industry"]
        city, nature = meta["city"], meta["nature"]
        if mapped:
            industry = mapped.get("industry") or industry
            city = mapped.get("city") or city
            nature = mapped.get("nature") or nature
            career_url = mapped.get("career_url") or career_url
        return {"name": name, "website": website, "industry": industry,
                "city": city, "nature": nature, "career_url": career_url,
                "source": "search", "confidence": found["confidence"]}
    if mapped:
        # 名录命中但官网也没找到：返回名录元数据（行业/城市/性质/招聘站），官网留空待人工
        return {"name": name, "website": None, "industry": mapped.get("industry"),
                "city": mapped.get("city"), "nature": mapped.get("nature"),
                "career_url": mapped.get("career_url"),
                "source": "mapping", "confidence": "high"}
    return {"name": name, "website": None, "industry": None, "city": None, "nature": None,
            "career_url": None, "source": "failed", "confidence": None,
            "error": "未找到可靠官网，请手动填写"}
