from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.config import settings
from db.database import get_db
from db.models.user import User, UserRole, UserStatus

# 指向真实的登录获取 Token 接口地址，用于 Swagger 授权调试
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/users/login/access-token")

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    根据 Token 获取当前登录的用户。
    
    校验 JWT 的有效性，提取 sub 声明（用户ID），加载数据库用户并校验其状态。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="凭证校验失败，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # ── 新增：在 Redis 中前置检查此 Token 是否在吊销黑名单（已注销）中 ────────────
    try:
        from core.redis import redis_client
        is_blacklisted = await redis_client.get(f"token_blacklist:{token}")
        if is_blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="您的账号凭证已安全登出/吊销，请重新登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except Exception as e:
        # Redis 连接失败不影响主要认证流，进行降级容错
        import logging
        logging.getLogger(__name__).warning("Redis blacklist check failed, falling back: %s", e)

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_id_int = int(user_id)
    except (JWTError, ValueError):
        raise credentials_exception
        
    query = select(User).where(User.id == user_id_int, User.deleted_at.is_(None))
    result = await db.execute(query)
    user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
    if user.status == UserStatus.FROZEN:
        raise HTTPException(status_code=403, detail="该账户已被冻结")
        
    return user

def require_role(allowed_roles: list[UserRole]):
    """
    角色权限控制拦截器（RBAC 依赖）。
    """
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="操作权限不足"
            )
        return current_user
    return role_checker

# 便捷依赖注入项
get_current_admin = require_role([UserRole.ADMIN])

# 注意：管理员被纳入教师权限组，允许其调用教材上传、班级管理等教师接口（用于平台运营与调试）。
# 潜在风险：管理员通过教师路径创建的数据（班级/教材）会以管理员的 user_id 作为 teacher_id 存入库，
# 正式业务中建议管理员仅使用 /admin/* 接口，不参与具体教学活动。
get_current_teacher = require_role([UserRole.TEACHER, UserRole.ADMIN])

# 学生接口仅允许学生角色调用（不含管理员/教师，防止角色混淆）
get_current_student = require_role([UserRole.STUDENT])

