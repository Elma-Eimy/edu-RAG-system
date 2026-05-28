from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)

async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "msg": exc.detail, "data": None},
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"code": 422, "msg": "Validation Error", "data": exc.errors()},
    )

async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    # 仅记录日志（含完整异常信息），不将数据库内部细节（表名、SQL 语句等）暴露给客户端
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "msg": "数据库访问异常，请稍后重试", "data": None},
    )
    
async def global_exception_handler(request: Request, exc: Exception):
    # 兜底捕获所有未被处理的普通 Python 异常，同样不暴露内部细节
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "msg": "系统内部服务错误，请联系管理员", "data": None},
    )

