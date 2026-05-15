import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fastapi import HTTPException, status
from app.repositories.user_repository import UserRepository
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
)
from app.core.redis import cache_set, cache_exists
from app.schemas.user import RegisterRequest, TokenResponse
from app.models.user import User
from app.models.rating import RefreshToken
from app.config import settings


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)

    async def register(self, data: RegisterRequest) -> User:
        if await self.repo.get_by_email(data.email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        if await self.repo.get_by_username(data.username):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
        return await self.repo.create(
            email=data.email,
            username=data.username,
            hashed_password=hash_password(data.password),
        )

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self.repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")
        return await self._make_tokens(user.id)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

        token_hash = hash_token(refresh_token)
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked == False,
            )
        )
        stored = result.scalar_one_or_none()
        if not stored:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found or revoked")

        user_id_str = payload.get("sub")
        try:
            user_id = uuid.UUID(user_id_str)
        except (ValueError, TypeError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user id")

        user = await self.repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Инвалидируем старый refresh токен
        stored.revoked = True
        await self.db.flush()

        return await self._make_tokens(user.id)

    async def logout(self, access_token: str, refresh_token: str | None) -> None:
        # Кладём access токен в blacklist Redis
        try:
            payload = decode_token(access_token)
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                now = int(datetime.now(timezone.utc).timestamp())
                ttl = max(exp - now, 1)
                await cache_set(f"blacklist:{jti}", "1", ttl=ttl)
        except ValueError:
            pass

        # Отзываем refresh токен в БД
        if refresh_token:
            token_hash = hash_token(refresh_token)
            await self.db.execute(
                delete(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
            await self.db.flush()

    async def _make_tokens(self, user_id: uuid.UUID) -> TokenResponse:
        user_id_str = str(user_id)
        access_token = create_access_token({"sub": user_id_str})
        refresh_token, _ = create_refresh_token({"sub": user_id_str})

        # Сохраняем refresh токен в БД
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        self.db.add(RefreshToken(
            user_id=user_id,
            token_hash=hash_token(refresh_token),
            expires_at=expires_at,
        ))
        await self.db.flush()

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)