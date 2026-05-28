"""
会话与对话接口

端点列表：
  POST /chat/sessions              创建会话（已有）
  GET  /chat/sessions              拉取当前学生的会话列表
  GET  /chat/sessions/{id}/messages  历史消息列表（新增）
  POST /chat/stream                SSE 流式问答（含真实 RAG 链路）
"""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import get_current_student, get_current_teacher, get_current_user, get_db
from db.database import AsyncSessionLocal
from db.models.chat import ChatSession, Message, SenderRole
from db.models.course_class import CourseClass
from db.models.relations import ClassTextbook, StudentClass, StudentClassStatus
from db.models.textbook import Textbook, TextbookStatus
from db.models.user import User, UserRole
from crud import crud_chat_session, crud_message
from services.ai_service import AIService
from services.rag_service import RAGService

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class ChatSessionCreate(BaseModel):
    title: str = Field(..., max_length=100, description="会话标题，最长 100 字")
    textbook_id: int


class ChatMessageRequest(BaseModel):
    session_id: int
    content: str


class MessageResponse(BaseModel):
    id: int
    sender: SenderRole
    content: str
    created_at: str  # ISO-8601 字符串，前端直接渲染

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    id: int
    title: str
    textbook_id: int
    created_at: str

    class Config:
        from_attributes = True


class TeacherChatSessionResponse(BaseModel):
    id: int
    title: str
    student_id: int
    student_name: str
    textbook_id: int
    textbook_title: str
    class_id: int
    class_name: str
    summary: str | None
    summary_updated_at: str | None
    created_at: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# 辅助：鉴权 —— 确认会话属于当前学生
# ---------------------------------------------------------------------------

