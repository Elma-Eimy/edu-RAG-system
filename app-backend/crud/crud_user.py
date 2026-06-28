from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from crud.base import CRUDBase
from db.models.user import User

class CRUDUser(CRUDBase[User, Any, Any]):
    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        result = await db.execute(
            select(self.model).where(
                func.lower(self.model.username) == username.lower(),
                self.model.deleted_at.is_(None)
            )
        )
        return result.scalars().first()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(
            select(self.model).where(
                func.lower(self.model.email) == email.lower(),
                self.model.deleted_at.is_(None)
            )
        )
        return result.scalars().first()

crud_user = CRUDUser(User)
