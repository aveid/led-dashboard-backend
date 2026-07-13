"""schemas.py — контракты HTTP модуля аутентификации.

LoginResponse расширяет обычный токен-ответ полем role, чтобы фронт знал роль
сразу после логина (инструкция §1.1). Источник истины о роли — GET /api/auth/me
(актуален после смены роли); role в логине — лишь удобная подсказка.
"""

from __future__ import annotations

from pydantic import BaseModel

from features.users.domain.entities import UserRole


class LoginResponse(BaseModel):
    """Ответ на вход: JWT access-токен + роль пользователя."""

    access_token: str
    token_type: str = "bearer"
    role: UserRole
