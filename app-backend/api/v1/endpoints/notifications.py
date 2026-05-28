from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List

from core.dependencies import get_db, get_current_user
from db.models.user import User
from crud import crud_notification

router = APIRouter()

class NotificationResponse(BaseModel):
    """通知响应数据结构"""
    id: int
    sender_id: int | None
    receiver_id: int
    title: str
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("", response_model=List[NotificationResponse], summary="查询个人通知列表")
async def list_notifications(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前登录用户的所有未删除通知列表，按创建时间倒序排列。
    """
    notifications = await crud_notification.get_multi_by_receiver(
        db, receiver_id=current_user.id, skip=skip, limit=limit
    )
    return notifications

@router.post("/{notification_id}/read", summary="标记通知为已读")
async def read_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    将单条通知标记为已读。
    包含水平越权控制：只有当该通知的 receiver_id 与当前登录用户 id 一致时才允许修改。
    """
    notification = await crud_notification.get(db, id=notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在或已被删除"
        )
    
    # 水平越权校验
    if notification.receiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此通知"
        )
        
    await crud_notification.update(db, db_obj=notification, obj_in={"is_read": True})
    return {"message": "已成功标记为已读"}

@router.post("/read-all", summary="一键标记所有通知为已读")
async def read_all_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    将当前用户所有未读状态的通知一键标记为已读。
    """
    count = await crud_notification.mark_all_read(db, receiver_id=current_user.id)
    return {"message": f"成功将 {count} 条通知标记为已读"}

@router.delete("/{notification_id}", summary="删除单条通知")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    软删除当前用户名下的一条通知。
    包含水平越权控制：只有 receiver_id 与当前登录用户 id 一致时才允许删除。
    """
    notification = await crud_notification.get(db, id=notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在或已被删除"
        )

    # 水平越权校验
    if notification.receiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此通知"
        )

    await crud_notification.remove(db, id=notification_id)
    return {"message": "通知已删除"}
