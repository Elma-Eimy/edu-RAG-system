from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, field_validator, EmailStr
import re

from core.config import settings
from core.security import verify_password, create_access_token, get_password_hash
from core.dependencies import get_db, get_current_user, oauth2_scheme
from db.models.user import User, UserRole, UserStatus
from crud import crud_user

router = APIRouter()

from typing import Optional

# ── Pydantic 模型（Schemas） ──────────────────────────────────────────────────

class SendCodeRequest(BaseModel):
    """发送验证码请求数据结构"""
    email: EmailStr = Field(..., description="电子邮箱")

class UserRegister(BaseModel):
    """用户注册请求数据结构"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="电子邮箱")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    role: UserRole = Field(default=UserRole.STUDENT, description="角色")
    verification_code: str = Field(..., min_length=6, max_length=6, description="邮箱验证码")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if "@" in v:
            raise ValueError("用户名不能包含 '@' 字符（禁止使用邮箱作为用户名）")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("用户名仅支持英文字母、数字、下划线和减号，且不能包含空格或特殊字符")
        return v
    
    # ── 新增教师资质审核注册字段 ──────────────────────────────────────────
    real_name: Optional[str] = Field(None, max_length=50, description="真实姓名")
    school_name: Optional[str] = Field(None, max_length=100, description="学校名称")
    credential_code: Optional[str] = Field(None, max_length=50, description="教师证件编号/工作证号")
    credential_image_url: Optional[str] = Field(None, max_length=255, description="教师证件照片/图片 URL")

class UserResponse(BaseModel):
    """用户响应数据结构"""
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

# ── API 端点 ───────────────────────────────────────────────────────────────

@router.post("/send-verification-code", summary="发送邮箱验证码")
async def send_verification_code(
    payload: SendCodeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    向指定邮箱发送 6 位数随机验证码，并存入 Redis (有效期 5 分钟)。
    """
    import random
    import logging
    from core.redis import redis_client
 
    # Redis 限流校验：限制同一邮箱 60 秒内只能获取一次验证码
    rate_limit_key = f"rate_limit:send_code:{payload.email}"
    is_limited = await redis_client.get(rate_limit_key)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="验证码发送频繁，请 60 秒后再试"
        )
 
    # 1. 校验邮箱是否已被占用
    existing_email = await crud_user.get_by_email(db, email=payload.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该电子邮箱已被注册"
        )
 
    # 2. 生成 6 位随机验证码
    code = f"{random.randint(100000, 999999)}"
 
    # 3. 存入 Redis，TTL = 300 秒 (5分钟)
    redis_key = f"email_verification:{payload.email}"
    success = await redis_client.setex(redis_key, 300, code)
    if not success:
        logging.getLogger(__name__).warning("Redis setex failed for OTP. Using log fallback.")
 
    # 4. 写入限流标记
    await redis_client.setex(rate_limit_key, 60, "1")
 
    # 5. 模拟发送（打印到控制台/日志，实际生产环境可用 SMTP 发送）
    print(f"\n[EMAIL MOCK SENDER] Send verification code to {payload.email}: {code}\n")
    logging.getLogger(__name__).info(f"Verification code for {payload.email}: {code}")
 
    return {"message": "验证码已成功发送（开发环境已输出至后台控制台）"}

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="用户注册")
async def register_user(
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    新用户注册。
    
    - 校验验证码正确性
    - 检查用户名是否已被占用
    - 检查电子邮箱是否已被占用
    - 若为教师，校验是否提交了真实姓名、学校和证书资质等信息
    - 使用 bcrypt 算法对明文密码进行哈希加密后持久化
    """
    from core.redis import redis_client

    # ── 1. 验证码校验 ──────────────────────────────────────────────────────────
    redis_key = f"email_verification:{user_in.email}"
    cached_code = await redis_client.get(redis_key)
    
    if cached_code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码已过期或未发送，请重新获取"
        )
    if cached_code != user_in.verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码输入错误，请重新输入"
        )

    # ── 2. 校验用户名唯一性 ──────────────────────────────────────────────────────
    existing_user = await crud_user.get_by_username(db, username=user_in.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被注册"
        )
    
    # ── 3. 校验邮箱唯一性 ────────────────────────────────────────────────────────
    existing_email = await crud_user.get_by_email(db, email=user_in.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该电子邮箱已被注册"
        )

    # ── 4. 安全性控制：禁止直接通过公开接口注册管理员 ──────────────────────────────
    if user_in.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持直接注册管理员账号"
        )
        
    # ── 5. 教师注册资质字段必填校验 ──────────────────────────────────────────────
    user_status = UserStatus.ACTIVE
    if user_in.role == UserRole.TEACHER:
        if not all([user_in.real_name, user_in.school_name, user_in.credential_code, user_in.credential_image_url]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="教师注册必须填写真实姓名、学校、教师资格证/工作证号并上传证件照片"
            )
        user_status = UserStatus.FROZEN
        
    # 密码哈希处理
    hashed_pwd = get_password_hash(user_in.password)
    
    user_data = {
        "username": user_in.username,
        "email": user_in.email,
        "hashed_password": hashed_pwd,
        "role": user_in.role,
        "status": user_status,
        "real_name": user_in.real_name,
        "school_name": user_in.school_name,
        "credential_code": user_in.credential_code,
        "credential_image_url": user_in.credential_image_url,
    }
    
    user = await crud_user.create(db, obj_in=user_data)
    
    # 校验通过且注册成功后，销毁验证码以防二次使用 (Replay Attack)
    await redis_client.delete(redis_key)
    
    return user

@router.post("/login/access-token", summary="用户登录获取访问 Token")
async def login_access_token(
    db: AsyncSession = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    OAuth2 兼容的 Token 登录，获取用于后续请求的 Bearer Access Token。
    """
    user = await crud_user.get_by_username(db, username=form_data.username)
    if not user:
        user = await crud_user.get_by_email(db, email=form_data.username)
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名、邮箱或密码错误")
    elif user.status == UserStatus.FROZEN:
        if user.role == UserRole.TEACHER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该教师账号正在资质审核中，请联系管理员批准后再登录"
            )
        raise HTTPException(status_code=400, detail="该账户已被冻结，无法登录")
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            user.id, role=user.role.value, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.get("/me", response_model=UserResponse, summary="获取当前登录用户信息")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    获取当前会话中登录用户的个人资料。
    """
    return current_user


@router.post("/logout", summary="用户注销登录并强状态吊销 Token")
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user)
):
    """
    用户登出注销。
    计算当前 JWT 的剩余寿命，将其存入 Redis 黑名单，强制失效该凭证。
    """
    from jose import jwt
    from datetime import datetime, timezone
    from core.redis import redis_client
    
    try:
        # 解码并提取 token 的失效时间（exp）
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        exp = payload.get("exp")
        if exp:
            # 计算剩余有效秒数（TTL）
            now = int(datetime.now(timezone.utc).timestamp())
            ttl = exp - now
            if ttl > 0:
                await redis_client.setex(
                    f"token_blacklist:{token}",
                    ttl,
                    "blacklisted"
                )
    except Exception as e:
        # 即使 Redis 写入失败或 JWT 解码出错，也友好返回登出结果以确保 UX
        import logging
        logging.getLogger(__name__).error("Failed to blacklist token during logout: %s", e)
        
    return {"message": "已安全登出并注销账号凭证"}

# ── Pydantic 模型（新增修改密码与重置密码） ──────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    """修改密码请求数据结构"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")

