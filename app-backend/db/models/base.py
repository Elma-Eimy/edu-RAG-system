from datetime import datetime,timezone
from typing import Any
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declared_attr

class Base(DeclarativeBase):
    id: Any
    __name__: str

    # 根据实体类名自动映射生成数据库表名（例如 User -> users）
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"

class SoftDeleteMixin:
    """
    为数据库模型提供软删除功能的 Mixin 混入类。
    """
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)

    def soft_delete(self):
        """执行软删除，记录当前删除时间。"""
        self.deleted_at = datetime.now(timezone.utc)

