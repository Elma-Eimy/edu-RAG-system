from sqlalchemy import ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.models.base import Base, SoftDeleteMixin
import enum

class StudentClassStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class ClassTextbook(Base, SoftDeleteMixin):
    __tablename__:str = "class_textbooks"
    __table_args__ = (
        UniqueConstraint("class_id", "textbook_id", name="uq_class_textbook"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    textbook_id: Mapped[int] = mapped_column(ForeignKey("textbooks.id"))

    course_class = relationship("CourseClass", back_populates="textbook_links")
    textbook = relationship("Textbook", back_populates="class_links")

class StudentClass(Base, SoftDeleteMixin):
    __tablename__:str = "student_classes"
    __table_args__ = (
        UniqueConstraint("student_id", "class_id", name="uq_student_class"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    status: Mapped[StudentClassStatus] = mapped_column(Enum(StudentClassStatus), default=StudentClassStatus.PENDING)

    student = relationship("User", foreign_keys=[student_id], back_populates="enrolled_classes")
    course_class = relationship("CourseClass", back_populates="student_links")
