"""
教材管理 API

端点列表：
  POST  /textbooks/upload                  教师上传 PDF，入队 Celery 解析
  GET   /textbooks/                        教师查看自己的教材列表
  GET   /textbooks/{id}/status             状态轮询（pending→processing→success/failed）
  POST  /textbooks/{id}/bind-classes       将教材（幂等）绑定到 1~N 个班级
  POST  /textbooks/{id}/reprocess          失败后重新触发解析
"""

import logging
import os
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import get_current_teacher, get_db
from db.models.course_class import CourseClass
from db.models.relations import ClassTextbook
from db.models.textbook import Textbook, TextbookStatus
from db.models.user import User
from services.file_storage import FileStorageService
from crud import crud_textbook, crud_class, crud_class_textbook

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic 校验模型
# ---------------------------------------------------------------------------

class TextbookBriefResponse(BaseModel):
    id: int
    title: str
    status: TextbookStatus
    processing_progress: int
    chroma_collection_id: str | None
    file_path: str
    created_at: str

    class Config:
        from_attributes = True


class TextbookStatusResponse(BaseModel):
    id: int
    title: str
    status: TextbookStatus
    processing_progress: int
    chroma_collection_id: str | None


class BindClassesRequest(BaseModel):
    class_ids: List[int]


class BindClassesResponse(BaseModel):
    bound_count: int
    skipped_count: int        # 总跳过数（已绑定 + 越权/无效）
    already_bound_count: int  # 其中已绑定的班级数
    invalid_count: int        # 其中越权或不存在的班级数
    message: str


# ---------------------------------------------------------------------------
# 辅助：获取属于当前教师的教材，越权/不存在则抛异常
# ---------------------------------------------------------------------------

async def _get_owned_textbook(
    textbook_id: int,
    current_user: User,
    db: AsyncSession,
) -> Textbook:
    textbook = await crud_textbook.get(db, id=textbook_id)
    if not textbook or textbook.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="教材不存在或无权操作",
        )
    return textbook


