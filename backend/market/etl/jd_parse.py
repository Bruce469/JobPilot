# -*- coding: utf-8 -*-
"""JD 文本解析：从职位描述中提取经验/学历要求（数据集无独立字段）。

解析失败返回 None，由调用侧按需求置"不限"（11.5：无法判断时置 NULL/不限并计入报告）。
"""
from __future__ import annotations

import re
from typing import Optional

# 学历正则（按 11.5 目标枚举）
EDU_PATTERNS = [
    (r"博士", "博士"),
    (r"硕士(?:及以上|或以上|以上)?", "硕士"),
    (r"本科(?:及以上|或以上|以上)?", "本科"),
    (r"大专|专科", "大专"),
    (r"中专|高中|中技|职高", "中专及以下"),
]
EDU_NONE = re.compile(r"学历不限|不限学历|无学历要求|学历.*?不限")

# 经验正则（按 11.5 目标枚举）
EXP_PATTERNS = [
    (r"10\s*年(?:以上|及以上)", "10年以上"),
    (r"5\s*[-~至到]\s*10\s*年", "5-10年"),
    (r"3\s*年(?:以上|及以上)", "3年以上"),
    (r"3\s*[-~至到]\s*5\s*年", "3-5年"),
    (r"1\s*[-~至到]\s*3\s*年", "1-3年"),
    (r"1\s*年(?:以内|以下)", "1年以内"),
    (r"应届(?:生|毕业生)?|在校生|无经验", "1年以内"),
]
EXP_NONE = re.compile(r"经验不限|不限经验|经验.*?不限|无经验要求")


def parse_education_from_text(text: Optional[str]) -> Optional[str]:
    """从 JD 文本解析学历要求（11.5 归一化）；"学历不限"→"不限"；无法判断 None。"""
    if not text:
        return None
    # 先查"不限"
    if EDU_NONE.search(text):
        return "不限"
    for pat, target in EDU_PATTERNS:
        if re.search(pat, text):
            return target
    return None


def parse_experience_from_text(text: Optional[str]) -> Optional[str]:
    """从 JD 文本解析经验要求（11.5 归一化）；"经验不限"→"不限"；无法判断 None。"""
    if not text:
        return None
    if EXP_NONE.search(text):
        return "不限"
    for pat, target in EXP_PATTERNS:
        if re.search(pat, text):
            return target
    return None
