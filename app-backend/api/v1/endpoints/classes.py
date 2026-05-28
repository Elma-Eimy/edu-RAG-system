"""
班级审批与流转中心 - API 端点
包含：
  - POST   /classes/           教师创建班级
  - POST   /classes/join       学生申请加入班级（输入 6 位 class_code）
  - GET    /classes/{class_id}/applications   教师查看申请列表
  - POST   /classes/{class_id}/applications/review  教师批量审批（同意/拒绝）
  - GET    /classes/dashboard  教师数据看板（班级 + 教材 + 学生清单）
"""

import logging
import random
import string
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_student, get_current_teacher, get_db
from db.models.course_class import CourseClass
from db.models.relations import ClassTextbook, StudentClass, StudentClassStatus
from db.models.textbook import Textbook
from db.models.user import User
from crud import crud_class, crud_student_class

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic 校验模型
# ---------------------------------------------------------------------------

class ClassCreate(BaseModel):
    name: str


class ClassResponse(BaseModel):
    id: int
    name: str
    class_code: str
    teacher_id: int

    class Config:
        from_attributes = True


class JoinClassRequest(BaseModel):
    class_code: str

    @field_validator("class_code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 6:
            raise ValueError("class_code 必须为 6 位")
        return v


class ApplicationResponse(BaseModel):
    """单条入班申请的视图"""
    application_id: int
    student_id: int
    student_username: str
    status: StudentClassStatus

    class Config:
        from_attributes = True


class ReviewAction(BaseModel):
    application_ids: List[int]
    action: str  # "approve" (同意) 或 "reject" (拒绝)

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        v = v.lower()
        if v not in ("approve", "reject"):
            raise ValueError("action 只能为 'approve' 或 'reject'")
        return v


class ReviewResult(BaseModel):
    updated_count: int
    action: str


# ── 数据看板校验模型 ─────────────────────────────────────────────────────────

class TextbookBrief(BaseModel):
    id: int
    title: str
    status: str

    class Config:
        from_attributes = True


class StudentBrief(BaseModel):
    student_id: int
    username: str

    class Config:
        from_attributes = True


class ClassDashboard(BaseModel):
    id: int
    name: str
    class_code: str
    textbooks: List[TextbookBrief]
    students: List[StudentBrief]

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    classes: List[ClassDashboard]


class MyClassResponse(BaseModel):
    """\u5b66\u751f\u4e2a\u4eba\u73ed\u7ea7\u5217\u8868\u89c6\u56fe"""
    application_id: int
    class_id: int
    class_name: str
    class_code: str
    teacher_id: int
    application_status: StudentClassStatus

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def generate_class_code(length: int = 6) -> str:
    """生成随机大写字母+数字的班级码。"""
    characters = string.ascii_uppercase + string.digits
    return "".join(random.choice(characters) for _ in range(length))


async def _get_class_owned_by_teacher(
    class_id: int,
    current_user: User,
    db: AsyncSession,
) -> CourseClass:
    """获取属于当前教师的班级，不存在或越权则抛 404/403。"""
    course_class = await crud_class.get(db, id=class_id)
    if course_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="班级不存在")
    if course_class.teacher_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作此班级")
    return course_class


# ---------------------------------------------------------------------------
# 1. 教师创建班级
# ---------------------------------------------------------------------------

