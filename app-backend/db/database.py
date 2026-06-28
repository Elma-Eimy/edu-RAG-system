from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from core.config import settings

engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    future=True,
    pool_recycle=3600,     # 连接最多复用 1 小时，防止超过 MySQL wait_timeout（默认 8h）后断裂
)

# 异步数据库会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# FastAPI 依赖项，用于在接口请求生命周期内获取和释放数据库异步连接会话
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

