from typing import Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from crud.base import CRUDBase
from db.models.textbook import Textbook

class CRUDTextbook(CRUDBase[Textbook, Any, Any]):
    async def get_multi_by_teacher(
        self, db: AsyncSession, *, teacher_id: int, skip: int = 0, limit: int = 100
    ) -> List[Textbook]:
        result = await db.execute(
            select(self.model)
            .where(
                self.model.teacher_id == teacher_id,
                self.model.deleted_at.is_(None)
            )
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

crud_textbook = CRUDTextbook(Textbook)
