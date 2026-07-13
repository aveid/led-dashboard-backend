"""mappers.py — преобразование ORM-модели пользователя в доменную сущность."""

from __future__ import annotations

from features.users.domain.entities import User, UserRole

from .models import UserModel


def user_to_domain(model: UserModel) -> User:
    """Строка users (ORM) → доменный User (роль строки → UserRole)."""
    return User(
        username=model.username,
        password_hash=model.password_hash,
        role=UserRole(model.role),
        is_active=model.is_active,
        id=model.id,
        created_at=model.created_at,
    )