# ---------------------------------------------------------------------------
# 1. PDF 上传
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=TextbookBriefResponse,
    status_code=status.HTTP_201_CREATED,
    summary="教师上传 PDF 教材",
)
async def upload_textbook(
    title: str = Form(..., description="教材名称"),
    file: UploadFile = File(..., description="PDF 文件"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    上传 PDF 教材。

    - 校验文件类型（必须为 application/pdf）
    - 校验文件大小（≤ MAX_UPLOAD_MB）
    - 写入本地磁盘，在 DB 插入 status=PENDING 的记录
    - 投递 Celery 异步解析任务
    """
    # ── 校验 MIME 类型 ────────────────────────────────────────────────────────
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="仅支持 PDF 格式，请上传 .pdf 文件",
        )

    # ── 校验文件大小 ──────────────────────────────────────────────────────────
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content_length = file.size  # FastAPI >= 0.106 支持，客户端未发送时为 None

    if content_length is not None and content_length > max_bytes:
        # Content-Length 已知且超限，提前拒绝（不读文件内容，节省带宽）
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超出限制，最大允许 {settings.MAX_UPLOAD_MB} MB",
        )

    # ── 保存到本地磁盘（流式写入，边写边校验大小） ────────────────────────────
    storage = FileStorageService()
    try:
        relative_path, actual_size = await storage.save_with_size_check(file, max_bytes)
    except ValueError as size_exc:
        # FileStorageService 在写入过程中检测到超限时抛出 ValueError
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(size_exc),
        )
    except Exception as exc:
        logger.exception("File save failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件保存失败，请稍后重试",
        )


    # ── 写入数据库（status=PENDING）────────────────────────────────────────────
    textbook = await crud_textbook.create(
        db,
        obj_in={
            "title": title,
            "file_path": relative_path,
            "status": TextbookStatus.PENDING,
            "teacher_id": current_user.id,
        }
    )
    
    # ── 失效教材列表缓存 ────────────────────────────────────────────────────────
    try:
        from core.redis import redis_client
        await redis_client.delete(f"cache:textbooks:list:{current_user.id}")
    except Exception:
        pass

    # ── 投递 Celery 任务 ───────────────────────────────────────────────────────
    absolute_path = storage.get_absolute_path(relative_path)
    try:
        from worker.tasks import process_textbook_task
        process_textbook_task.delay(textbook.id, absolute_path)
        logger.info("Queued process_textbook_task for textbook_id=%d", textbook.id)
    except Exception as exc:
        # Celery 不可达时不影响 HTTP 响应，但记录警告（可后续手动重触发）
        logger.error("Failed to enqueue Celery task for textbook %d: %s", textbook.id, exc)

    return TextbookBriefResponse(
        id=textbook.id,
        title=textbook.title,
        status=textbook.status,
        processing_progress=textbook.processing_progress,
        chroma_collection_id=textbook.chroma_collection_id,
        file_path=textbook.file_path,
        created_at=textbook.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# 2. 教师教材列表
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=List[TextbookBriefResponse],
    summary="教师查看自己的教材列表",
)
async def list_textbooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """按创建时间倒序返回当前教师名下所有未删除的教材。"""
    from core.redis import redis_client
    import json
    
    # ── 1. 尝试从 Redis 缓存中获取 ─────────────────────────────────────────────
    cache_key = f"cache:textbooks:list:{current_user.id}"
    try:
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        logger.warning("Failed to read textbooks list cache: %s", e)

    # ── 2. 缓存未击中，查询数据库并构造成员 ───────────────────────────────────────
    textbooks = await crud_textbook.get_multi_by_teacher(db, teacher_id=current_user.id)

    response_list = [
        TextbookBriefResponse(
            id=t.id,
            title=t.title,
            status=t.status,
            processing_progress=t.processing_progress,
            chroma_collection_id=t.chroma_collection_id,
            file_path=t.file_path,
            created_at=t.created_at.isoformat(),
        )
        for t in textbooks
    ]

    # ── 3. 将结果写入 Redis 缓存（有效期 10 分钟） ─────────────────────────────
    try:
        serialized = json.dumps([item.model_dump() for item in response_list])
        await redis_client.setex(cache_key, 600, serialized)
    except Exception as e:
        logger.warning("Failed to write textbooks list cache: %s", e)

    return response_list


# ---------------------------------------------------------------------------
# 3. 状态轮询（前端 3s 轮询一次，直到 success / failed）
# ---------------------------------------------------------------------------

@router.get(
    "/{textbook_id}/status",
    response_model=TextbookStatusResponse,
    summary="查询教材解析进度",
)
async def get_textbook_status(
    textbook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    轮询教材解析状态。

    状态流转：`pending` → `processing` → `success` | `failed`
    """
    textbook = await _get_owned_textbook(textbook_id, current_user, db)
    return TextbookStatusResponse(
        id=textbook.id,
        title=textbook.title,
        status=textbook.status,
        processing_progress=textbook.processing_progress,
        chroma_collection_id=textbook.chroma_collection_id,
    )


# ---------------------------------------------------------------------------
# 4. 班级绑定（幂等）
# ---------------------------------------------------------------------------

@router.post(
    "/{textbook_id}/bind-classes",
    response_model=BindClassesResponse,
    summary="将教材绑定到班级",
)
async def bind_classes(
    textbook_id: int,
    body: BindClassesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    将已解析成功的教材幂等绑定到 1 个或多个班级。

    - 教材必须属于当前教师且 status == SUCCESS
    - 只有属于当前教师的班级才会被绑定（过滤掉越权班级）
    - 已绑定的跳过（幂等），返回 `skipped_count`
    """
    textbook = await _get_owned_textbook(textbook_id, current_user, db)

    if textbook.status != TextbookStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"教材尚未解析完成（当前状态：{textbook.status.value}），无法绑定班级",
        )

    if not body.class_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="class_ids 不能为空",
        )

    # 只取属于当前教师的班级（防止越权）
    classes = await crud_class.get_multi_by_ids_and_teacher(
        db, class_ids=body.class_ids, teacher_id=current_user.id
    )
    valid_class_ids = {cls.id for cls in classes}

    # 查出已存在的绑定（幂等检查）
    existing_bindings = await crud_class_textbook.get_multi_by_textbook_and_classes(
        db, textbook_id=textbook_id, class_ids=list(valid_class_ids)
    )
    already_bound = {b.class_id for b in existing_bindings}

    # 细化分拆：越权或不存在的班级数 / 已绑定数 / 本次新增绑定数
    invalid_count = len(body.class_ids) - len(valid_class_ids)
    already_bound_count = len(already_bound)
    to_bind = valid_class_ids - already_bound
    skipped_count = invalid_count + already_bound_count

    for class_id in to_bind:
        await crud_class_textbook.create_or_restore(db, class_id=class_id, textbook_id=textbook_id)

    # ── 绑定关系发生改变，必须失效教师主看板数据缓存 ────────────────────────────────
    try:
        from core.redis import redis_client
        await redis_client.delete(f"cache:teacher_dashboard:{current_user.id}")
    except Exception:
        pass

    return BindClassesResponse(
        bound_count=len(to_bind),
        skipped_count=skipped_count,
        already_bound_count=already_bound_count,
        invalid_count=invalid_count,
        message="绑定成功" if to_bind else "所有班级均已绑定，无需重复操作",
    )


# ---------------------------------------------------------------------------
# 5. 失败重试（reprocess）
# ---------------------------------------------------------------------------

@router.post(
    "/{textbook_id}/reprocess",
    summary="重新触发教材解析（仅限 failed 状态）",
)
async def reprocess_textbook(
    textbook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    将 status=failed 的教材重置为 pending 并重新投递 Celery 任务。
    只有最终失败（failed）的教材才允许重试。
    """
    textbook = await _get_owned_textbook(textbook_id, current_user, db)

    if textbook.status != TextbookStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"只有 failed 状态的教材才可重新解析（当前状态：{textbook.status.value}）",
        )

    # ── 先校验原始文件是否存在，再修改状态（避免文件缺失时状态被破坏卡死在 PENDING）
    storage = FileStorageService()
    absolute_path = storage.get_absolute_path(textbook.file_path)

    if not os.path.exists(absolute_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原始文件已不存在，请重新上传教材",
        )

    # ── 文件确认存在后，再重置状态 ────────────────────────────────────────────
    await crud_textbook.update(
        db,
        db_obj=textbook,
        obj_in={"status": TextbookStatus.PENDING, "chroma_collection_id": None}
    )
    
    # ── 重新投递解析，失效列表缓存，使其呈现 pending ────────────────────────────
    try:
        from core.redis import redis_client
        await redis_client.delete(f"cache:textbooks:list:{current_user.id}")
    except Exception:
        pass

    # ── 投递 Celery 任务 ───────────────────────────────────────────────────────
    try:
        from worker.tasks import process_textbook_task
        process_textbook_task.delay(textbook.id, absolute_path)
        logger.info("Re-queued process_textbook_task for textbook_id=%d", textbook.id)
    except Exception as exc:
        logger.error("Failed to re-enqueue task for textbook %d: %s", textbook.id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务队列暂时不可用，请稍后重试",
        )

    return {
        "id": textbook.id,
        "status": TextbookStatus.PENDING.value,
        "message": "已重新提交解析任务，请稍后轮询状态",
    }


# ---------------------------------------------------------------------------
# 6. 教材解绑班级
# ---------------------------------------------------------------------------

@router.delete(
    "/{textbook_id}/unbind-classes",
    summary="解绑教材与班级的关联",
)
async def unbind_classes(
    textbook_id: int,
    body: BindClassesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    解除已绑定的教材与班级的关系（软删除中间表记录）。
    """
    textbook = await _get_owned_textbook(textbook_id, current_user, db)

    if not body.class_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="class_ids 不能为空",
        )

    # 查出已存在的绑定记录（仅查询传入的且教师拥有权限的班级关联）
    classes = await crud_class.get_multi_by_ids_and_teacher(
        db, class_ids=body.class_ids, teacher_id=current_user.id
    )
    valid_class_ids = {cls.id for cls in classes}

    existing_bindings = await crud_class_textbook.get_multi_by_textbook_and_classes(
        db, textbook_id=textbook_id, class_ids=list(valid_class_ids)
    )

    unbound_count = 0
    for binding in existing_bindings:
        await crud_class_textbook.remove(db, id=binding.id)
        unbound_count += 1

    # ── 解绑教材，失效教师看板数据缓存 ──────────────────────────────────────────
    if unbound_count > 0:
        try:
            from core.redis import redis_client
            await redis_client.delete(f"cache:teacher_dashboard:{current_user.id}")
        except Exception:
            pass

    return {
        "message": "解绑成功" if unbound_count > 0 else "没有找到有效的绑定记录",
        "unbound_count": unbound_count
    }


# ---------------------------------------------------------------------------
# 7. 软删除教材
# ---------------------------------------------------------------------------

@router.delete(
    "/{textbook_id}",
    summary="软删除教材",
)
async def delete_textbook(
    textbook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    软删除特定教材。
    删除后该教材无法再被查询，且关联该教材的会话均将不可用。
    """
    textbook = await _get_owned_textbook(textbook_id, current_user, db)
    chroma_collection_id = textbook.chroma_collection_id  # 先取出，软删除后仍可引用
    file_path = textbook.file_path
    
    # ── 清理关联的班级绑定（软删除中间关系记录） ───────────────────────────
    from sqlalchemy import select
    from db.models.relations import ClassTextbook
    from db.models.chat import ChatSession
    bindings_query = select(ClassTextbook).where(
        ClassTextbook.textbook_id == textbook.id,
        ClassTextbook.deleted_at.is_(None)
    )
    bindings_result = await db.execute(bindings_query)
    for binding in bindings_result.scalars().all():
        await crud_class_textbook.remove(db, id=binding.id)

    # ── 软删除该教材下所有学生的 ChatSession（防止学生列表出现僵尸会话）──────────
    sessions_query = select(ChatSession).where(
        ChatSession.textbook_id == textbook.id,
        ChatSession.deleted_at.is_(None),
    )
    sessions_result = await db.execute(sessions_query)
    for sess in sessions_result.scalars().all():
        sess.soft_delete()
        db.add(sess)
    await db.commit()

    # ── 软删除教材主表记录 ───────────────────────────────────────────────
    await crud_textbook.remove(db, id=textbook.id)


    # ── 清理磁盘上的 PDF 物理物理文件，防止存储泄露 ────────────────────────
    if file_path:
        try:
            storage = FileStorageService()
            await storage.delete(file_path)
            logger.info("Physically deleted textbook PDF file: %s", file_path)
        except Exception as e:
            logger.warning("Failed to physically delete textbook PDF file: %s", e)

    # ── 最佳努力异步清理 ChromaDB 向量集合，避免阻塞事件循环 ───────────────
    if chroma_collection_id:
        try:
            import chromadb
            import asyncio
            chroma_client = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
            await asyncio.to_thread(chroma_client.delete_collection, name=chroma_collection_id)
            logger.info("Deleted ChromaDB collection '%s' for textbook %d", chroma_collection_id, textbook_id)
        except Exception as e:
            logger.warning("Failed to delete ChromaDB collection for textbook %d: %s", textbook_id, e)

    # ── 彻底下架，失效教材列表缓存与看板数据缓存 ────────────────────────────────────
    try:
        from core.redis import redis_client
        await redis_client.delete(f"cache:textbooks:list:{current_user.id}")
        await redis_client.delete(f"cache:teacher_dashboard:{current_user.id}")
    except Exception:
        pass

    return {"message": "教材已成功删除"}
