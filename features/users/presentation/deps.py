"""deps.py — зависимости FastAPI раздела «Пользователи»."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db
from features.users.application.ports import PasswordHasher
from features.users.domain.repositories import UserRepository
from features.users.infrastructure.hasher import PasslibPasswordHasher
from features.users.infrastructure.repositories import SqlAlchemyUserRepository


def get_user_repository(db: Annotated[Session, Depends(get_db)]) -> UserRepository:
    """Возвращает репозиторий пользователей, привязанный к сессии текущего запроса."""
    return SqlAlchemyUserRepository(db)


def get_password_hasher() -> PasswordHasher:
    """Возвращает хешер паролей (bcrypt поверх config.security)."""
    return PasslibPasswordHasher()
