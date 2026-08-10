"""
POST /api/v1/auth/register — 用户注册
POST /api/v1/auth/login    — JWT 登录

首次启动自动创建默认管理员 admin / admin123。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import create_access_token, hash_password, verify_password
from app.core.logger import get_logger
from app.models.repositories import UserRepository
from app.schemas.user import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from app.schemas.common import APIResponse

logger = get_logger(__name__)
router = APIRouter(tags=["auth"])
_user_repo = UserRepository()


async def _ensure_default_admin():
    """首次启动时创建默认管理员账号（如已存在则跳过）。"""
    from app.core.database import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        try:
            existing = await _user_repo.get_by_username(session, "admin")
            if existing is None:
                await _user_repo.create(
                    session,
                    username="admin",
                    password_hash=hash_password("admin123"),
                    role="admin",
                )
                await session.commit()
                logger.info("default_admin_created", username="admin")
        except Exception as e:
            await session.rollback()
            logger.warning("default_admin_init_failed", error=str(e))


@router.post("/auth/register", response_model=APIResponse[UserResponse])
async def register(
    req: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> APIResponse[UserResponse]:
    """用户注册。

    默认角色为 user，不允许自行注册为 admin。
    """
    # 重名检测
    existing = await _user_repo.get_by_username(session, req.username)
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    # 创建用户
    user = await _user_repo.create(
        session,
        username=req.username,
        password_hash=hash_password(req.password),
        role="user",
        phone=req.phone,
        email=req.email,
    )

    logger.info("user_registered", username=req.username, user_id=user["user_id"])

    return APIResponse(
        message="注册成功",
        data=UserResponse(
            user_id=user["user_id"],
            username=user["username"],
            role=user["role"],
            phone=user["phone"],
            email=user["email"],
            status=user["status"],
            created_at=user["created_at"],
        ),
    )


@router.post("/auth/login", response_model=APIResponse[LoginResponse])
async def login(
    req: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> APIResponse[LoginResponse]:
    """用户登录，返回 JWT Token。

    测试账号（首次启动自动创建）：
    - admin / admin123
    """
    user = await _user_repo.get_by_username(session, req.username)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if user["status"] != 1:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(user["user_id"], role=user["role"])

    logger.info("user_login", username=req.username, user_id=user["user_id"], role=user["role"])

    return APIResponse(
        message="登录成功",
        data=LoginResponse(
            access_token=token,
            user_id=user["user_id"],
            role=user["role"],
            username=user["username"],
        ),
    )
