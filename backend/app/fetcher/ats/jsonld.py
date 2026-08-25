"""JSON-LD 通用兜底解析器（架构 5.4）。"""
import json
from typing import Iterator

from bs4 import BeautifulSoup

from .base import JobCandidate


class JsonLdAdapter:
    name = "jsonld"

    def detect(self, url: str, html: str) -> bool:
        return "application/ld+json" in html

    def extract_jobs(self, html: str, base_url: str) -> list[JobCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        out = []
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue
            for item in self._iter_job_postings(data):
                cand = self._map(item)
                if cand:
                    out.append(cand)
        return self._dedupe(out)

    @staticmethod
    def _iter_job_postings(data) -> Iterator[dict]:
        if isinstance(data, dict):
            t = data.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(x == "JobPosting" for x in types):
                yield data
            for v in data.values():
                yield from JsonLdAdapter._iter_job_postings(v)
        elif isinstance(data, list):
            for v in data:
                yield from JsonLdAdapter._iter_job_postings(v)

    @staticmethod
    def _map(d: dict) -> JobCandidate | None:
        title = d.get("title")
        if not title:
            return None
        loc = d.get("jobLocation") or {}
        address = loc.get("address") if isinstance(loc, dict) else {}
        city = address.get("addressLocality") if isinstance(address, dict) else None
        identifier = d.get("identifier")
        sid = None
        if isinstance(identifier, dict):
            sid = str(identifier.get("value") or "") or None
        elif identifier is not None:
            sid = str(identifier)
        job_type = None
        et = str(d.get("employmentType") or "").lower()
        if "intern" in et:
            job_type = "实习"
        degree = None
        edu = d.get("educationRequirements")
        if isinstance(edu, dict):
            c = str(edu.get("credentialCategory") or edu.get("description") or "").lower()
            for k, v in (("phd", "博士"), ("doctor", "博士"), ("master", "硕士"), ("bachelor", "本科"), ("本科", "本科"), ("硕士", "硕士"), ("博士", "博士")):
                if k in c:
                    degree = v
                    break
        deadline = d.get("validThrough")
        if deadline:
            deadline = str(deadline)[:10]
        return JobCandidate(
            position=title, city=city, job_url=d.get("url"), source_job_id=sid,
            deadline=deadline, degree=degree, job_type=job_type,
        )

    @staticmethod
    def _dedupe(items: list[JobCandidate]) -> list[JobCandidate]:
        seen, out = set(), []
        for c in items:
            key = (c.source_job_id, c.job_url, c.position)
            if key not in seen:
                seen.add(key)
                out.append(c)
        return out
