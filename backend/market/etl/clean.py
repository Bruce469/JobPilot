# -*- coding: utf-8 -*-
"""字段清洗归一化纯函数（需求 REQ-DQ-02 / 附录 11.5）。

- clean_city：去"市"后缀 + 变体归并（如"苏州工业园区"→"苏州"）
- clean_education / clean_experience / clean_company_size：11.5 枚举映射
- clean_industry：低频归并（< 阈值 → 其他），阈值在调用侧传入
- clean_job_type：实习/校招/社招/不限（解析自标题/标签/详情，无法判定为"不限"）
- classify_category：岗位大类（附录 11.2 映射表 + 需求 4.4 扩展关键词）
"""
from __future__ import annotations

import re
from typing import Optional

# ---- 城市变体归并表（REQ-DQ-02）----
CITY_VARIANTS = {
    "苏州工业园区": "苏州", "苏州新区": "苏州", "苏州高新区": "苏州",
    "北京亦庄": "北京", "北京市": "北京", "上海浦东": "上海", "上海市": "上海",
    "广州市": "广州", "深圳市": "深圳", "杭州市": "杭州", "成都市": "成都",
    "南京市": "南京", "武汉市": "武汉", "西安市": "西安", "重庆市": "重庆",
    "天津滨海新区": "天津",
}

# 10 城白名单（REQ-4.4；其他城市/“其他” → is_valid=0）
CITY_WHITELIST = {"北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉", "西安", "苏州"}

# ---- 学历归一化（附录 11.5）----
EDUCATION_MAP = [
    (r"博士", "博士"),
    (r"硕士", "硕士"),
    (r"本科", "本科"),
    (r"大专|专科", "大专"),
    (r"中专|高中|中技|职高", "中专及以下"),
    (r"学历不限|不限学历|教育不限", "不限"),
]

# ---- 经验归一化（附录 11.5，数值化口径见注释）----
EXPERIENCE_MAP = [
    (r"10年以上", "10年以上"),          # 数值化 10（封顶）
    (r"5-10年|5到10年|五年以上十年以下", "5-10年"),   # 数值化 7.5
    (r"3年以上|三年以上", "3年以上"),    # 数值化 3
    (r"3-5年|3到5年|三到五年", "3-5年"),  # 数值化 4
    (r"1-3年|1到3年|一到三年", "1-3年"),  # 数值化 2
    (r"1年以内|应届生|应届|在校生|无经验|经验不限|不限经验", "1年以内"),  # 数值化 0.5
]

# ---- 公司规模有序桶（附录 11.5）----
COMPANY_SIZE_BUCKETS = [
    (r"少于50人|0-50人|1-49人|少于100人|0-100人", "50人以下"),
    (r"50-150人|50-100人|100-150人|50人以上", "50-150人"),
    (r"150-500人|100-499人|100-500人|150-300人|200-500人", "150-500人"),
    (r"500-1000人|500-999人|500-900人", "500-1000人"),
    (r"1000-5000人|1000-9999人|1000-10000人|1000人以上", "1000-5000人"),
    (r"5000-10000人|5000-9999人", "5000-10000人"),
    (r"10000人以上|万人以上", "10000人以上"),
]

# ---- 岗位大类：附录 11.2 关键词映射 + 需求 4.4 扩展关键词 ----
CATEGORY_RULES = [
    # 规则顺序即优先级；返回 (大类, 命中的关键词说明)
    ("BI数仓", r"数据仓库|数仓|BI开发|商业智能|BI工程师|报表开发|BI报表|帆软|FineBI"),
    ("大数据", r"大数据|Hadoop|Spark|Flink|Hive|数据平台|数据开发|ClickHouse"),
    ("BI数仓", r"BI分析|BI数据|Power\s?BI|Tableau|数据可视化|看板"),
    ("数据科学", r"数据科学|数据科学家|数据挖掘|统计建模|生物统计"),
    ("算法", r"算法工程师|机器学习|深度学习|推荐系统|推荐算法|\bNLP\b|大模型|\bLLM\b|AIGC|神经网络"),
    # label 兜底（由调用侧传入 label）
]
# label 兜底映射（数据集 label → 大类）
LABEL_FALLBACK = {
    "数据分析": "数据分析",
    "经济金融": "数据分析",
    "算法岗": "算法",
    "大模型相关": "数据科学",
    "生物统计": "数据科学",
}

KNOWN_CATEGORIES = ["数据分析", "数据科学", "大数据", "算法", "BI数仓"]

# 数据类岗位标题判定（实时源主题过滤用；标题是岗位主题最可靠信号）
DATA_JOB_TITLE_RE = re.compile(
    r"数据|分析|算法|机器学习|深度学习|数据挖掘|统计|数据仓库|数仓|"
    r"大数据|BI|商业智能|报表|人工智能|AI|NLP|推荐|模型", re.I)


