"""ATS 适配器注册表 + 识别（架构 5.2 / 9.2 扩展点）。"""
from .base import JobCandidate
from .feishu import FeishuAdapter
from .greenhouse import GreenhouseAdapter
from .jsonld import JsonLdAdapter
from .lever import LeverAdapter

ADAPTERS = [GreenhouseAdapter(), LeverAdapter(), FeishuAdapter(), JsonLdAdapter()]


def detect_ats(url: str, html: str):
    """按注册表顺序识别 ATS，返回 (name, adapter)；全部未命中用 JSON-LD 兜底。"""
    for adapter in ADAPTERS:
        if adapter.detect(url, html):
            return adapter.name, adapter
    return "generic", JsonLdAdapter()
