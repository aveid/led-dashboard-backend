"""mappers.py (presentation) — доменный User → схема UserRead."""

from __future__ import annotations

from features.users.domain.entities import User

from .schemas import UserRead


def user_to_read(user: User) -> UserRead:
    """Доменный User → схема ответа API (без пароля/хеша)."""
    return UserRead(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )
