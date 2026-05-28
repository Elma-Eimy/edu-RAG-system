from typing import Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from crud.base import CRUDBase
from db.models.course_class import CourseClass
from db.models.relations import ClassTextbook, StudentClass

class CRUDClass(CRUDBase[CourseClass, Any, Any]):
    async def get_by_code(self, db: AsyncSession, class_code: str) -> Optional[CourseClass]:
        result = await db.execute(
            select(self.model).where(
                self.model.class_code == class_code,
                self.model.deleted_at.is_(None)
            )
        )
        return result.scalars().first()

    async def get_multi_by_teacher(
        self, db: AsyncSession, *, teacher_id: int, skip: int = 0, limit: int = 100
    ) -> List[CourseClass]:
        result = await db.execute(
            select(self.model)
            .options(
                selectinload(self.model.textbook_links).selectinload(ClassTextbook.textbook),
                selectinload(self.model.student_links).selectinload(StudentClass.student),
            )
            .where(
                self.model.teacher_id == teacher_id,
                self.model.deleted_at.is_(None)
            )
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_multi_by_ids_and_teacher(
        self, db: AsyncSession, *, class_ids: List[int], teacher_id: int
    ) -> List[CourseClass]:
        result = await db.execute(
            select(self.model).where(
                self.model.id.in_(class_ids),
                self.model.teacher_id == teacher_id,
                self.model.deleted_at.is_(None)
            )
        )
        return list(result.scalars().all())

crud_class = CRUDClass(CourseClass)
