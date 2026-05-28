import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from core.config import settings
from db.models.base import Base
# 在此处导入所有模型，以便 Alembic 可以跟踪其元数据
import db.models

# 这是 Alembic 配置对象，用于访问正在使用的 .ini 文件中的配置项。
config = context.config

# 解析配置文件以进行 Python 日志配置。
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 用于 'autogenerate' 的目标元数据
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """以 'offline' 模式运行迁移。"""
    url = settings.async_database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """在此场景中，我们需要创建一个引擎，
    并将一个连接与上下文关联起来。
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.async_database_url
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    """以 'online' 模式运行迁移。"""
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
