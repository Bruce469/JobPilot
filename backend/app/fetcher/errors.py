"""抓取模块异常类型。"""


class TaskTimeout(Exception):
    """整任务超过 60s 上限。"""


class RobotsDisallowed(Exception):
    """robots.txt 禁止抓取。"""


class FetchError(Exception):
    """可报告的抓取失败（含错误码）。"""

    def __init__(self, code: str, message: str, mark_manual: bool = True):
        super().__init__(message)
        self.code = code
        self.message = message
        self.mark_manual = mark_manual  # 是否需要把公司置为「需人工」
