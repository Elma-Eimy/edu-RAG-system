import redis.asyncio as aioredis
from core.config import settings

# 全局共享的异步 Redis 客户端，在生命周期内复用底层连接池
# settings.REDIS_URL 通常类似于 "redis://localhost:6379/0"
redis_client = aioredis.from_url(
    settings.REDIS_URL, 
    decode_responses=True,
    encoding="utf-8"
)
