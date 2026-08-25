# -*- coding: utf-8 -*-
"""薪资归一化单测（REQ-DQ-01 / 需求 4.3 规则 1~9，每条规则 ≥1 用例）。"""
import pytest

from market.etl.salary import (
    DEFAULT_MONTHS,
    MAX_MONTHLY,
    MIN_MONTHLY,
    parse_salary,
)


class TestRule1_UnitNormalization:
    """规则 1：单位统一（K=千元/月；万/年×12→月；元/天→月）。"""

    def test_k_unit(self):
        r = parse_salary("15-25K")
        assert (r.salary_min, r.salary_max, r.salary_avg) == (15000, 25000, 20000)

    def test_wan_per_year(self):
        r = parse_salary("30-50万/年")
        assert (r.salary_min, r.salary_max) == (25000, 41667)
        assert r.salary_avg == 33334  # round((25000+41667)/2)

    def test_yuan_per_day_fulltime(self):
        r = parse_salary("200-300元/天", job_type="社招")
        assert (r.salary_min, r.salary_max) == (4350, 6525)  # ×21.75
        assert r.salary_avg == 5438


class TestRule2_SingleValue:
    """规则 2：单值 x → min=max=x。"""

    def test_single_k(self):
        r = parse_salary("20K")
        assert (r.salary_min, r.salary_max, r.salary_avg) == (20000, 20000, 20000)


class TestRule3_ChineseUnit:
    """规则 3：中文单位（5千-8千 / 1万-2万）。"""

    def test_cn_qian(self):
        r = parse_salary("5千-8千")
        assert (r.salary_min, r.salary_max) == (5000, 8000)

    def test_cn_wan(self):
        r = parse_salary("1万-2万")
        assert (r.salary_min, r.salary_max) == (10000, 20000)


class TestRule4_Months:
    """规则 4：含"薪"数年薪 → 先换算为月薪；无法解析按 12 薪。"""

    def test_k_with_14_months(self):
        r = parse_salary("15-25K·14薪")
        # 15K×12/14 ≈ 12857 ; 25K×12/14 ≈ 21429
        assert (r.salary_min, r.salary_max) == (12857, 21429)
        assert "14薪" in r.note

    def test_wan_year_with_13_months(self):
        # 年薪 30-50万 / 13薪 → 月薪 = 年薪/13
        r = parse_salary("30-50万/年·13薪")
        assert (r.salary_min, r.salary_max) == (23077, 38462)

    def test_no_months_falls_back_to_12(self):
        r = parse_salary("15-25K·N薪")
        assert (r.salary_min, r.salary_max) == (15000, 25000)


class TestRule5_MianyiMissing:
    """规则 5：面议/缺失/解析失败 → NULL，parse_ok=False。"""

    def test_mianyi(self):
        r = parse_salary("面议")
        assert r.parse_ok is False
        assert r.salary_min is None and r.salary_max is None and r.salary_avg is None

    def test_none(self):
        r = parse_salary(None)
        assert r.parse_ok is False and r.salary_min is None

    def test_empty_string(self):
        r = parse_salary("   ")
        assert r.parse_ok is False and r.salary_min is None


class TestRule6_Outliers:
    """规则 6：异常值 → is_valid=0。"""

    def test_max_over_300k(self):
        r = parse_salary("350-500K")
        assert r.is_valid is False
        assert "30万" in r.note

    def test_min_below_1500(self):
        r = parse_salary("1-3K")
        assert r.is_valid is False

    def test_min_greater_than_max(self):
        # 区间颠倒（防呆：交换并标记）
        r = parse_salary("25-15K")
        assert r.salary_min == 15000 and r.salary_max == 25000


class TestRule7_InternDayRate:
    """规则 7：实习岗元/天 → ×20（不乘 21.75）。"""

    def test_intern_uses_20_days(self):
        r = parse_salary("200-300元/天", job_type="实习")
        assert (r.salary_min, r.salary_max) == (4000, 6000)  # ×20

    def test_fulltime_uses_2175_days(self):
        r = parse_salary("200-300元/天", job_type="社招")
        assert (r.salary_min, r.salary_max) == (4350, 6525)  # ×21.75


class TestRule8_UnknownFormat:
    """规则 8：未知格式 → NULL + 计入未知格式统计。"""

    def test_unknown(self):
        r = parse_salary("薪资优厚")
        assert r.parse_ok is False
        assert r.format_type == "unknown"
        assert r.salary_min is None

    def test_format_type_tracking(self):
        assert parse_salary("15-25K").format_type == "k_interval"
        assert parse_salary("面议").format_type == "mianyi"
        assert parse_salary(None).format_type == "empty"
        assert parse_salary("(25000.0, 50000.0)").format_type == "paren_tuple"


class TestRule9_PureFunction:
    """规则 9：纯函数（相同输入 → 相同输出，无副作用）。"""

    def test_deterministic(self):
        a = parse_salary("15-25K·14薪").as_dict()
        b = parse_salary("15-25K·14薪").as_dict()
        assert a == b

    def test_input_not_mutated(self):
        text = " 15-25K "
        parse_salary(text)
        assert text == " 15-25K "


class TestDatasetFormat:
    """数据集格式 (25000.0, 50000.0)。"""

    def test_paren_tuple(self):
        r = parse_salary("(25000.0, 50000.0)")
        assert (r.salary_min, r.salary_max, r.salary_avg) == (25000, 50000, 37500)

    def test_decimal_rounding(self):
        r = parse_salary("(46666.67, 73333.33)")
        assert (r.salary_min, r.salary_max) == (46667, 73333)


class TestConstants:
    def test_thresholds(self):
        assert MAX_MONTHLY == 300_000
        assert MIN_MONTHLY == 1_500
        assert DEFAULT_MONTHS == 12
