import redis.asyncio as aioredis
from core.config import settings
import logging

logger = logging.getLogger(__name__)

# 基础 Redis 客户端，设置较短的超时时间（以便初次检测时能快速失败）
_raw_client = aioredis.from_url(
    settings.REDIS_URL, 
    decode_responses=True,
    encoding="utf-8",
    socket_connect_timeout=0.2, # 200ms 连接超时
    socket_timeout=0.2          # 200ms 操作超时
)

_redis_available = True

class SafeRedisClient:
    """
    包装 Redis 客户端，在 Redis 服务宕机时能够快速失败，防止长时间的连接超时。
    包含一个本地内存字典回退机制（带 TTL 过期），用于 Redis 离线时的本地开发与测试。
    """
    def __init__(self):
        # 存储格式：{name: (value, expire_at)}，expire_at 为时间戳，None 表示永不过期
        self._local_storage = {}

    def _get_local(self, name):
        import time
        if name in self._local_storage:
            val, expire_at = self._local_storage[name]
            if expire_at is None or time.time() < expire_at:
                return val
            else:
                del self._local_storage[name]
        return None

    async def get(self, name):
        global _redis_available
        if not _redis_available:
            return self._get_local(name)
        try:
            return await _raw_client.get(name)
        except Exception as e:
            _redis_available = False
            logger.warning("Redis is down, disabling cache (get failed): %s", e)
            return self._get_local(name)

    async def setex(self, name, time_seconds, value):
        global _redis_available
        import time
        expire_at = time.time() + float(time_seconds)
        self._local_storage[name] = (str(value), expire_at)
        if not _redis_available:
            return True
        try:
            return await _raw_client.setex(name, time_seconds, value)
        except Exception as e:
            _redis_available = False
            logger.warning("Redis is down, disabling cache (setex failed): %s", e)
            return True

    async def delete(self, *names):
        global _redis_available
        deleted_count = 0
        for name in names:
            if name in self._local_storage:
                del self._local_storage[name]
                deleted_count += 1
        if not _redis_available:
            return deleted_count
        try:
            db_deleted = await _raw_client.delete(*names)
            return db_deleted or deleted_count
        except Exception as e:
            _redis_available = False
            logger.warning("Redis is down, disabling cache (delete failed): %s", e)
            return deleted_count

    async def ping(self):
        global _redis_available
        try:
            return await _raw_client.ping()
        except Exception:
            _redis_available = False
            return False

redis_client = SafeRedisClient()
