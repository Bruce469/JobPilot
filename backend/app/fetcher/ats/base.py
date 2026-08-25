"""ATS 适配器接口（Protocol）与岗位候选模型。"""
from typing import List, Optional, Protocol

from pydantic import BaseModel


class JobCandidate(BaseModel):
    """适配器产出的岗位候选，字段即 jobs 表抓取字段。"""
    position: str
    city: Optional[str] = None
    job_url: Optional[str] = None
    source_job_id: Optional[str] = None
    deadline: Optional[str] = None
    degree: Optional[str] = None
    job_type: Optional[str] = None  # 校招/社招/实习


class ATSAdapter(Protocol):
    name: str

    def detect(self, url: str, html: str) -> bool:
        """根据 URL 特征与页面内容判断是否命中该 ATS。"""
        ...

    def extract_jobs(self, html: str, base_url: str) -> List[JobCandidate]:
        """从页面 HTML 提取岗位列表。"""
        ...