class ResetPasswordRequest(BaseModel):
    """通过验证码重置密码请求数据结构"""
    email: EmailStr = Field(..., description="绑定的电子邮箱")
    verification_code: str = Field(..., min_length=6, max_length=6, description="邮箱验证码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


# ── 密码管理 API ────────────────────────────────────────────────────────────

@router.post("/send-reset-code", summary="发送重置密码的邮箱验证码")
async def send_reset_code(
    payload: SendCodeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    向注册邮箱发送用于重置密码的 6 位数随机验证码并存入 Redis。
    """
    import random
    import logging
    from core.redis import redis_client
 
    # Redis 限流校验
    rate_limit_key = f"rate_limit:send_code:{payload.email}"
    is_limited = await redis_client.get(rate_limit_key)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="验证码发送频繁，请 60 秒后再试"
        )
 
    # 1. 校验邮箱是否注册
    existing_email = await crud_user.get_by_email(db, email=payload.email)
    if not existing_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该电子邮箱未注册账户"
        )
 
    # 2. 生成 6 位随机验证码
    code = f"{random.randint(100000, 999999)}"
 
    # 3. 存入 Redis，TTL = 300 秒 (5分钟)
    redis_key = f"email_verification:{payload.email}"
    success = await redis_client.setex(redis_key, 300, code)
    if not success:
        logging.getLogger(__name__).warning("Redis setex failed for reset OTP. Using log fallback.")
 
    # 4. 写入限流标记
    await redis_client.setex(rate_limit_key, 60, "1")
 
    # 5. 模拟发送
    print(f"\n[EMAIL MOCK SENDER] Send password reset verification code to {payload.email}: {code}\n")
    logging.getLogger(__name__).info(f"Password reset verification code for {payload.email}: {code}")
 
    return {"message": "密码重置验证码已成功发送（开发环境已输出至后台控制台）"}


@router.post("/change-password", summary="修改当前登录用户密码")
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    当前登录用户修改自身密码。
    验证旧密码是否匹配，匹配后使用 bcrypt 加密新密码并更新。
    """
    # 验证旧密码
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前旧密码输入错误"
        )
    
    # 校验新旧密码不能相同
    if payload.old_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与旧密码相同"
        )

    # 加密并更新
    hashed_pwd = get_password_hash(payload.new_password)
    await crud_user.update(db, db_obj=current_user, obj_in={"hashed_password": hashed_pwd})
    
    return {"message": "密码修改成功，新密码已生效"}


