from typing import Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from crud.base import CRUDBase
from db.models.chat import ChatSession, Message

class CRUDChatSession(CRUDBase[ChatSession, Any, Any]):
    async def get_by_student(self, db: AsyncSession, *, session_id: int, student_id: int) -> Optional[ChatSession]:
        result = await db.execute(
            select(self.model).where(
                self.model.id == session_id,
                self.model.student_id == student_id,
                self.model.deleted_at.is_(None)
            )
        )
        return result.scalars().first()

    async def get_multi_by_student(
        self, db: AsyncSession, *, student_id: int, skip: int = 0, limit: int = 100
    ) -> List[ChatSession]:
        result = await db.execute(
            select(self.model)
            .where(
                self.model.student_id == student_id,
                self.model.deleted_at.is_(None)
            )
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

class CRUDMessage(CRUDBase[Message, Any, Any]):
    async def get_multi_by_session(
        self, db: AsyncSession, *, session_id: int, skip: int = 0, limit: int = 50
    ) -> List[Message]:
        result = await db.execute(
            select(self.model)
            .where(
                self.model.session_id == session_id,
                self.model.deleted_at.is_(None)
            )
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_by_session(
        self, db: AsyncSession, *, session_id: int, exclude_message_id: int, limit: int
    ) -> List[Message]:
        result = await db.execute(
            select(self.model)
            .where(
                self.model.session_id == session_id,
                self.model.id != exclude_message_id,
                self.model.deleted_at.is_(None)
            )
            .order_by(self.model.created_at.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

crud_chat_session = CRUDChatSession(ChatSession)
crud_message = CRUDMessage(Message)
