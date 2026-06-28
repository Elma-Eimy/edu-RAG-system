from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from core.dependencies import get_current_admin, get_db
from core.config import settings, save_config_overrides
from db.models.user import User, UserRole, UserStatus
from db.models.textbook import Textbook
from db.models.chat import ChatSession
from crud import crud_user, crud_textbook, crud_chat_session, crud_message

# 路由器不再使用 router 级统一鉴权，改为每个接口函数按需注入 get_current_admin，避免双重 DB 查询
router = APIRouter()

# 校验模型
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    status: UserStatus
    real_name: Optional[str] = None
    school_name: Optional[str] = None
    credential_code: Optional[str] = None
    credential_image_url: Optional[str] = None

    class Config:
        from_attributes = True

class ConfigResponse(BaseModel):
    LLM_API_KEY: str
    LLM_BASE_URL: str
    LLM_MODEL_NAME: str
    RAG_TOP_K: int
    TEXTBOOK_CHUNK_SIZE: int

class ConfigUpdateRequest(BaseModel):
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_MODEL_NAME: Optional[str] = None
    RAG_TOP_K: Optional[int] = Field(None, ge=1, le=20)
    TEXTBOOK_CHUNK_SIZE: Optional[int] = Field(None, ge=50, le=2000)

class NotificationCreateRequest(BaseModel):
    receiver_id: int
    title: str = Field(..., max_length=200)
    content: str

class NotificationBroadcastRequest(BaseModel):
    title: str = Field(..., max_length=200)
    content: str

class AdminTextbookResponse(BaseModel):
    id: int
    title: str
    status: str
    teacher_name: Optional[str] = None
    created_at: str

class AdminChatSessionResponse(BaseModel):
    id: int
    title: str
    student_name: str
    textbook_title: str
    summary: Optional[str] = None
    created_at: str

class AdminMessageResponse(BaseModel):
    id: int
    sender: str
    content: str
    reasoning_content: Optional[str] = None
    created_at: str

# 接口端点
@router.get("/users", response_model=List[UserResponse], summary="管理员获取用户列表")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
    role: Optional[UserRole] = None,
    status: Optional[UserStatus] = None,
    skip: int = 0,
    limit: int = 100,
):
    """
    管理员拉取所有未软删除的用户，支持按角色和状态过滤。
    """
    from sqlalchemy import select
    query = select(User).where(User.deleted_at.is_(None))
    if role:
        query = query.where(User.role == role)
    if status:
        query = query.where(User.status == status)
    # 加上稳定排序，确保分页结果不会重复或遗漏
    query = query.order_by(User.id.asc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    return users

@router.post("/users/{user_id}/approve-teacher", response_model=UserResponse, summary="审批教师资质")
async def approve_teacher(user_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin)):
    """
    批准用户教师资质。修改角色为 teacher，状态置为 active。
    仅允许对处于 FROZEN 状态的 TEACHER 角色用户执行此操作。
    """
    user = await crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 安全校验：防止将管理员降级为教师，或对已激活的用户重复操作
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不允许对管理员账号执行此操作",
        )
    if user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="该用户不是教师账号，无需审批",
        )
    if user.status != UserStatus.FROZEN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"该用户当前状态为 {user.status.value}，无需审批",
        )

    updated_user = await crud_user.update(
        db, db_obj=user, obj_in={"role": UserRole.TEACHER, "status": UserStatus.ACTIVE}
    )
    return updated_user

@router.post("/users/{user_id}/freeze", response_model=UserResponse, summary="冻结违规账号")
async def freeze_user(user_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin)):
    """
    冻结用户账号。状态置为 frozen。
    """
    user = await crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    updated_user = await crud_user.update(
        db, db_obj=user, obj_in={"status": UserStatus.FROZEN}
    )
    return updated_user

@router.post("/users/{user_id}/unfreeze", response_model=UserResponse, summary="解冻违规账号")
async def unfreeze_user(user_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin)):
    """
    解冻用户账号。状态置为 active。
    """
    user = await crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    updated_user = await crud_user.update(
        db, db_obj=user, obj_in={"status": UserStatus.ACTIVE}
    )
    return updated_user

