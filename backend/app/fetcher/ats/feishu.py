"""飞书招聘适配器（架构 5.4）：JS 渲染 SPA，尽力提取页面内嵌 JSON，失败降级。"""
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import JobCandidate

_INJECTION_PATTERNS = [
    r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*[;]",
    r"window\.__APP_DATA__\s*=\s*(\{.*?\})\s*[;]",
    r"window\.APP_DATA\s*=\s*(\{.*?\})\s*[;]",
    r"window\.__NEXT_DATA__\s*=\s*(\{.*?\})\s*[;]",
]


class FeishuAdapter:
    name = "feishu"

    def detect(self, url: str, html: str) -> bool:
        u = url.lower()
        return "feishu.cn" in u or "feishu" in html.lower()

    def extract_jobs(self, html: str, base_url: str) -> list[JobCandidate]:
        data = self._extract_json(html)
        if data is None:
            return []
        out = []
        seen = set()
        for item in self._find_jobs(data):
            title = item.get("name") or item.get("title") or item.get("job_name")
            if not title:
                continue
            sid = str(item.get("post_id") or item.get("job_id") or item.get("id") or "")
            if not sid and title in seen:
                continue
            city = item.get("city") or item.get("work_location") or item.get("location")
            if not isinstance(city, str):
                city = None
            href = item.get("url") or item.get("link") or item.get("job_url") or item.get("apply_url")
            job_url = urljoin(base_url, href) if href and not href.startswith("http") else (href or None)
            seen.add(sid or title)
            out.append(JobCandidate(position=title, city=city, job_url=job_url,
                                    source_job_id=sid or None))
        return out

    @staticmethod
    def _extract_json(html: str):
        soup = BeautifulSoup(html, "html.parser")
        for sel in ('script[id="__NEXT_DATA__"]', 'script[type="application/json"]'):
            el = soup.select_one(sel)
            if el and el.string:
                try:
                    return json.loads(el.string)
                except json.JSONDecodeError:
                    pass
        for pat in _INJECTION_PATTERNS:
            m = re.search(pat, html, re.S)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    continue
        return None

    @staticmethod
    def _find_jobs(data) -> list[dict]:
        """递归找含 post_id/job_id 的岗位对象，避免重复。"""
        jobs, seen = [], set()

        def walk(node):
            if isinstance(node, dict):
                if ("post_id" in node or "job_id" in node) and (
                        "name" in node or "title" in node or "job_name" in node):
                    key = id(node)
                    if key not in seen:
                        seen.add(key)
                        jobs.append(node)
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(data)
        return jobs
