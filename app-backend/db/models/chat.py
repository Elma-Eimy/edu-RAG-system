from sqlalchemy import String, ForeignKey, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.models.base import Base, SoftDeleteMixin
from datetime import datetime
import enum

class SenderRole(str, enum.Enum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"

class ChatSession(Base, SoftDeleteMixin):
    __tablename__: str = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(100), default="New Chat")
    
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    textbook_id: Mapped[int] = mapped_column(ForeignKey("textbooks.id"))

    # 新增：AI 提炼的会话阶段性摘要与更新时间
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    student = relationship("User", back_populates="chat_sessions")
    textbook = relationship("Textbook", back_populates="chat_sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

class Message(Base, SoftDeleteMixin):
    __tablename__: str = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"))
    sender: Mapped[SenderRole] = mapped_column(Enum(SenderRole))
    content: Mapped[str] = mapped_column(Text)
    # 新增：保存大模型思考/推理过程的字段，允许为空（非思考模式或普通消息无此内容）
    reasoning_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship("ChatSession", back_populates="messages")
