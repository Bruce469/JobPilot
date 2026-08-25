"""统一错误结构与错误码（架构 4.1：HTTP 4xx/5xx 返回 {"error":{code,message,details?}}）。"""
from typing import Any


class APIError(Exception):
    """业务异常，由 FastAPI 异常处理器转换为统一 JSON。"""

    def __init__(self, status_code: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_body(code: str, message: str, details: Any = None) -> dict:
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def not_found(resource: str, rid: Any = None) -> APIError:
    return APIError(404, "NOT_FOUND", f"{resource}不存在", {"id": rid} if rid is not None else None)


def validation_error(message: str, details: Any = None) -> APIError:
    return APIError(400, "VALIDATION_ERROR", message, details)


def conflict(message: str, details: Any = None) -> APIError:
    return APIError(409, "CONFLICT", message, details)


def import_error(message: str, details: Any = None) -> APIError:
    return APIError(422, "IMPORT_ERROR", message, details)
