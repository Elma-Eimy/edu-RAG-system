from sqlalchemy import String, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.models.base import Base, SoftDeleteMixin

class Notification(Base, SoftDeleteMixin):
    """
    通知实体模型。
    用于存储系统推送、管理员推送或针对用户（教师/学生）的各类消息通知。
    """
    __tablename__: str = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])
