"""dto.py — DTO прикладного слоя раздела «Пользователи».

Простые неизменяемые контейнеры данных для входа сценариев, отвязанные от HTTP и
БД. В UpdateUserInput поля необязательны: None означает «не менять» (у role,
is_active и password осмысленного null нет, поэтому отдельный флаг «прислано vs
явный null» не нужен — в отличие от nullable-даты у экрана).
"""

from __future__ import annotations

from dataclasses import dataclass

from features.users.domain.entities import UserRole


@dataclass(frozen=True)
class CreateUserInput:
    """Данные для создания пользователя."""

    username: str
    password: str
    role: UserRole = UserRole.USER
    is_active: bool = True


@dataclass(frozen=True)
class UpdateUserInput:
    """Данные для частичного редактирования пользователя. None-поля не меняются.

    acting_user_id — id администратора, выполняющего операцию (для запрета
    самопонижения/самодеактивации).
    """

    user_id: int
    acting_user_id: int
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = None


@dataclass(frozen=True)
class DeleteUserInput:
    """Данные для удаления пользователя.

    acting_user_id — id администратора, выполняющего операцию (для запрета
    самоудаления).
    """

    user_id: int
    acting_user_id: int