@router.delete("/textbooks/{textbook_id}", summary="管理员强制介入软删除教材")
async def delete_textbook(
    textbook_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    介入式软删除：强制将某本教材的 deleted_at 赋值为当前时间。
    同时，系统自动向教材所属教师推送一条系统通知，通知其教材已被软删除下架。
    """
    textbook = await crud_textbook.get(db, id=textbook_id)
    if not textbook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="教材不存在或已被删除")
        
    teacher_id = textbook.teacher_id
    textbook_title = textbook.title
    chroma_collection_id = textbook.chroma_collection_id
    file_path = textbook.file_path
    
    # ── 清理关联的班级绑定（软删除中间关系记录） ───────────────────────
    from sqlalchemy import select
    from db.models.relations import ClassTextbook, StudentClass, StudentClassStatus
    from db.models.chat import ChatSession
    from crud import crud_class_textbook
    bindings_query = select(ClassTextbook).where(
        ClassTextbook.textbook_id == textbook.id,
        ClassTextbook.deleted_at.is_(None)
    )
    bindings_result = await db.execute(bindings_query)
    bindings = bindings_result.scalars().all()
    class_ids = {b.class_id for b in bindings}
    for binding in bindings:
        await crud_class_textbook.remove(db, id=binding.id)
        
    # 失效关联班级内所有学生的教材列表缓存
    if class_ids:
        try:
            from core.redis import redis_client
            student_query = select(StudentClass.student_id).where(
                StudentClass.class_id.in_(class_ids),
                StudentClass.status == StudentClassStatus.APPROVED,
                StudentClass.deleted_at.is_(None)
            )
            student_result = await db.execute(student_query)
            student_ids = student_result.scalars().all()
            for sid in student_ids:
                await redis_client.delete(f"cache:textbooks:list:student:{sid}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to invalidate student caches in admin delete_textbook: %s", e)

    # ── 软删除该教材下所有学生的 ChatSession（防止学生列表出现僵尸会话）─────
    sessions_query = select(ChatSession).where(
        ChatSession.textbook_id == textbook.id,
        ChatSession.deleted_at.is_(None),
    )
    sessions_result = await db.execute(sessions_query)
    for sess in sessions_result.scalars().all():
        sess.soft_delete()
        db.add(sess)
    await db.commit()

    # 软删除教材主表记录
    await crud_textbook.remove(db, id=textbook_id)

    # ── 失效该教材所属教师的列表与主看板数据缓存 ─────────────────────────────
    if teacher_id:
        try:
            from core.redis import redis_client
            await redis_client.delete(f"cache:textbooks:list:teacher:{teacher_id}")
            await redis_client.delete(f"cache:textbooks:list:admin:{teacher_id}")
            await redis_client.delete(f"cache:teacher_dashboard:{teacher_id}")
        except Exception:
            pass

    # ── 清理磁盘上的 PDF 物理文件，防止存储泄露 ───────────────────────────
    if file_path:
        try:
            from services.file_storage import FileStorageService
            storage = FileStorageService()
            await storage.delete(file_path)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to physically delete textbook PDF file: %s", e)
    
    # ── 最佳努力异步清理 ChromaDB 向量集合，避免事件循环阻塞 ───────────────
    if chroma_collection_id:
        try:
            import chromadb
            import asyncio
            chroma_client = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
            await asyncio.to_thread(chroma_client.delete_collection, name=chroma_collection_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to delete ChromaDB collection '%s' for textbook %d: %s",
                chroma_collection_id, textbook_id, e
            )

    # ── 清理 FTS5 全文索引记录，防存储泄露 ─────────────────────────────────
    try:
        from services.rag_optimizer import FTSIndexManager
        import logging
        FTSIndexManager.delete_document_chunks(textbook_id)
        logging.getLogger(__name__).info("Deleted SQLite FTS5 records for textbook ID: %d", textbook_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to delete SQLite FTS5 records for textbook %d: %s", textbook_id, e)
    
    # 向教师发送系统通知
    from db.models.notification import Notification
    notification = Notification(
        sender_id=current_admin.id,
        receiver_id=teacher_id,
        title=f"教材下架通知：《{textbook_title}》已被管理员下架",
        content=f"尊敬的老师，您上传的教材《{textbook_title}》（ID: {textbook_id}）由于违规或平台调整，已被管理员强制下架，特此通知。",
        is_read=False,
    )
    db.add(notification)
    await db.commit()
    
    return {"message": "教材已成功强制软删除，并已向对应教师推送通知"}

@router.delete("/chat/sessions/{session_id}", summary="管理员强制介入软删除聊天会话")
async def delete_chat_session(session_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin)):
    """
    介入式软删除：强制将某个会话的 deleted_at 赋值为当前时间。
    """
    session = await crud_chat_session.get(db, id=session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在或已被删除")
        
    await crud_chat_session.remove(db, id=session_id)
    return {"message": "会话已成功强制软删除"}

@router.get("/config", response_model=ConfigResponse, summary="获取大模型与RAG全局配置")
async def get_config(_: User = Depends(get_current_admin)):
    """
    读取当前的配置快照。
    """
    return {
        "LLM_API_KEY": settings.LLM_API_KEY,
        "LLM_BASE_URL": settings.LLM_BASE_URL,
        "LLM_MODEL_NAME": settings.LLM_MODEL_NAME,
        "RAG_TOP_K": settings.RAG_TOP_K,
        "TEXTBOOK_CHUNK_SIZE": settings.TEXTBOOK_CHUNK_SIZE,
    }

@router.put("/config", response_model=ConfigResponse, summary="动态修改大模型与RAG全局配置")
async def update_config(config_in: ConfigUpdateRequest, _: User = Depends(get_current_admin)):
    """
    动态更新大模型通道、模型名称、Top-K 检索阈值和文本切片长度。
    更新将同步回写到本地 config_override.json 配置文件以支持持久化，并在当前运行时立即生效。
    """
    update_data = config_in.model_dump(exclude_unset=True)
    save_config_overrides(update_data)
    
    return {
        "LLM_API_KEY": settings.LLM_API_KEY,
        "LLM_BASE_URL": settings.LLM_BASE_URL,
        "LLM_MODEL_NAME": settings.LLM_MODEL_NAME,
        "RAG_TOP_K": settings.RAG_TOP_K,
        "TEXTBOOK_CHUNK_SIZE": settings.TEXTBOOK_CHUNK_SIZE,
    }

@router.post("/notifications", summary="管理员向特定用户推送通知")
async def send_notification(
    notification_in: NotificationCreateRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    管理员向特定用户推送自定义消息通知。
    """
    # 检查接收者是否存在
    receiver = await crud_user.get(db, id=notification_in.receiver_id)
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="接收者用户不存在")
    
    from crud import crud_notification
    db_obj = await crud_notification.create(
        db,
        obj_in={
            "sender_id": current_admin.id,
            "receiver_id": notification_in.receiver_id,
            "title": notification_in.title,
            "content": notification_in.content,
            "is_read": False,
        }
    )
    return {"message": "通知发送成功", "id": db_obj.id}