async def _get_owned_session(
    session_id: int,
    current_user: User,
    db: AsyncSession,
) -> ChatSession:
    session = await crud_chat_session.get_by_student(db, session_id=session_id, student_id=current_user.id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return session


# ---------------------------------------------------------------------------
# 1. 创建会话
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=ChatSessionResponse, summary="创建 Chat 会话")
async def create_chat_session(
    session_in: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    为指定教材创建新会话。
    - 学生：必须通过已审批（APPROVED）的班级关联教材。
    - 教师：特许创建其名下状态为 SUCCESS 的教材的测试会话。
    - 管理员：可为系统内任意状态为 SUCCESS 的教材创建会话。
    """
    if current_user.role == UserRole.STUDENT:
        # 学生校验逻辑：必须与教材所在班级绑定
        query = (
            select(Textbook)
            .join(ClassTextbook, ClassTextbook.textbook_id == Textbook.id)
            .join(StudentClass, StudentClass.class_id == ClassTextbook.class_id)
            .join(CourseClass, CourseClass.id == ClassTextbook.class_id)
            .where(
                Textbook.id == session_in.textbook_id,
                Textbook.deleted_at.is_(None),
                StudentClass.student_id == current_user.id,
                StudentClass.status == StudentClassStatus.APPROVED,
                StudentClass.deleted_at.is_(None),
                ClassTextbook.deleted_at.is_(None),
                CourseClass.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        textbook = result.scalars().first()
        if not textbook:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="教材不存在或您没有访问权限",
            )
    elif current_user.role == UserRole.TEACHER:
        # 教师校验逻辑：只能测试自己名下解析成功的教材
        query = (
            select(Textbook)
            .where(
                Textbook.id == session_in.textbook_id,
                Textbook.teacher_id == current_user.id,
                Textbook.status == TextbookStatus.SUCCESS,
                Textbook.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        textbook = result.scalars().first()
        if not textbook:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="教材不存在、尚未解析完成或您没有该教材的测试权限",
            )
    elif current_user.role == UserRole.ADMIN:
        # 管理员校验逻辑：可以测试系统内任何解析成功的教材
        query = (
            select(Textbook)
            .where(
                Textbook.id == session_in.textbook_id,
                Textbook.status == TextbookStatus.SUCCESS,
                Textbook.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        textbook = result.scalars().first()
        if not textbook:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="教材不存在或尚未解析完成",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前用户角色无权创建问答会话",
        )

    new_session = await crud_chat_session.create(
        db,
        obj_in={
            "title": session_in.title,
            "student_id": current_user.id,
            "textbook_id": session_in.textbook_id,
        }
    )

    return ChatSessionResponse(
        id=new_session.id,
        title=new_session.title,
        textbook_id=new_session.textbook_id,
        created_at=new_session.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# 2. 拉取当前学生的会话列表
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=List[ChatSessionResponse], summary="获取学生会话列表")
async def list_chat_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """按创建时间倒序返回当前学生未删除的所有会话。教师审计请使用 GET /chat/teacher/student-chats。"""
    sessions = await crud_chat_session.get_multi_by_student(db, student_id=current_user.id)

    return [
        ChatSessionResponse(
            id=s.id,
            title=s.title,
            textbook_id=s.textbook_id,
            created_at=s.created_at.isoformat(),
        )
        for s in sessions
    ]


# ---------------------------------------------------------------------------
# 3. 历史消息列表（学生刷新页面时调用）
# ---------------------------------------------------------------------------

@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[MessageResponse],
    summary="获取会话历史消息",
)
async def get_session_messages(
    session_id: int,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),  # 仅学生本人可访问自己的会话消息
):
    """
    拉取指定会话下的全部历史消息（按 created_at 升序，即对话时间顺序）。

    - skip / limit 支持分页，前端首次加载建议 limit=50，上翻时增加 skip。
    - 只有会话归属学生本人才可访问（隐式校验）。
    """
    await _get_owned_session(session_id, current_user, db)
    messages = await crud_message.get_multi_by_session(db, session_id=session_id, skip=skip, limit=limit)

    return [
        MessageResponse(
            id=msg.id,
            sender=msg.sender,
            content=msg.content,
            created_at=msg.created_at.isoformat(),
        )
        for msg in messages
    ]


# ---------------------------------------------------------------------------
# 4. SSE 流式问答（含真实 RAG 检索链路）
# ---------------------------------------------------------------------------

@router.post("/stream", summary="SSE 流式问答（含 RAG 上下文）")
async def stream_chat(
    chat_in: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    完整的 RAG 问答链路：

    1. 校验会话归属权限
    2. 持久化用户消息
    3. 从 DB 获取最近 CHAT_HISTORY_WINDOW 轮对话（每轮 = user + ai 各一条）
    4. 向 ChromaDB 检索教材相关文本块（textbook_vec_<id>）
    5. 将历史 + RAG 上下文组装为 messages，流式调用大模型
    6. 流式传输结束后持久化 AI 回复内容
    """
    # 1. 权限鉴别
    session = await _get_owned_session(chat_in.session_id, current_user, db)
    
    # 提前获取 session 的非惰性加载 ID 及教材 ID，防止异步生成器中发生连接已释放导致的游离对象属性访问错误（DetachedInstanceError）
    session_id = session.id
    textbook_id = session.textbook_id

    # 1.1. 实时拦截鉴权（防御“影子越权”漏洞）
    if current_user.role == UserRole.STUDENT:
        # 校验：此学生当前是否仍在已授权的、绑定了该教材的有效班级中
        auth_query = (
            select(Textbook.id)
            .join(ClassTextbook, ClassTextbook.textbook_id == Textbook.id)
            .join(StudentClass, StudentClass.class_id == ClassTextbook.class_id)
            .join(CourseClass, CourseClass.id == ClassTextbook.class_id)
            .where(
                Textbook.id == textbook_id,
                Textbook.deleted_at.is_(None),
                StudentClass.student_id == current_user.id,
                StudentClass.status == StudentClassStatus.APPROVED,
                StudentClass.deleted_at.is_(None),
                ClassTextbook.deleted_at.is_(None),
                CourseClass.deleted_at.is_(None),
            )
        )
        auth_result = await db.execute(auth_query)
        if not auth_result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="该会话关联的教材或班级已被解绑、软删除或您已被移出班级，无法继续对话",
            )
    elif current_user.role == UserRole.TEACHER:
        # 教师实时鉴权：校验该教材仍属于当前教师且未被软删除
        auth_query = (
            select(Textbook.id)
            .where(
                Textbook.id == textbook_id,
                Textbook.teacher_id == current_user.id,
                Textbook.deleted_at.is_(None),
            )
        )
        auth_result = await db.execute(auth_query)
        if not auth_result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="该会话关联的教材已被删除或您已无权访问，无法继续对话",
            )

    # 2. 写入用户本次消息
    user_msg = await crud_message.create(
        db,
        obj_in={
            "session_id": session_id,
            "sender": SenderRole.USER,
            "content": chat_in.content,
        }
    )

    # 3. 提取历史窗口消息（N 轮 = N*2 条消息：用户与 AI 对答）
    #    排除刚写入的 user_msg（因为这已是最新的单次用户输入）
    window = settings.CHAT_HISTORY_WINDOW
    recent_msgs = await crud_message.get_recent_by_session(
        db,
        session_id=session_id,
        exclude_message_id=user_msg.id,
        limit=window * 2
    )

    # 转换为统一的对话格式（SenderRole.AI 转换为 "assistant"）
    history_payload = [
        {
            "role": "assistant" if msg.sender == SenderRole.AI else "user",
            "content": msg.content,
        }
        for msg in recent_msgs
    ]

    # 4 & 5. 注入 RAG 上下文并构建整体消息载荷
    rag_service = RAGService()
    messages_payload = await rag_service.build_messages(
        textbook_id=textbook_id,
        user_query=chat_in.content,
        history=history_payload,
    )

    # 6. SSE 流式请求大语言模型
    ai_service = AIService()

    async def event_generator():
        full_ai_reply = ""
        try:
            import asyncio
            stream_response = await ai_service.chat_completion(
                messages=messages_payload, stream=True
            )
            
            # 使用 asyncio.wait_for 和迭代器，为流添加 settings.RERANK_SSE_HEARTBEAT_SECONDS 秒读取超时，超时则发送 SSE 注释维持长连接心跳
            iterator = stream_response.__aiter__()
            while True:
                try:
                    chunk = await asyncio.wait_for(iterator.__anext__(), timeout=settings.RERANK_SSE_HEARTBEAT_SECONDS)
                    if chunk.choices and chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        full_ai_reply += token
                        yield f"data: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # 超时未获得新 Token，发送 SSE 规范内的空注释（心跳包），防止代理或网关超时掐断连接
                    yield ": ping\n\n"
                except StopAsyncIteration:
                    break

            # 流式迭代完毕后，使用独立的新数据库连接会话保存 AI 的完整回复内容，防止请求上下文中的主 session 已被回收
            async with AsyncSessionLocal() as generator_db:
                await crud_message.create(
                    generator_db,
                    obj_in={
                        "session_id": session_id,
                        "sender": SenderRole.AI,
                        "content": full_ai_reply,
                    }
                )

            # 异步触发会话摘要提炼任务（受 ENABLE_HISTORY_SUMMARY 开关控制）
            if settings.ENABLE_HISTORY_SUMMARY:
                try:
                    from worker.tasks import summarize_chat_session_task
                    summarize_chat_session_task.delay(session_id)
                except Exception as e:
                    logger.error("Failed to enqueue summarize_chat_session_task: %s", e)

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.exception("SSE 流式响应异常，会话 ID: %d", session_id)
            # 若 AI 已生成部分内容，保存到数据库防止对话历史出现缺口
            if full_ai_reply:
                try:
                    async with AsyncSessionLocal() as fallback_db:
                        await crud_message.create(
                            fallback_db,
                            obj_in={
                                "session_id": session_id,
                                "sender": SenderRole.AI,
                                "content": full_ai_reply + "\n\n[*回复因异常中断*]",
                            }
                        )
                except Exception as save_err:
                    logger.error("Failed to save partial AI reply: %s", save_err)
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# 5. 教师审计：获取学生问答会话列表（含摘要）
# ---------------------------------------------------------------------------