@router.post("/", response_model=ClassResponse, summary="教师创建班级")
async def create_class(
    class_in: ClassCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    创建新班级，自动生成唯一 6 位班级码。
    碰撞时最多重试 3 次。
    """
    max_retries = 3
    for attempt in range(max_retries):
        code = generate_class_code()
        try:
            new_class = await crud_class.create(
                db,
                obj_in={
                    "name": class_in.name,
                    "class_code": code,
                    "teacher_id": current_user.id,
                }
            )
            # ── 失效看板缓存 ──────────────────────────────────────────────────────────
            try:
                from core.redis import redis_client
                await redis_client.delete(f"cache:teacher_dashboard:{current_user.id}")
            except Exception:
                pass
            return new_class
        except IntegrityError:
            await db.rollback()
            if attempt == max_retries - 1:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="多次尝试后仍无法生成唯一班级码，请稍后重试。",
                )


# ---------------------------------------------------------------------------
# 5. 教师数据看板  ← 必须在 /{class_id} 参数路由之前注册，避免被误匹配
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_model=DashboardResponse, summary="教师数据看板")
async def teacher_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    拉取当前教师名下所有班级，以及每个班级下的：
    - 教材清单（通过 ClassTextbook 关联）
    - 已审批通过（APPROVED）的学生清单
    """
    from core.redis import redis_client
    import json
    
    # ── 1. 尝试从 Redis 缓存中获取 ─────────────────────────────────────────────
    cache_key = f"cache:teacher_dashboard:{current_user.id}"
    try:
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        logger.warning("Failed to read teacher dashboard cache: %s", e)

    # ── 2. 缓存未击中，查询数据库 ───────────────────────────────────────────────
    classes = await crud_class.get_multi_by_teacher(db, teacher_id=current_user.id)

    dashboard_classes: List[ClassDashboard] = []
    for cls in classes:
        # 教材：过滤掉已软删除的关联
        textbooks = [
            TextbookBrief(
                id=link.textbook.id,
                title=link.textbook.title,
                status=link.textbook.status.value,
            )
            for link in cls.textbook_links
            if link.deleted_at is None and link.textbook and link.textbook.deleted_at is None
        ]

        # 学生：只取已审批通过且未被软删除的
        students = [
            StudentBrief(
                student_id=link.student.id,
                username=link.student.username,
            )
            for link in cls.student_links
            if link.deleted_at is None
            and link.status == StudentClassStatus.APPROVED
            and link.student
            and link.student.deleted_at is None
        ]

        dashboard_classes.append(
            ClassDashboard(
                id=cls.id,
                name=cls.name,
                class_code=cls.class_code,
                textbooks=textbooks,
                students=students,
            )
        )

    response_data = DashboardResponse(classes=dashboard_classes)

    # ── 3. 将结果写入 Redis 缓存（有效期 10 分钟） ─────────────────────────────
    try:
        await redis_client.setex(
            cache_key,
            600,
            response_data.model_dump_json()
        )
    except Exception as e:
        logger.warning("Failed to write teacher dashboard cache: %s", e)

    return response_data


# ---------------------------------------------------------------------------
# 6†. 学生查看自己的班级列表  ← 必须在 /{class_id} 参数路由之前注册
# ---------------------------------------------------------------------------

@router.get("/my-classes", response_model=List[MyClassResponse], summary="学生查看自己的班级列表")
async def list_my_classes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """
    学生获取自己所有已申请或已加入的班级列表，按申请时间倒序。
    每条记录包含：班级基本信息 + 当前升班申请状态（pending / approved / rejected）。
    """
    records = await crud_student_class.get_multi_by_student(db, student_id=current_user.id)
    return [
        MyClassResponse(
            application_id=sc.id,
            class_id=cls.id,
            class_name=cls.name,
            class_code=cls.class_code,
            teacher_id=cls.teacher_id,
            application_status=sc.status,
        )
        for sc, cls in records
    ]


# ---------------------------------------------------------------------------
# 2. 学生申请加入班级
# ---------------------------------------------------------------------------

@router.post("/join", status_code=status.HTTP_201_CREATED, summary="学生申请加入班级")
async def join_class(
    body: JoinClassRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """
    学生输入 6 位 class_code 申请加班。
    - 若班级不存在 → 404
    - 若已有 pending/approved 记录 → 409
    - 成功则生成一条 status=PENDING 的 StudentClass 记录
    """
    # 查找班级
    course_class = await crud_class.get_by_code(db, class_code=body.class_code)
    if course_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="班级码无效，请核对后重试")

    # 幂等性检查：已有未被拒绝的申请（且未软删除）
    existing = await crud_student_class.get_pending_or_approved_by_student_and_class(
        db, student_id=current_user.id, class_id=course_class.id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="您已申请加入该班级或已在班级中，请勿重复提交",
        )

    # 使用 create_or_restore：若曾经退出/被踢，复用旧记录并重置为 PENDING，避免唯一约束冲突
    application = await crud_student_class.create_or_restore(
        db, student_id=current_user.id, class_id=course_class.id
    )

    return {
        "application_id": application.id,
        "class_id": course_class.id,
        "class_name": course_class.name,
        "status": application.status,
        "message": "申请已提交，请等待教师审批",
    }


# ---------------------------------------------------------------------------
# 3. 教师查看申请列表
# ---------------------------------------------------------------------------

@router.get(
    "/{class_id}/applications",
    response_model=List[ApplicationResponse],
    summary="教师查看班级申请列表",
)
async def list_applications(
    class_id: int,
    filter_status: Optional[StudentClassStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    教师查看指定班级下的入班申请。
    可通过 `filter_status` 按状态筛选（pending / approved / rejected）。
    """
    await _get_class_owned_by_teacher(class_id, current_user, db)

    results = await crud_student_class.get_applications_by_class(
        db, class_id=class_id, status_filter=filter_status
    )

    return [
        ApplicationResponse(
            application_id=sc.id,
            student_id=sc.student_id,
            student_username=user.username,
            status=sc.status,
        )
        for sc, user in results
    ]


# ---------------------------------------------------------------------------
# 4. 教师批量审批申请
# ---------------------------------------------------------------------------

@router.post(
    "/{class_id}/applications/review",
    response_model=ReviewResult,
    summary="教师批量审批入班申请",
)
async def review_applications(
    class_id: int,
    body: ReviewAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    批量同意（approve）或拒绝（reject）指定的申请 ID。
    - 只有属于当前教师班级且处于 PENDING 状态的申请才会被更新。
    - 返回实际更新的条数。
    """
    await _get_class_owned_by_teacher(class_id, current_user, db)

    new_status = (
        StudentClassStatus.APPROVED if body.action == "approve" else StudentClassStatus.REJECTED
    )

    # 单条 SQL 批量更新，一次事务提交，避免 N 次 commit 导致的部分提交风险
    updated_count = await crud_student_class.bulk_update_status(
        db,
        application_ids=body.application_ids,
        class_id=class_id,
        new_status=new_status,
    )

    # ── 失效看板缓存 ──────────────────────────────────────────────────────────
    try:
        from core.redis import redis_client
        await redis_client.delete(f"cache:teacher_dashboard:{current_user.id}")
    except Exception:
        pass

    return ReviewResult(updated_count=updated_count, action=body.action)


# ---------------------------------------------------------------------------
# 6. 教师移除学生（踢出）
# ---------------------------------------------------------------------------

@router.delete(
    "/{class_id}/students/{student_id}",
    summary="教师将学生从班级中移除",
)
async def remove_student_from_class(
    class_id: int,
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    将学生从当前班级中软删除。
    - 仅限班级的创建教师操作。
    - 若学生原本不在班级中则返回 404。
    """
    await _get_class_owned_by_teacher(class_id, current_user, db)

    student_class_record = await crud_student_class.get_by_student_and_class(
        db, student_id=student_id, class_id=class_id
    )
    if not student_class_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该学生不在当前班级中",
        )

    # 区分：PENDING 申请应走「拒绝」，APPROVED 成员才是「移除」
    if student_class_record.status == StudentClassStatus.PENDING:
        # 仅将申请状态改为拒绝，而非执行移除操作，语义更准确
        await crud_student_class.update(
            db, db_obj=student_class_record, obj_in={"status": StudentClassStatus.REJECTED}
        )
        action_desc = "申请已拒绝"
    else:
        await crud_student_class.remove(db, id=student_class_record.id)
        action_desc = "已成功将学生移除该班级"

    # ── 失效看板缓存 ──────────────────────────────────────────────────────────
    try:
        from core.redis import redis_client
        await redis_client.delete(f"cache:teacher_dashboard:{current_user.id}")
    except Exception:
        pass

    return {"message": action_desc}


# ---------------------------------------------------------------------------
# 7. 教师解散班级
# ---------------------------------------------------------------------------

@router.delete(
    "/{class_id}",
    summary="教师解散班级",
)
async def disband_class(
    class_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher),
):
    """
    软删除整个班级。
    执行后，班级将不再显示，且该班级下所有学生与关联教材的会话权限也会自动被切断。
    """
    course_class = await _get_class_owned_by_teacher(class_id, current_user, db)
    
    # ── 清理该班级下的所有学生加入记录与教材绑定记录（软删除中间表关系） ─────────────────
    from sqlalchemy import select
    from db.models.relations import StudentClass, ClassTextbook
    from db.models.chat import ChatSession
    from crud import crud_student_class, crud_class_textbook
    
    # 1. 软删除学生与班级关联
    sc_query = select(StudentClass).where(
        StudentClass.class_id == course_class.id,
        StudentClass.deleted_at.is_(None)
    )
    sc_result = await db.execute(sc_query)
    for sc in sc_result.scalars().all():
        await crud_student_class.remove(db, id=sc.id)
        
    # 2. 软删除教材与班级关联，并记录受影响的教材 ID（后续清理 ChatSession 需要）
    ct_query = select(ClassTextbook).where(
        ClassTextbook.class_id == course_class.id,
        ClassTextbook.deleted_at.is_(None)
    )
    ct_result = await db.execute(ct_query)
    ct_list = ct_result.scalars().all()
    affected_textbook_ids = [ct.textbook_id for ct in ct_list]
    for ct in ct_list:
        await crud_class_textbook.remove(db, id=ct.id)

    # 3. 软删除学生在该班级教材下的 ChatSession，防止列表中出现失效会话
    if affected_textbook_ids:
        sessions_query = select(ChatSession).where(
            ChatSession.textbook_id.in_(affected_textbook_ids),
            ChatSession.deleted_at.is_(None),
        )
        sessions_result = await db.execute(sessions_query)
        for sess in sessions_result.scalars().all():
            sess.soft_delete()
            db.add(sess)
        await db.commit()
        logger.info(
            "Soft-deleted chat sessions for disbanded class %d (textbooks: %s)",
            course_class.id, affected_textbook_ids,
        )

    # 4. 软删除班级主记录
    await crud_class.remove(db, id=course_class.id)
    
    # ── 失效看板缓存 ──────────────────────────────────────────────────────────
    try:
        from core.redis import redis_client
        await redis_client.delete(f"cache:teacher_dashboard:{current_user.id}")
    except Exception:
        pass

    return {"message": "班级已解散"}


# ---------------------------------------------------------------------------
# 8. 学生主动退出班级
# ---------------------------------------------------------------------------

@router.delete(
    "/{class_id}/quit",
    summary="学生主动退出班级",
)
async def quit_class(
    class_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """
    学生主动退出已加入或正在申请中的班级（软删除关联记录）。
    """
    student_class_record = await crud_student_class.get_by_student_and_class(
        db, student_id=current_user.id, class_id=class_id
    )
    
    if not student_class_record:
        # 如果获取不到，说明可能已经被拒绝、软删除，或者根本没申请过
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="您当前不在该班级或已退出",
        )

    # 获取 teacher_id 以失效看板缓存
    course_class = await crud_class.get(db, id=class_id)
    teacher_id = course_class.teacher_id if course_class else None

    await crud_student_class.remove(db, id=student_class_record.id)
    
    # ── 失效看板缓存 ──────────────────────────────────────────────────────────
    if teacher_id:
        try:
            from core.redis import redis_client
            await redis_client.delete(f"cache:teacher_dashboard:{teacher_id}")
        except Exception:
            pass

    return {"message": "已成功退出班级"}
