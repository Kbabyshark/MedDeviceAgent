"""
安全模块：JWT Token 生成/验证、密码哈希。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


# ============================================================
# Password
# ============================================================


def hash_password(password: str) -> str:
    """哈希密码。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码。"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ============================================================
# JWT
# ============================================================


def create_access_token(user_id: int, role: str = "user", expires_delta: timedelta | None = None) -> str:
    """生成 JWT access token。"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt.access_token_expire_minutes)
    )
    to_encode = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(to_encode, settings.jwt.secret_key, algorithm=settings.jwt.algorithm)


def decode_access_token(token: str) -> dict:
    """解析 JWT token，返回 payload；验证失败则抛出异常。"""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt.secret_key, algorithms=[settings.jwt.algorithm])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e
