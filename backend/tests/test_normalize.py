"""规范化函数单测（去重用，PRD 4.12）。"""
from app.fetcher import normalize


def test_normalize_position_removes_batch_prefix():
    assert normalize.normalize_position("【2026秋招】后端开发工程师") == "后端开发工程师"
    assert normalize.normalize_position("【内推】【2026校招】前端开发") == "前端开发"


def test_normalize_position_removes_hot_suffix():
    assert normalize.normalize_position("后端开发工程师急聘") == "后端开发工程师"
    assert normalize.normalize_position("算法工程师热招") == "算法工程师"


def test_normalize_position_halfwidth_and_space():
    assert normalize.normalize_position("ＡＢＣ 软 件") == "ABC软件"


def test_normalize_company_suffixes():
    assert normalize.normalize_company("字节跳动有限公司") == "字节跳动"
    assert normalize.normalize_company("北京字节跳动（中国）") == "北京字节跳动"
    assert normalize.normalize_company("某某股份有限公司") == "某某"
