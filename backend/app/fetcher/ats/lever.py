"""Lever 适配器（架构 5.4）：优先公开 postings API，失败解析 HTML。"""
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..errors import FetchError
from ..http import fetch_json
from .base import JobCandidate

API_URL = "https://api.lever.co/v0/postings/{company}?mode=json"


class LeverAdapter:
    name = "lever"

    def detect(self, url: str, html: str) -> bool:
        return "lever.co" in url

    def extract_jobs(self, html: str, base_url: str) -> list[JobCandidate]:
        company = self._company(base_url)
        jobs = self._from_api(company) if company else None
        if jobs is None:
            jobs = self._from_html(html, base_url)
        return jobs

    @staticmethod
    def _company(url: str) -> str | None:
        path = urlparse(url).path.strip("/").split("/")
        for seg in path:
            if seg and seg not in ("jobs",):
                return seg
        return None

    def _from_api(self, company: str) -> list[JobCandidate] | None:
        try:
            data = fetch_json(API_URL.format(company=company))
        except FetchError:
            return None
        if not isinstance(data, list):
            return None
        out = []
        for p in data:
            cats = p.get("categories") or {}
            commitment = str(cats.get("commitment") or "").lower()
            out.append(JobCandidate(
                position=p.get("text"),
                city=cats.get("location"),
                job_url=p.get("hostedUrl"),
                source_job_id=p.get("id"),
                job_type="实习" if "intern" in commitment else None,
            ))
        return out

    @staticmethod
    def _from_html(html: str, base_url: str) -> list[JobCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        out = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "lever.co" not in href:
                continue
            title = a.get_text(strip=True)
            if not title:
                continue
            job_url = urljoin(base_url, href)
            key = (title, job_url)
            if key in seen:
                continue
            seen.add(key)
            m = re.search(r"lever\.co/(?:[^/]+)/([0-9a-f-]+)", job_url)
            out.append(JobCandidate(position=title, job_url=job_url,
                                    source_job_id=m.group(1) if m else None))
        return out
