from sqlalchemy import String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.models.base import Base, SoftDeleteMixin
import enum

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"

class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    FROZEN = "frozen"  # 用于管理员冻结违规用户账号

class User(Base, SoftDeleteMixin):
    __tablename__ : str = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.STUDENT)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE)

    # 实体间关系关联配置
    textbooks = relationship("Textbook", back_populates="teacher", cascade="all, delete-orphan")
    classes = relationship("CourseClass", back_populates="teacher", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="student", cascade="all, delete-orphan")
    enrolled_classes = relationship("StudentClass", back_populates="student", cascade="all, delete-orphan")

