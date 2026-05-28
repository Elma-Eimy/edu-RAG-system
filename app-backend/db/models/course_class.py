from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.models.base import Base, SoftDeleteMixin

class CourseClass(Base, SoftDeleteMixin):
    __tablename__:str = "classes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    class_code: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    
    # 外键约束
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # 实体间关系关联
    teacher = relationship("User", back_populates="classes")
    textbook_links = relationship("ClassTextbook", back_populates="course_class", cascade="all, delete-orphan")
    student_links = relationship("StudentClass", back_populates="course_class", cascade="all, delete-orphan")

