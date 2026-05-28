from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from crud.base import CRUDBase
from db.models.user import User

class CRUDUser(CRUDBase[User, Any, Any]):
    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        result = await db.execute(
            select(self.model).where(
                self.model.username == username,
                self.model.deleted_at.is_(None)
            )
        )
        return result.scalars().first()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(
            select(self.model).where(
                self.model.email == email,
                self.model.deleted_at.is_(None)
            )
        )
        return result.scalars().first()

crud_user = CRUDUser(User)
