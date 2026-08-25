"""安全中间件：Host 头校验 + boot 的 Origin 校验 + 其余请求 token 校验（架构 7 章）。

本中间件在 CORS 白名单中间件外层（Starlette 后注册者在外），因此预检 OPTIONS 在此放行、交由内层 CORS 处理。
"""
from fastapi import Request
from fastapi.responses import JSONResponse

from . import config
from .errors import error_body


async def security_middleware(request: Request, call_next):
    host = (request.headers.get("host") or "").split(":")[0].lower()
    if host not in config.ALLOWED_HOSTS:
        return JSONResponse(status_code=403, content=error_body("FORBIDDEN", "Host 校验失败，拒绝访问"))
    if request.method == "OPTIONS":
        # 预检请求不校验 token，交由内层 CORS 中间件应答
        return await call_next(request)
    if request.url.path == "/api/boot":
        # boot 本身受 Host + Origin 双重校验（无 Origin 视为同源/命令行访问）
        origin = request.headers.get("origin")
        if origin and origin not in config.ALLOWED_ORIGINS:
            return JSONResponse(status_code=403, content=error_body("FORBIDDEN", "Origin 校验失败"))
        return await call_next(request)
    if request.headers.get("x-auth-token") != config.TOKEN:
        return JSONResponse(status_code=401, content=error_body("UNAUTHORIZED", "token 缺失或错误"))
    return await call_next(request)
