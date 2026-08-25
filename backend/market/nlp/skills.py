# -*- coding: utf-8 -*-
"""技能匹配引擎（REQ-NLP-01/02/05）：
- jieba 分词 + 自定义领域词典 + 停用词清洗 JD
- 技能词表 config/skill_words.json 匹配（大小写不敏感）
- 产出 skills_hit / skills_count 特征（写 features.parquet）
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

import jieba
import pandas as pd

logger = logging.getLogger(__name__)

# 合并后 config 资源随包迁至 backend/market/config/
PACKAGE_DIR = Path(__file__).resolve().parent.parent            # backend/market/
CONFIG_DIR = PACKAGE_DIR / "config"


class SkillMatcher:
    """技能词匹配器：加载技能词表/词典，JD → 命中技能清单。"""

    def __init__(self, skill_words_path: str | Path | None = None,
                 stopwords_path: str | Path | None = None,
                 userdict_path: str | Path | None = None):
        self.skill_words_path = Path(skill_words_path) if skill_words_path else CONFIG_DIR / "skill_words.json"
        self.stopwords_path = Path(stopwords_path) if stopwords_path else CONFIG_DIR / "stopwords.txt"
        self.userdict_path = Path(userdict_path) if userdict_path else CONFIG_DIR / "userdict.txt"
        self._load()

    def _load(self) -> None:
        # 技能词表（分组 dict → 扁平 list）
        with open(self.skill_words_path, "r", encoding="utf-8") as f:
            grouped = json.load(f)
        self.skill_words: list[str] = []
        self.skill_groups: dict[str, list[str]] = {}
        for group, words in grouped.items():
            self.skill_groups[group] = list(words)
            for w in words:
                w = w.strip()
                if w and w not in self.skill_words:
                    self.skill_words.append(w)

        # 停用词
        self.stopwords: set[str] = set()
        if self.stopwords_path.exists():
            self.stopwords = {ln.strip() for ln in
                              self.stopwords_path.read_text(encoding="utf-8").splitlines() if ln.strip()}

        # 用户词典（jieba）
        if self.userdict_path.exists():
            jieba.load_userdict(str(self.userdict_path))

        # 技能词加入 jieba 词典（保证整词识别）
        for w in self.skill_words:
            jieba.add_word(w)
        # 预编译大小写不敏感模式：
        # - 长度 ≤2 的短词（如 R / BI / NLP）要求独立词边界，防误命中（REQ-NLP-01）
        # - "R"（R 语言）额外匹配 "R语言" 组合
        self._patterns = {}
        for w in self.skill_words:
            if len(w) <= 2:
                if w == "R":
                    self._patterns[w] = re.compile(r"\bR\b|R语言", re.I)
                else:
                    self._patterns[w] = re.compile(rf"\b{re.escape(w)}\b", re.I)
            else:
                self._patterns[w] = re.compile(re.escape(w), re.I)

    @property
    def word_count(self) -> int:
        return len(self.skill_words)

    def match_skills(self, text: Optional[str]) -> list[str]:
        """返回文本中命中的技能词清单（去重、保持词表顺序）。"""
        if not text:
            return []
        hits = []
        for w in self.skill_words:
            if self._patterns[w].search(text):
                hits.append(w)
        return hits

    def compute_features(self, df: pd.DataFrame, desc_col: str = "job_desc") -> pd.DataFrame:
        """为 DataFrame 添加 skills_hit / skills_count 列（REQ-NLP-05）。"""
        out = df.copy()
        hits = out[desc_col].fillna("").apply(self.match_skills)
        out["skills_hit"] = hits.apply(lambda x: x)
        out["skills_count"] = hits.apply(len)
        return out

    def jieba_tokens(self, text: str) -> list[str]:
        """jieba 分词 + 停用词过滤（REQ-NLP-01 抽样核对用）。"""
        words = jieba.lcut(text)
        return [w for w in words if w.strip() and w not in self.stopwords and len(w) > 1]