@router.post("/reset-password", summary="通过邮箱验证码重置密码")
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    忘记密码时，通过获取并校验邮箱验证码来重置密码。
    """
    from core.redis import redis_client

    # 1. 校验邮箱对应的用户是否存在
    user = await crud_user.get_by_email(db, email=payload.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该电子邮箱未注册任何账户"
        )

    # 2. 校验验证码正确性
    redis_key = f"email_verification:{payload.email}"
    cached_code = await redis_client.get(redis_key)
    
    if cached_code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码已过期或未发送，请重新获取"
        )
    if cached_code != payload.verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码输入错误，请重新输入"
        )

    # 3. 校验新密码是否和原密码哈希相同
    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与原密码相同"
        )

    # 4. 更新密码并销毁验证码
    hashed_pwd = get_password_hash(payload.new_password)
    await crud_user.update(db, db_obj=user, obj_in={"hashed_password": hashed_pwd})
    await redis_client.delete(redis_key)
 
    return {"message": "密码重置成功，请使用新密码登录"}
 
 
@router.post("/upload-credential", summary="上传教师证件照片")
async def upload_credential(
    file: UploadFile = File(...)
):
    """
    上传教师资格证或工作证件照片。
    只允许 png, jpg, jpeg, gif 格式图片。
    保存至本地 ./uploads/credentials/ 目录。
    """
    import uuid
    import os
    import shutil
 
    # 限制上传格式
    allowed_extensions = {".png", ".jpg", ".jpeg", ".gif"}
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 PNG, JPG, JPEG, GIF 格式图片"
        )
    
    # 确保目录存在
    save_dir = os.path.join("uploads", "credentials")
    os.makedirs(save_dir, exist_ok=True)
    
    # 生成唯一文件名
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(save_dir, filename)
    
    # 异步流式写入磁盘
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件写入失败: {str(e)}"
        )
        
    # 返回相对 static URL
    url = f"/static/credentials/{filename}"
    return {"credential_image_url": url}
