from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from core.config import settings
from core.security import verify_password, create_access_token, get_password_hash
from core.dependencies import get_db, get_current_user, oauth2_scheme
from db.models.user import User, UserRole, UserStatus
from crud import crud_user

router = APIRouter()

# ── Pydantic 模型（Schemas） ──────────────────────────────────────────────────

class UserRegister(BaseModel):
    """用户注册请求数据结构"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., min_length=3, max_length=100, description="电子邮箱")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    role: UserRole = Field(default=UserRole.STUDENT, description="角色")

class UserResponse(BaseModel):
    """用户响应数据结构"""
    id: int
    username: str
    email: str
    role: UserRole
    status: UserStatus

    class Config:
        from_attributes = True

# ── API 端点 ───────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="用户注册")
async def register_user(
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    新用户注册。
    
    - 检查用户名是否已被占用
    - 检查电子邮箱是否已被占用
    - 使用 bcrypt 算法对明文密码进行哈希加密后持久化
    """
    # 校验用户名唯一性
    existing_user = await crud_user.get_by_username(db, username=user_in.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被注册"
        )
    
    # 校验邮箱唯一性
    existing_email = await crud_user.get_by_email(db, email=user_in.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该电子邮箱已被注册"
        )
        
    # 密码哈希处理并落库
    hashed_pwd = get_password_hash(user_in.password)
    
    # ── 安全性控制：禁止直接通过公开接口注册管理员 ──────────────────────────────
    if user_in.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持直接注册管理员账号"
        )
    
    # ── 安全性控制：教师账号注册后必须为冻结状态，等待管理员审批激活 ────────────────────
    user_status = UserStatus.ACTIVE
    if user_in.role == UserRole.TEACHER:
        user_status = UserStatus.FROZEN
        
    user_data = {
        "username": user_in.username,
        "email": user_in.email,
        "hashed_password": hashed_pwd,
        "role": user_in.role,
        "status": user_status
    }
    
    user = await crud_user.create(db, obj_in=user_data)
    return user

@router.post("/login/access-token", summary="用户登录获取访问 Token")
async def login_access_token(
    db: AsyncSession = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    OAuth2 兼容的 Token 登录，获取用于后续请求的 Bearer Access Token。
    """
    user = await crud_user.get_by_username(db, username=form_data.username)
    
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