@router.get(
    "/teacher/student-chats",
    response_model=List[TeacherChatSessionResponse],
    summary="教师获取名下班级学生的会话审计列表",
)
async def get_teacher_student_chats(
    class_id: Optional[int] = None,
    student_id: Optional[int] = None,
    textbook_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    拉取当前教师所属班级的所有有效学生的会话列表，支持多条件检索与分页。
    """
    # 构造联表查询：
    # 限制 CourseClass.teacher_id 为当前教师，且学生必须处于 APPROVED 状态
    query = (
        select(
            ChatSession,
            User.username.label("student_name"),
            CourseClass.id.label("class_id"),
            CourseClass.name.label("class_name"),
            Textbook.title.label("textbook_title")
        )
        .join(User, User.id == ChatSession.student_id)
        .join(Textbook, Textbook.id == ChatSession.textbook_id)
        .join(ClassTextbook, ClassTextbook.textbook_id == ChatSession.textbook_id)
        .join(CourseClass, CourseClass.id == ClassTextbook.class_id)
        .join(
            StudentClass,
            (StudentClass.class_id == CourseClass.id) & (StudentClass.student_id == ChatSession.student_id)
        )
        .where(
            CourseClass.teacher_id == current_user.id,
            CourseClass.deleted_at.is_(None),
            StudentClass.status == StudentClassStatus.APPROVED,
            StudentClass.deleted_at.is_(None),
            ClassTextbook.deleted_at.is_(None),
            Textbook.deleted_at.is_(None),
            ChatSession.deleted_at.is_(None)
        )
    )

    if class_id is not None:
        query = query.where(CourseClass.id == class_id)
    if student_id is not None:
        query = query.where(ChatSession.student_id == student_id)
    if textbook_id is not None:
        query = query.where(ChatSession.textbook_id == textbook_id)

    query = query.order_by(ChatSession.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    response_list = []
    seen_session_ids: set[int] = set()
    for row in rows:
        session_obj = row[0]
        # 若同一教材绑定了多个班级，同一 ChatSession 可能被 JOIN 产生多行，去重处理
        if session_obj.id in seen_session_ids:
            continue
        seen_session_ids.add(session_obj.id)

        student_name = row[1]
        cls_id = row[2]
        class_name = row[3]
        textbook_title = row[4]

        response_list.append(
            TeacherChatSessionResponse(
                id=session_obj.id,
                title=session_obj.title,
                student_id=session_obj.student_id,
                student_name=student_name,
                textbook_id=session_obj.textbook_id,
                textbook_title=textbook_title,
                class_id=cls_id,
                class_name=class_name,
                summary=session_obj.summary,
                summary_updated_at=session_obj.summary_updated_at.isoformat() if session_obj.summary_updated_at else None,
                created_at=session_obj.created_at.isoformat(),
            )
        )

    return response_list


# ---------------------------------------------------------------------------
# 6. 教师审计：调阅学生特定会话的历史对话记录
# ---------------------------------------------------------------------------

@router.get(
    "/teacher/student-chats/{session_id}/messages",
    response_model=List[MessageResponse],
    summary="教师调阅学生特定会话的全部消息历史",
)
async def get_teacher_student_chat_messages(
    session_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    调阅学生单次会话的历史对话记录。包含严格的水平越权校验。
    """
    # 严格校验该会话对应的班级和学生，确保班级所有者确实为当前调用接口的教师
    auth_query = (
        select(ChatSession)
        .join(ClassTextbook, ClassTextbook.textbook_id == ChatSession.textbook_id)
        .join(CourseClass, CourseClass.id == ClassTextbook.class_id)
        .join(
            StudentClass,
            (StudentClass.class_id == CourseClass.id) & (StudentClass.student_id == ChatSession.student_id)
        )
        .where(
            ChatSession.id == session_id,
            ChatSession.deleted_at.is_(None),
            CourseClass.teacher_id == current_user.id,
            CourseClass.deleted_at.is_(None),
            StudentClass.status == StudentClassStatus.APPROVED,
            StudentClass.deleted_at.is_(None),
            ClassTextbook.deleted_at.is_(None)
        )
    )
    auth_result = await db.execute(auth_query)
    session_obj = auth_result.scalars().first()

    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="会话不存在或您没有权限调阅此会话的对话记录"
        )

    # 权限校验通过，查询消息记录
    messages = await crud_message.get_multi_by_session(
        db, session_id=session_id, skip=skip, limit=limit
    )

    return [
        MessageResponse(
            id=msg.id,
            sender=msg.sender,
            content=msg.content,
            created_at=msg.created_at.isoformat(),
        )
        for msg in messages
    ]


# ---------------------------------------------------------------------------
# 7. 删除会话 (学生清理自己的聊天列表)
# ---------------------------------------------------------------------------

@router.delete(
    "/sessions/{session_id}",
    summary="删除会话",
)
async def delete_chat_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),  # 仅学生本人可删除自己的会话
):
    """
    学生软删除自己的会话及历史消息。
    """
    session = await _get_owned_session(session_id, current_user, db)
    await crud_chat_session.remove(db, id=session.id)
    return {"message": "会话已删除"}