@router.post("/notifications/broadcast", summary="管理员向全员广播通知")
async def broadcast_notification(
    notification_in: NotificationBroadcastRequest,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    管理员向所有活跃且未删除的用户广播自定义消息通知。
    """
    from sqlalchemy import select
    from db.models.notification import Notification
    
    # 查询所有未删除且活跃的用户
    result = await db.execute(
        select(User).where(User.deleted_at.is_(None), User.status == UserStatus.ACTIVE)
    )
    users = result.scalars().all()
    
    count = 0
    for u in users:
        db_obj = Notification(
            sender_id=current_admin.id,
            receiver_id=u.id,
            title=notification_in.title,
            content=notification_in.content,
            is_read=False,
        )
        db.add(db_obj)
        count += 1
        
    await db.commit()
    return {"message": f"广播发送成功，共发送给 {count} 名用户"}

@router.get("/textbooks", response_model=List[AdminTextbookResponse], summary="管理员获取所有教材列表")
async def list_all_textbooks(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 100,
):
    """
    管理员获取系统内所有教材（已排除了已软删除的）。
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    query = (
        select(Textbook)
        .where(Textbook.deleted_at.is_(None))
        .options(selectinload(Textbook.teacher))
        .order_by(Textbook.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    textbooks = result.scalars().all()
    
    return [
        AdminTextbookResponse(
            id=t.id,
            title=t.title,
            status=t.status.value,
            teacher_name=t.teacher.username if t.teacher else "系统默认",
            created_at=t.created_at.isoformat(),
        )
        for t in textbooks
    ]

@router.get("/chat/sessions", response_model=List[AdminChatSessionResponse], summary="管理员获取所有对话会话审计列表")
async def list_all_chat_sessions(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 100,
):
    """
    管理员拉取所有未被软删除的问答会话列表。
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    query = (
        select(ChatSession)
        .where(ChatSession.deleted_at.is_(None))
        .options(selectinload(ChatSession.student), selectinload(ChatSession.textbook))
        .order_by(ChatSession.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    return [
        AdminChatSessionResponse(
            id=s.id,
            title=s.title,
            student_name=s.student.username if s.student else "未知学生",
            textbook_title=s.textbook.title if s.textbook else "未知教材",
            summary=s.summary,
            created_at=s.created_at.isoformat(),
        )
        for s in sessions
    ]

@router.get("/chat/sessions/{session_id}/messages", response_model=List[AdminMessageResponse], summary="管理员调阅特定会话的全部消息历史")
async def get_admin_session_messages(
    session_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """
    管理员强力审计：直接调阅任意特定会话的全部消息历史，不受班级与教师绑定限制。
    """
    # 验证会话存在且未被删除
    from sqlalchemy import select
    query = select(ChatSession).where(ChatSession.id == session_id, ChatSession.deleted_at.is_(None))
    result = await db.execute(query)
    session_obj = result.scalars().first()
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或已被删除"
        )
        
    from crud import crud_message
    messages = await crud_message.get_multi_by_session(
        db, session_id=session_id, skip=skip, limit=limit
    )
    
    return [
        AdminMessageResponse(
            id=msg.id,
            sender=msg.sender.value,
            content=msg.content,
            reasoning_content=msg.reasoning_content,
            created_at=msg.created_at.isoformat(),
        )
        for msg in messages
    ]

