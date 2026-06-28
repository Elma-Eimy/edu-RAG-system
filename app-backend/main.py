from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from core.exceptions import (
    custom_http_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    global_exception_handler,
)

def create_app() -> FastAPI:
    app = FastAPI(
            title=settings.PROJECT_NAME,
            openapi_url=f"{settings.API_V1_STR}/openapi.json",
            exception_handlers={
                StarletteHTTPException: custom_http_exception_handler,
                RequestValidationError: validation_exception_handler,
                SQLAlchemyError: sqlalchemy_exception_handler,
                Exception: global_exception_handler,
            }
        )

    # 配置跨域资源共享 (CORS)
    # ⚠️  注意：CORS 规范禁止 allow_origins=["*"] 与 allow_credentials=True 同时使用，
    # 浏览器会拒绝此类响应。必须在 .env 中配置 ALLOWED_ORIGINS 为具体域名列表。
    # 示例（多个域名用逗号分隔）：
    #   ALLOWED_ORIGINS=http://localhost:5173,https://yourdomain.com
    allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        return {"message": f"Welcome to {settings.PROJECT_NAME} API"}

    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    # 包含 API 路由分发器
    from api.v1.api import api_router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # 挂载静态文件目录以提供教材下载与教师证件照访问功能
    import os
    from fastapi.staticfiles import StaticFiles
    os.makedirs("uploads", exist_ok=True)
    app.mount("/static", StaticFiles(directory="uploads"), name="static")

    return app

app = create_app()
