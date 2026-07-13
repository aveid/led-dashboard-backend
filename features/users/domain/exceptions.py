"""exceptions.py — доменные исключения раздела «Пользователи».

Разделены по смыслу, чтобы слой представления отдал правильный HTTP-статус и,
где нужно, машиночитаемое тело (см. backend-instruction §1.2):

    UserAlreadyExistsError — дубль логина → 422 (наследует UnprocessableEntityError,
        поэтому переводится глобальным обработчиком; тело-строка через `detail`).
    UserNotFoundError      — нет пользователя с таким id → 404 с телом
        {"detail": {"code": "USER_NOT_FOUND"}} (собирается в роутере, поэтому это
        отдельный тип, НЕ core.NotFoundError, чей глобальный обработчик даёт строку).
    LastAdminError         — попытка удалить/понизить/деактивировать последнего
        активного администратора → 409 {"detail": {"code": "LAST_ADMIN", ...}}.
    CannotModifySelfError  — попытка удалить/понизить/деактивировать самого себя →
        409 {"detail": {"code": "CANNOT_MODIFY_SELF"}}.

LastAdminError и CannotModifySelfError — бизнес-правила: тело ответа специфично и
собирается в роутере (как ScreenTypeInUseError / ATTACHMENT_LIMIT_EXCEEDED), поэтому
они не регистрируются в глобальном обработчике.
"""

from __future__ import annotations

from core.domain.exceptions import UnprocessableEntityError


class UserAlreadyExistsError(UnprocessableEntityError):
    """Логин уже занят другим пользователем (→ 422 через глобальный обработчик)."""


class UserNotFoundError(Exception):
    """Пользователь с таким id не найден (→ 404 с машиночитаемым телом в роутере)."""


class LastAdminError(Exception):
    """Нельзя удалить/понизить/деактивировать последнего активного администратора (→ 409)."""


class CannotModifySelfError(Exception):
    """Нельзя удалить/понизить/деактивировать собственную учётную запись (→ 409)."""
