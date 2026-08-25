"""FastAPI 应用入口：中间件顺序、异常处理器、路由注册、启动迁移与抓取工作线程。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config, db, services
from .errors import APIError, error_body
from .routes import router
from .security import security_middleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.migrate()
    from .fetcher import tasks as fetcher_tasks

    fetcher_tasks.start()
    backup = services.last_export_info()
    if backup["need_backup"]:
        logger.warning("距上次导出备份 %s 天，建议尽快导出（GET /api/backup/export）", backup["days_since"])
    logger.info("后端就绪 %s v%s（数据文件：%s）", config.APP_NAME, config.APP_VERSION, config.DB_PATH)
    yield


app = FastAPI(title=config.APP_NAME, version=config.APP_VERSION, lifespan=lifespan)

# 中间件注册顺序：后注册者在外层先执行 —— security 最外层（先于 CORS），
# 未认证请求最先被拦截；CORS 在内层处理白名单来源与预检（security 对 OPTIONS 放行）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Auth-Token"],
)


@app.middleware("http")
async def security(request: Request, call_next):
    return await security_middleware(request, call_next)


# ---------------- 统一异常处理器 ----------------
@app.exception_handler(APIError)
async def api_error_handler(_: Request, exc: APIError):
    return JSONResponse(status_code=exc.status_code,
                        content=error_body(exc.code, exc.message, exc.details))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400,
                        content=error_body("VALIDATION_ERROR", "请求参数校验失败", exc.errors()))


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException):
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 403: "FORBIDDEN"}.get(
        exc.status_code, "HTTP_ERROR")
    return JSONResponse(status_code=exc.status_code,
                        content=error_body(code, str(exc.detail)))


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception):
    logger.exception("未处理异常")
    return JSONResponse(status_code=500, content=error_body("INTERNAL_ERROR", "服务器内部错误"))


app.include_router(router, prefix="/api")

# JobPulse 招聘情报（market 模块）路由：/api/market/*（鉴权/异常统一走本应用中间件）
from market.api.app import build_router as build_market_router  # noqa: E402

app.include_router(build_market_router())
