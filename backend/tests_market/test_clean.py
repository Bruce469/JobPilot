# -*- coding: utf-8 -*-
"""字段清洗归一化单测（REQ-DQ-02 / 附录 11.5）。"""
import pytest

from market.etl.clean import (
    clean_city,
    clean_company_size,
    clean_education,
    clean_experience,
    clean_industry,
    clean_job_type,
    classify_category,
    company_size_to_ordinal,
    experience_to_numeric,
)


class TestCity:
    def test_remove_shi_suffix(self):
        assert clean_city("苏州市") == "苏州"
        assert clean_city("北京") == "北京"

    def test_variant_merge(self):
        assert clean_city("苏州工业园区") == "苏州"
        assert clean_city("北京市") == "北京"

    def test_none_empty(self):
        assert clean_city(None) is None
        assert clean_city("   ") is None


class TestEducation:
    def test_11_5_mapping(self):
        assert clean_education("本科及以上") == "本科"
        assert clean_education("硕士及以上") == "硕士"
        assert clean_education("博士") == "博士"
        assert clean_education("大专") == "大专"
        assert clean_education("专科") == "大专"
        assert clean_education("高中") == "中专及以下"
        assert clean_education("学历不限") == "不限"
        assert clean_education(None) is None


class TestExperience:
    def test_11_5_mapping(self):
        assert clean_experience("经验1-3年") == "1-3年"
        assert clean_experience("3-5年") == "3-5年"
        assert clean_experience("5-10年") == "5-10年"
        assert clean_experience("10年以上") == "10年以上"
        assert clean_experience("3年以上") == "3年以上"
        assert clean_experience("应届生") == "1年以内"
        assert clean_experience("经验不限") == "不限"

    def test_numeric_conversion(self):
        assert experience_to_numeric("1-3年") == 2
        assert experience_to_numeric("10年以上") == 10
        assert experience_to_numeric("不限") is None

    def test_unknown(self):
        assert clean_experience("无法识别经验") is None


class TestCompanySize:
    def test_buckets(self):
        assert clean_company_size("少于50人") == "50人以下"
        assert clean_company_size("50-150人") == "50-150人"
        assert clean_company_size("100-499人") == "150-500人"
        assert clean_company_size("500-999人") == "500-1000人"
        assert clean_company_size("1000-9999人") == "1000-5000人"
        assert clean_company_size("5000-10000人") == "5000-10000人"
        assert clean_company_size("10000人以上") == "10000人以上"

    def test_ordinal(self):
        assert company_size_to_ordinal("50人以下") == 1
        assert company_size_to_ordinal("10000人以上") == 7

    def test_unknown(self):
        assert clean_company_size("未知规模") is None


class TestIndustry:
    def test_low_freq_merge(self):
        counts = {"互联网": 100, "金融": 10}
        assert clean_industry("互联网", counts, 50) == "互联网"
        assert clean_industry("金融", counts, 50) == "其他"

    def test_none(self):
        assert clean_industry(None) is None


class TestJobType:
    def test_intern(self):
        assert clean_job_type(title="数据分析实习生") == "实习"

    def test_campus(self):
        assert clean_job_type(title="算法工程师", desc="2026届校园招聘") == "校招"

    def test_social(self):
        assert clean_job_type(title="高级数据分析师", desc="社招") == "社招"

    def test_unknown_default(self):
        assert clean_job_type(title="数据分析师") == "不限"


class TestCategory:
    def test_bihao_ku(self):
        assert classify_category(title="BI工程师") == "BI数仓"
        assert classify_category(title="数据仓库开发工程师") == "BI数仓"
        assert classify_category(title="报表开发工程师") == "BI数仓"

    def test_bigdata(self):
        assert classify_category(title="大数据开发工程师") == "大数据"
        assert classify_category(title="Spark开发工程师") == "大数据"

    def test_datascience(self):
        assert classify_category(title="数据科学工程师") == "数据科学"
        assert classify_category(title="数据挖掘工程师") == "数据科学"

    def test_algorithm(self):
        assert classify_category(title="算法工程师") == "算法"
        assert classify_category(title="机器学习工程师") == "算法"
        assert classify_category(title="大模型算法工程师") == "算法"

    def test_label_fallback(self):
        assert classify_category(title="数据分析师", label="数据分析") == "数据分析"
        assert classify_category(title="量化研究员", label="经济金融") == "数据分析"

    def test_unknown_label(self):
        assert classify_category(title="其他岗位", label="未知") == "数据分析"