def is_data_job_title(title: str = "") -> bool:
    """标题是否命中数据类岗位关键词（实时源主题过滤）。"""
    return bool(title and DATA_JOB_TITLE_RE.search(title))


# ---------------------------------------------------------------- 城市

def clean_city(city: Optional[str]) -> Optional[str]:
    """统一去掉"市"后缀 + 变体归并；无法识别返回 None。"""
    if city is None:
        return None
    s = str(city).strip()
    if not s:
        return None
    if s in CITY_VARIANTS:
        return CITY_VARIANTS[s]
    # "苏州市" → "苏州"；"北京" 不变
    if s.endswith("市"):
        s = s[:-1]
    return s if s else None


# ---------------------------------------------------------------- 学历/经验/规模

def clean_education(edu: Optional[str]) -> Optional[str]:
    """学历归一化（11.5）；无法判断置 None（计入数据质量报告未知值）。"""
    if not edu:
        return None
    s = str(edu).strip()
    if not s:
        return None
    for pattern, target in EDUCATION_MAP:
        if re.search(pattern, s):
            return target
    return None


def clean_experience(exp: Optional[str]) -> Optional[str]:
    """经验归一化（11.5）；经验不限 → "不限"（建模单独类别）。"""
    if not exp:
        return None
    s = str(exp).strip()
    if not s:
        return None
    if re.search(r"经验不限|不限经验|经验学历不限|无要求", s):
        return "不限"
    for pattern, target in EXPERIENCE_MAP:
        if re.search(pattern, s):
            return target
    return None


def clean_company_size(size: Optional[str]) -> Optional[str]:
    """公司规模 → 有序桶（11.5）；无法判断返回 None。"""
    if not size:
        return None
    s = str(size).strip()
    if not s:
        return None
    for pattern, target in COMPANY_SIZE_BUCKETS:
        if re.search(pattern, s):
            return target
    return None


def clean_industry(industry: Optional[str], counts: Optional[dict] = None,
                   threshold: int = 50) -> Optional[str]:
    """行业清洗：去空白 + 低频归并（counts < threshold → 其他）（REQ-DQ-02）。"""
    if not industry:
        return None
    s = str(industry).strip()
    if not s:
        return None
    if counts and counts.get(s, 0) < threshold:
        return "其他"
    return s


# ---------------------------------------------------------------- 岗位性质

def clean_job_type(title: str = "", tags: str = "", desc: str = "") -> str:
    """岗位性质：实习/校招/社招/不限。

    解析自标题/标签/详情（4.2 job_type 说明）；无法判定为"不限"。
    优先级：实习 > 校招 > 社招。
    """
    text = f"{title} {tags} {desc}"
    if re.search(r"实习", text):
        return "实习"
    if re.search(r"校招|校园招聘|应届毕业生|应届生", text):
        return "校招"
    if re.search(r"社招|社会招聘", text):
        return "社招"
    return "不限"


# ---------------------------------------------------------------- 岗位大类

def classify_category(title: str = "", desc: str = "", label: str = "") -> str:
    """岗位大类归一化（附录 11.2 映射 + 需求 4.4 扩展关键词）。

    先按关键词规则匹配，未命中则用 label 兜底；仍未知归"数据分析"并可由调用侧标记。
    """
    text = f"{title} {desc}"
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, text, re.I):
            return category
    if label and label in LABEL_FALLBACK:
        return LABEL_FALLBACK[label]
    return "数据分析"


# ---------------------------------------------------------------- 经验数值化（建模用）

EXPERIENCE_MONTHS_VALUE = {
    "1年以内": 0.5,
    "1-3年": 2,
    "3-5年": 4,
    "5-10年": 7.5,
    "10年以上": 10,
    "3年以上": 3,
    "不限": None,
}


def experience_to_numeric(exp: Optional[str]) -> Optional[float]:
    """经验 → 数值（区间取中值，11.5 口径；不限 → None 由建模单独类别处理）。"""
    if not exp:
        return None
    return EXPERIENCE_MONTHS_VALUE.get(exp)


# ---------------------------------------------------------------- 公司规模有序值（建模用）

COMPANY_SIZE_ORDER = {
    "50人以下": 1, "50-150人": 2, "150-500人": 3, "500-1000人": 4,
    "1000-5000人": 5, "5000-10000人": 6, "10000人以上": 7,
}


def company_size_to_ordinal(size: Optional[str]) -> Optional[int]:
    if not size:
        return None
    return COMPANY_SIZE_ORDER.get(size)
