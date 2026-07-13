"""router.py — аутентификация: вход, выдача JWT и текущий пользователь (NFR-8).

За что отвечает модуль:
    • POST /api/auth/token — принимает логин/пароль (OAuth2-форма), сверяет с
      хранилищем пользователей (таблица users) и возвращает JWT access-токен + роль.
    • GET  /api/auth/me    — возвращает текущего аутентифицированного пользователя
      (источник истины о роли/активности; актуален после смены роли).

Учётные данные проверяются по БД (не по демо-настройкам): пароль сверяется с
bcrypt-хешем, деактивированный пользователь войти не может. Раздел users и гейт
require_admin живут в features/users; здесь — только вход и «кто я».
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from config.database import get_db
from config.security import create_access_token, verify_password
from core.api.auth import get_current_user
from features.users.domain.entities import User
from features.users.infrastructure.repositories import SqlAlchemyUserRepository
from features.users.presentation.mappers import user_to_read
from features.users.presentation.schemas import UserRead

from .schemas import LoginResponse

router = APIRouter(prefix="/api/auth", tags=["Аутентификация"])


@router.post("/token", response_model=LoginResponse, summary="Вход (получить JWT)")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    """Проверяет учётные данные по таблице users и возвращает access-токен + роль.

    Неверный логин/пароль или деактивированный пользователь → 401 (единый ответ,
    без раскрытия, что именно не так). Пароль сверяется с bcrypt-хешем.
    """
    user = SqlAlchemyUserRepository(db).get_by_username(form.username)
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=user.username)
    return LoginResponse(access_token=token, role=user.role)


@router.get("/me", response_model=UserRead, summary="Текущий пользователь")
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    """Возвращает текущего аутентифицированного пользователя (роль/активность из БД)."""
    return user_to_read(current_user)
