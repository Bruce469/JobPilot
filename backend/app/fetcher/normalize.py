"""岗位名 / 公司名规范化（去重用，PRD 4.12 / 架构 5.1）。"""
import re
import unicodedata


def _half(s: str) -> str:
    """全角 → 半角（NFKC 同时处理空格与标点差异）。"""
    return unicodedata.normalize("NFKC", s)


def normalize_position(position) -> str:
    """去【】批次前缀、去「急聘/热招」后缀、去空格与全半角差异。"""
    s = _half(str(position or "")).strip()
    s = re.sub(r"^(?:【[^】]*】)+", "", s)        # 【2026秋招】前端开发 / 【内推】【2026校招】前端开发
    s = re.sub(r"(急聘|热招|长期招聘|诚聘|火热招聘中)$", "", s)  # 后端开发工程师急聘
    s = re.sub(r"\s+", "", s)                   # 去全部空白
    s = s.strip("·|/()（）")
    return s


def normalize_company(name) -> str:
    """去「有限公司/股份/（中国）」等后缀。"""
    s = _half(str(name or "")).strip()
    s = re.sub(r"[（(]中国[）)]$", "", s)
    s = re.sub(r"有限责任公司$", "", s)
    s = re.sub(r"股份有限公司$", "", s)
    s = re.sub(r"有限公司$", "", s)
    s = re.sub(r"股份公司$", "", s)
    s = re.sub(r"公司$", "", s)
    return s.strip()
