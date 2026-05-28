from sqlalchemy import String, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.models.base import Base, SoftDeleteMixin
import enum

class TextbookStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class Textbook(Base, SoftDeleteMixin):
    __tablename__ = "textbooks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    file_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[TextbookStatus] = mapped_column(Enum(TextbookStatus), default=TextbookStatus.PENDING)
    processing_progress: Mapped[int] = mapped_column(default=0)
    chroma_collection_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 外键约束
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # 实体间关系关联
    teacher = relationship("User", back_populates="textbooks")
    class_links = relationship("ClassTextbook", back_populates="textbook", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="textbook", cascade="all, delete-orphan")

