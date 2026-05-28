from typing import Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from crud.base import CRUDBase
from db.models.notification import Notification

class CRUDNotification(CRUDBase[Notification, Any, Any]):
    """
    通知 CRUD 数据操作类。
    提供获取指定用户的通知列表、以及一键标记已读功能。
    """
    async def get_multi_by_receiver(
        self, db: AsyncSession, *, receiver_id: int, skip: int = 0, limit: int = 100
    ) -> List[Notification]:
        """
        分页获取指定接收者的所有未删除通知。
        按创建时间倒序排列。
        """
        result = await db.execute(
            select(self.model)
            .where(self.model.receiver_id == receiver_id, self.model.deleted_at.is_(None))
            .order_by(self.model.created_at.desc())
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def mark_all_read(self, db: AsyncSession, *, receiver_id: int) -> int:
        """
        将指定接收者的所有未读通知一键标记为已读。
        返回受影响的行数。
        """
        result = await db.execute(
            update(self.model)
            .where(
                self.model.receiver_id == receiver_id,
                self.model.is_read == False,
                self.model.deleted_at.is_(None)
            )
            .values(is_read=True)
        )
        await db.commit()
        return result.rowcount

crud_notification = CRUDNotification(Notification)
