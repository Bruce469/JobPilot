"""公司映射表匹配单测（PRD 4.12 v0.6）：规范名 / 别名 / 归一化匹配。"""
from app.fetcher import company_map


def test_lookup_canonical_name():
    entry = company_map.lookup("字节跳动")
    assert entry is not None
    assert entry["website"] == "https://www.bytedance.com"
    assert entry["industry"] == "互联网"
    assert entry["career_url"]


def test_lookup_alias_chinese():
    assert company_map.lookup("B站")["name"] == "哔哩哔哩"
    assert company_map.lookup("招行")["name"] == "招商银行"
    assert company_map.lookup("蚂蚁")["name"] == "蚂蚁集团"


def test_lookup_alias_english_case_insensitive():
    assert company_map.lookup("ByteDance")["name"] == "字节跳动"
    assert company_map.lookup("bytedance")["name"] == "字节跳动"
    assert company_map.lookup("bilibili")["name"] == "哔哩哔哩"
    assert company_map.lookup("NVIDIA")["name"] == "英伟达"


def test_lookup_normalized_name():
    """归一化匹配：去「有限公司/（中国）」等后缀后命中规范名。"""
    assert company_map.lookup("字节跳动有限公司")["name"] == "字节跳动"
    assert company_map.lookup("招商银行股份有限公司")["name"] == "招商银行"


def test_lookup_trims_space_and_halfwidth():
    assert company_map.lookup("  腾讯  ")["name"] == "腾讯"
    assert company_map.lookup("Ｂ站")["name"] == "哔哩哔哩"  # 全角 B


def test_lookup_miss_returns_none():
    assert company_map.lookup("某不存在的公司") is None
    assert company_map.lookup("") is None
    assert company_map.lookup("   ") is None


def test_entries_count_in_range():
    """映射表规模：101 家手工精选 + guoyang-pro 央企国企名录合并后约 230+ 家。"""
    assert 200 <= len(company_map.all_entries()) <= 400


def test_entries_have_city_and_nature():
    """每条映射均含城市与公司性质（供补全写库 / 公司库筛选）。"""
    for entry in company_map.all_entries():
        assert entry["city"], f"{entry['name']} 缺 city"
        assert entry["nature"], f"{entry['name']} 缺 nature"


def test_lookup_roster_soe():
    """guoyang-pro 央企国企名录条目可按简称/别名命中，性质与城市正确。"""
    e = company_map.lookup("中海油")
    assert e is not None
    assert e["name"] == "中国海洋石油集团有限公司"
    assert e["nature"] == "央企" and e["city"] == "北京" and e["industry"] == "能源"
    assert company_map.lookup("上海烟草")["nature"] == "央企"
    assert company_map.lookup("中央汇金")["city"] == "北京"
