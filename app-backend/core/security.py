from datetime import datetime, timezone, timedelta
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext
from core.config import settings

# 初始化 bcrypt 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与数据库中存储的哈希值是否匹配。"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成给定明文密码的哈希加密串。"""
    return pwd_context.hash(password)

def create_access_token(
    subject: Union[str, Any], role: str, expires_delta: timedelta | None = None
) -> str:
    """
    创建用户访问令牌 (JWT Access Token)。
    
    参数:
        subject: 令牌主体，一般为用户 ID
        role: 用户角色角色字符串
        expires_delta: 令牌自定义有效期，不指定则使用系统默认期限
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject), "role": role}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

