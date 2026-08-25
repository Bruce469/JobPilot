# -*- coding: utf-8 -*-
"""薪资归一化纯函数（需求 4.3 规则 1~9，P0 清洗模块核心）。

设计约束：
- 所有规则为纯函数（无 IO、无副作用），便于单测与复现（规则 9）
- 返回值携带解析状态（成功/未知格式/异常），供数据质量报告统计
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ---- 格式分类（数据质量报告统计口径）----
FMT_K_INTERVAL = "k_interval"        # 15-25K 类
FMT_K_SINGLE = "k_single"            # 20K 单值
FMT_WAN_YEAR = "wan_year"            # 30-50万/年
FMT_CN_UNIT = "cn_unit"              # 5千-8千 / 1万-2万
FMT_DAY_RATE = "day_rate"            # 200-300元/天
FMT_PAREN_TUPLE = "paren_tuple"      # (25000.0, 50000.0) 数据集格式
FMT_MIANYI = "mianyi"                # 面议
FMT_UNKNOWN = "unknown"              # 未知格式
FMT_EMPTY = "empty"                  # 缺失/空

# 异常阈值（规则 6）
MAX_MONTHLY = 300_000    # 月薪 30 万+
MIN_MONTHLY = 1_500      # 低于主要城市最低工资参考线
WORK_DAYS_FULL = 21.75   # 元/天 → 月（全职）
WORK_DAYS_INTERN = 20    # 元/天 → 月（实习岗，规则 7）
DEFAULT_MONTHS = 12      # 无法解析"薪"数时按 12 薪（规则 4）

_NUM = r"(\d+(?:\.\d+)?)"


@dataclass
class SalaryParseResult:
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_avg: Optional[int] = None
    is_valid: bool = True          # 规则 6：异常薪资标记
    parse_ok: bool = True          # 是否成功解析
    format_type: str = FMT_UNKNOWN
    note: str = ""                 # 日志/报告说明

    def as_dict(self) -> dict:
        return {
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_avg": self.salary_avg,
            "is_valid": self.is_valid,
            "parse_ok": self.parse_ok,
            "format_type": self.format_type,
            "note": self.note,
        }


# ---------------------------------------------------------------- 工具

def _round_int(x: float) -> int:
    """四舍五入取整（薪资单位统一为元/月）。"""
    return int(round(x))


def _avg(min_v: int, max_v: int) -> int:
    """salary_avg = (min+max)/2（4.2 字段说明）。"""
    return _round_int((min_v + max_v) / 2)


def _apply_salary_months(min_v: float, max_v: float, months: int) -> tuple[float, float]:
    """年薪（月薪×薪数）× months → 换算为月薪（规则 1/4：先换算为月薪再取 min/max）。"""
    return min_v * 12 / months, max_v * 12 / months


# ---------------------------------------------------------------- 解析器

def parse_salary(text: Optional[str], job_type: str = "不限") -> SalaryParseResult:
    """统一入口：解析薪资文本。

    规则 5/8：面议/缺失/未知格式 → 薪资字段 NULL，parse_ok=False，保留记录但不进入建模集。
    规则 6：异常值 → is_valid=False。
    规则 7：实习岗元/天 → ×20。
    """
    if text is None:
        return SalaryParseResult(parse_ok=False, format_type=FMT_EMPTY, note="薪资缺失")
    s = str(text).strip()
    if not s:
        return SalaryParseResult(parse_ok=False, format_type=FMT_EMPTY, note="薪资为空")

    # 面议
    if re.search(r"面议|薪资面议|可面议", s):
        return SalaryParseResult(parse_ok=False, format_type=FMT_MIANYI, note="面议")

    # 元组格式 (25000.0, 50000.0) —— 数据集预清洗格式（元/月）
    m = re.match(r"^\s*\(\s*" + _NUM + r"\s*,\s*" + _NUM + r"\s*\)\s*$", s)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return _finalize(lo, hi, FMT_PAREN_TUPLE)

    # 元/天（规则 1/7）
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*元?/天", s)
    if m:
        days = WORK_DAYS_INTERN if "实习" in str(job_type) else WORK_DAYS_FULL
        lo, hi = float(m.group(1)) * days, float(m.group(2)) * days
        return _finalize(lo, hi, FMT_DAY_RATE, note=f"元/天×{days}")

    # 万/年（规则 1/4）：年薪 → 月薪 = 年薪 / 薪数（默认 12）
    m = re.search(_NUM + r"\s*-\s*" + _NUM + r"\s*万/年", s)
    if m:
        months = _parse_months(s)
        lo, hi = float(m.group(1)) * 10000 / months, float(m.group(2)) * 10000 / months
        return _finalize(lo, hi, FMT_WAN_YEAR, note=f"万/年,{months}薪")

    # 中文单位：5千-8千 / 1万-2万（规则 3）
    m = re.search(r"(\d+(?:\.\d+)?)\s*千\s*-\s*(\d+(?:\.\d+)?)\s*千", s)
    if m:
        lo, hi = float(m.group(1)) * 1000, float(m.group(2)) * 1000
        return _finalize(lo, hi, FMT_CN_UNIT)
    m = re.search(r"(\d+(?:\.\d+)?)\s*万\s*-\s*(\d+(?:\.\d+)?)\s*万", s)
    if m:
        months = _parse_months(s)
        lo, hi = _apply_salary_months(float(m.group(1)) * 10000, float(m.group(2)) * 10000, months)
        return _finalize(lo, hi, FMT_CN_UNIT, note=f"万元区间,{months}薪" if months != 12 else "万元区间")

    # K 区间：15-25K / 15K-25K / 15-25k·14薪（规则 1/4）
    m = re.search(r"(\d+(?:\.\d+)?)\s*[Kk]\s*-\s*(\d+(?:\.\d+)?)\s*[Kk]", s)
    if m:
        months = _parse_months(s)
        lo, hi = _apply_salary_months(float(m.group(1)) * 1000, float(m.group(2)) * 1000, months)
        return _finalize(lo, hi, FMT_K_INTERVAL, note=f"{months}薪" if months != 12 else "K区间")
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*[Kk]", s)
    if m:
        months = _parse_months(s)
        lo, hi = _apply_salary_months(float(m.group(1)) * 1000, float(m.group(2)) * 1000, months)
        return _finalize(lo, hi, FMT_K_INTERVAL, note=f"{months}薪" if months != 12 else "K区间")

    # K 单值：20K / 20k·13薪（规则 2）
    m = re.search(r"(\d+(?:\.\d+)?)\s*[Kk]", s)
    if m:
        months = _parse_months(s)
        lo = hi = _round_int(float(m.group(1)) * 1000 * 12 / months) if months != 12 \
            else _round_int(float(m.group(1)) * 1000)
        return _finalize(float(m.group(1)) * 1000, float(m.group(1)) * 1000, FMT_K_SINGLE,
                         note=f"单值K,{months}薪" if months != 12 else "单值K")

    # 纯数字区间（元/月）：15000-25000
    m = re.match(r"^\s*" + _NUM + r"\s*-\s*" + _NUM + r"\s*$", s)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return _finalize(lo, hi, FMT_K_INTERVAL, note="纯数字区间")

    # 未知格式（规则 8）
    return SalaryParseResult(parse_ok=False, format_type=FMT_UNKNOWN, note=f"未知薪资格式: {s[:30]}")


def _parse_months(text: str) -> int:
    """解析"薪"数（规则 4）：14薪/13薪 → 14/13；无法解析按 12。"""
    m = re.search(r"(\d{1,2})\s*薪", text)
    return int(m.group(1)) if m else DEFAULT_MONTHS


def _finalize(lo: float, hi: float, fmt: str, note: str = "") -> SalaryParseResult:
    """规则 2/6：单值 min=max；异常值（>30万/<1500/min>max）标记 is_valid=0。"""
    lo_i, hi_i = _round_int(lo), _round_int(hi)
    if lo_i > hi_i:
        lo_i, hi_i = hi_i, lo_i  # 防呆：区间颠倒时交换（仍记 note）
        note = (note + ";区间颠倒已交换").strip(";")
    res = SalaryParseResult(
        salary_min=lo_i, salary_max=hi_i, salary_avg=_avg(lo_i, hi_i),
        format_type=fmt, note=note,
    )
    # 规则 6 异常值检测
    if hi_i > MAX_MONTHLY or lo_i < MIN_MONTHLY or lo_i > hi_i:
        res.is_valid = False
        reason = []
        if hi_i > MAX_MONTHLY:
            reason.append(f"上限>30万({hi_i})")
        if lo_i < MIN_MONTHLY:
            reason.append(f"下限<1500({lo_i})")
        if lo_i > hi_i:
            reason.append("min>max")
        res.note = (res.note + ";" + ";".join(reason)).strip(";")
    return res


# ---------------------------------------------------------------- 便捷函数

def normalize_salary(text: Optional[str], job_type: str = "不限") -> tuple[Optional[int], Optional[int], Optional[int]]:
    """简化接口：返回 (salary_min, salary_max, salary_avg)；解析失败返回 (None,None,None)。"""
    r = parse_salary(text, job_type)
    return r.salary_min, r.salary_max, r.salary_avg
