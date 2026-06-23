from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from crud.base import CRUDBase
from db.models.relations import ClassTextbook, StudentClass, StudentClassStatus
from db.models.user import User

class CRUDClassTextbook(CRUDBase[ClassTextbook, Any, Any]):
    async def get_by_class_and_textbook(
        self, db: AsyncSession, *, class_id: int, textbook_id: int
    ) -> Optional[ClassTextbook]:
        """仅查询未软删除的绑定记录。"""
        result = await db.execute(
            select(self.model).where(
                self.model.class_id == class_id,
                self.model.textbook_id == textbook_id,
                self.model.deleted_at.is_(None)
            )
        )
        return result.scalars().first()

    async def get_multi_by_textbook_and_classes(
        self, db: AsyncSession, *, textbook_id: int, class_ids: List[int]
    ) -> List[ClassTextbook]:
        result = await db.execute(
            select(self.model).where(
                self.model.textbook_id == textbook_id,
                self.model.class_id.in_(class_ids),
                self.model.deleted_at.is_(None)
            )
        )
        return list(result.scalars().all())

    async def create_or_restore(
        self, db: AsyncSession, *, class_id: int, textbook_id: int
    ) -> ClassTextbook:
        """
        幂等绑定：若存在同组合的软删除旧记录，则复用并恢复（deleted_at→None）；
        否则新建记录。避免 UniqueConstraint 与软删除机制的冲突。
        """
        # 先查含软删除的记录
        result = await db.execute(
            select(self.model).where(
                self.model.class_id == class_id,
                self.model.textbook_id == textbook_id,
            )
        )
        existing = result.scalars().first()
        if existing:
            if existing.deleted_at is not None:
                # 复用已软删除的记录
                existing.deleted_at = None
                db.add(existing)
                await db.commit()
                await db.refresh(existing)
            return existing
        # 不存在则正常新建（加 try/except 应对极低概率的并发竞态）
        try:
            return await self.create(db, obj_in={"class_id": class_id, "textbook_id": textbook_id})
        except IntegrityError:
            await db.rollback()
            # 并发唱入返回现有记录
            result2 = await db.execute(
                select(self.model).where(
                    self.model.class_id == class_id,
                    self.model.textbook_id == textbook_id,
                )
            )
            return result2.scalars().first()

class CRUDStudentClass(CRUDBase[StudentClass, Any, Any]):
    async def get_by_student_and_class(
        self, db: AsyncSession, *, student_id: int, class_id: int
    ) -> Optional[StudentClass]:
        """仅查询未软删除的关联记录（不区分状态）。"""
        result = await db.execute(
            select(self.model).where(
                self.model.student_id == student_id,
                self.model.class_id == class_id,
                self.model.deleted_at.is_(None)
            )
        )
        return result.scalars().first()

    async def get_pending_or_approved_by_student_and_class(
        self, db: AsyncSession, *, student_id: int, class_id: int
    ) -> Optional[StudentClass]:
        result = await db.execute(
            select(self.model).where(
                self.model.student_id == student_id,
                self.model.class_id == class_id,
                self.model.status != StudentClassStatus.REJECTED,
                self.model.deleted_at.is_(None)
            )
        )
        return result.scalars().first()

    async def create_or_restore(
        self, db: AsyncSession, *, student_id: int, class_id: int
    ) -> StudentClass:
        """
        幂等申请：若存在已软删除的旧关联记录，则复用并重置为 PENDING；
        否则新建记录。避免 UniqueConstraint 与软删除机制的冲突。
        """
        # 含软删除地查找同组合旧记录
        result = await db.execute(
            select(self.model).where(
                self.model.student_id == student_id,
                self.model.class_id == class_id,
            )
        )
        existing = result.scalars().first()
        if existing:
            if existing.deleted_at is not None or existing.status == StudentClassStatus.REJECTED:
                # 曾经被软删除（退出/被踢）或被拒绝，复用并重置为待审批状态
                existing.deleted_at = None
                existing.status = StudentClassStatus.PENDING
                db.add(existing)
                await db.commit()
                await db.refresh(existing)
            return existing
        # 完全不存在则新建（加 try/except 应对极低概率的并发竞态）
        try:
            return await self.create(
                db, obj_in={"student_id": student_id, "class_id": class_id, "status": StudentClassStatus.PENDING}
            )
        except IntegrityError:
            await db.rollback()
            # 并发唱入时回查现有记录
            result2 = await db.execute(
                select(self.model).where(
                    self.model.student_id == student_id,
                    self.model.class_id == class_id,
                )
            )
            return result2.scalars().first()

    async def bulk_update_status(
        self, db: AsyncSession, *, application_ids: List[int], class_id: int, new_status: StudentClassStatus
    ) -> int:
        """
        批量更新审批状态（单条 SQL，一次事务提交），避免 N 次独立 commit 带来的部分提交风险。
        返回实际更新的行数。
        """
        result = await db.execute(
            sa_update(self.model)
            .where(
                self.model.id.in_(application_ids),
                self.model.class_id == class_id,
                self.model.status == StudentClassStatus.PENDING,
                self.model.deleted_at.is_(None),
            )
            .values(status=new_status)
        )
        await db.commit()
        return result.rowcount

    async def get_applications_by_class(
        self, db: AsyncSession, *, class_id: int, status_filter: Optional[StudentClassStatus] = None
    ) -> List[tuple[StudentClass, User]]:
        query = (
            select(self.model, User)
            .join(User, User.id == self.model.student_id)
            .where(
                self.model.class_id == class_id,
                self.model.deleted_at.is_(None),
                User.deleted_at.is_(None)
            )
        )
        if status_filter is not None:
            query = query.where(self.model.status == status_filter)
            
        result = await db.execute(query)
        return list(result.all())

    async def get_pending_applications_by_ids(
        self, db: AsyncSession, *, class_id: int, application_ids: List[int]
    ) -> List[StudentClass]:
        result = await db.execute(
            select(self.model).where(
                self.model.id.in_(application_ids),
                self.model.class_id == class_id,
                self.model.status == StudentClassStatus.PENDING,
                self.model.deleted_at.is_(None)
            )
        )
        return list(result.scalars().all())

    async def get_multi_by_student(
        self, db: AsyncSession, *, student_id: int
    ) -> list:
        """获取学生所有已申请/加入的班级（含班级详情），按展示申请时间倒序。"""
        from db.models.course_class import CourseClass
        result = await db.execute(
            select(self.model, CourseClass)
            .join(CourseClass, CourseClass.id == self.model.class_id)
            .where(
                self.model.student_id == student_id,
                self.model.deleted_at.is_(None),
                CourseClass.deleted_at.is_(None),
            )
            .order_by(self.model.created_at.desc())
        )
        return list(result.all())

crud_class_textbook = CRUDClassTextbook(ClassTextbook)
crud_student_class = CRUDStudentClass(StudentClass)
