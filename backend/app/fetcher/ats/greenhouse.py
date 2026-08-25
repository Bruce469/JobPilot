"""Greenhouse 适配器（架构 5.4）：优先公开 board API，失败解析 HTML。"""
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..errors import FetchError
from ..http import fetch_json
from .base import JobCandidate

API_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


class GreenhouseAdapter:
    name = "greenhouse"

    def detect(self, url: str, html: str) -> bool:
        return "greenhouse.io" in url

    def extract_jobs(self, html: str, base_url: str) -> list[JobCandidate]:
        token = self._board_token(base_url)
        jobs = self._from_api(token) if token else None
        if jobs is None:
            jobs = self._from_html(html, base_url, token)
        return jobs

    def _board_token(self, url: str) -> str | None:
        path = urlparse(url).path.strip("/").split("/")
        if "boards" in path:
            i = path.index("boards")
            if i + 1 < len(path):
                return path[i + 1]
        for seg in path:
            if seg and seg not in ("v1", "jobs", "api"):
                return seg
        return None

    def _from_api(self, token: str) -> list[JobCandidate] | None:
        try:
            data = fetch_json(API_URL.format(token=token))
        except FetchError:
            return None
        out = []
        for j in data.get("jobs", []):
            loc = (j.get("location") or {}).get("name")
            job_type, degree = self._parse_metadata(j.get("metadata") or [])
            out.append(JobCandidate(
                position=j.get("title"),
                city=loc,
                job_url=j.get("absolute_url"),
                source_job_id=str(j.get("id")) if j.get("id") is not None else None,
                degree=degree,
                job_type=job_type,
            ))
        return out

    @staticmethod
    def _parse_metadata(metadata: list) -> tuple[str | None, str | None]:
        job_type = degree = None
        for m in metadata:
            name = str(m.get("name") or "").lower()
            value = str(m.get("value") or "").strip()
            if "employment" in name or "job type" in name:
                job_type = "实习" if "intern" in value.lower() else None
            elif "education" in name or "degree" in name:
                v = value.lower()
                for key, val in (("phd", "博士"), ("doctor", "博士"), ("master", "硕士"),
                                 ("bachelor", "本科"), ("本科", "本科"), ("硕士", "硕士"), ("博士", "博士")):
                    if key in v:
                        degree = val
                        break
        return job_type, degree

    @staticmethod
    def _from_html(html: str, base_url: str, token: str | None) -> list[JobCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        out = []
        for a in soup.select("div.opening a[href]"):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not title:
                continue
            container = a.find_parent("div", class_="opening") or a
            loc = container.find(class_="location") if container is not None else None
            city = loc.get_text(strip=True) if loc else None
            m = re.search(r"/(\d+)/?$", href)
            out.append(JobCandidate(
                position=title, city=city, job_url=urljoin(base_url, href),
                source_job_id=m.group(1) if m else None,
            ))
        return out
