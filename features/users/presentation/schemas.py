"""schemas.py — Pydantic-схемы (контракты HTTP) раздела «Пользователи».

Контракт (SSOT для фронтенда, всё snake_case):
    UserRead   = { id, username, role, is_active, created_at }   (пароль/хеш НИКОГДА)
    UserCreate = { username, password, role?, is_active? }
    UserUpdate = { role?, is_active?, password? }   (любое подмножество)

Роль — строковый enum "admin" | "user". Невалидная роль или слабый/пустой пароль
отсекаются здесь Pydantic'ом (→ 422) ещё до сценария.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from features.users.domain.entities import UserRole


class UserRead(BaseModel):
    """Пользователь в ответе API. Пароль/хеш не входят в схему принципиально."""

    id: int
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Тело запроса на создание пользователя.

    password ≥ 8 символов (пустой/слабый → 422). role по умолчанию USER.
    """

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.USER
    is_active: bool = True


class UserUpdate(BaseModel):
    """Тело запроса на редактирование пользователя. Все поля необязательны.

    Присланное поле применяется, отсутствующее — не трогается. password (если
    прислан) перехешируется; отсутствует — пароль остаётся прежним.
    """

    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
