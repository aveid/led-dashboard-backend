"""router.py — REST-эндпоинты раздела «Пользователи» (prefix /api/users).

Контракт (SSOT, синхронизируется с фронтендом):
    GET    /api/users?search=          → 200 UserRead[]   (bare array, как /api/cities)
    POST   /api/users   body:UserCreate → 201 UserRead | 422
    PATCH  /api/users/{id} body:UserUpdate → 200 UserRead | 404 | 409 | 422
    DELETE /api/users/{id}              → 204 | 404 | 409

Весь роутер — только для администратора: гейт Depends(require_admin) навешен на
уровне роутера (единая точка правды), не-admin → 403 ADMIN_ONLY. Дубликат логина
→ 422 (глобальный обработчик). Несуществующий id → 404 с машиночитаемым телом.
Инвариант «последний админ» и запрет самомодификации → 409 с машиночитаемым телом
(собираются здесь, как ATTACHMENT_LIMIT_EXCEEDED / screen_type_in_use).

Пароль/хеш наружу не отдаются никогда (UserRead их не содержит).
"""


from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.api.auth import require_admin
from features.users.application.dto import (
    CreateUserInput,
    DeleteUserInput,
    UpdateUserInput,
)
from features.users.application.ports import PasswordHasher
from features.users.application.use_cases import (
    CreateUserUseCase,
    DeleteUserUseCase,
    ListUsersUseCase,
    UpdateUserUseCase,
)
from features.users.domain.entities import User
from features.users.domain.exceptions import (
    CannotModifySelfError,
    LastAdminError,
    UserNotFoundError,
)
from features.users.domain.repositories import UserRepository

from .deps import get_password_hasher, get_user_repository
from .mappers import user_to_read
from .schemas import UserCreate, UserRead, UserUpdate

# Весь роутер требует прав администратора (см. §4 инструкции).
router = APIRouter(
    prefix="/api/users",
    tags=["Пользователи"],
    dependencies=[Depends(require_admin)],
)

Repo = Annotated[UserRepository, Depends(get_user_repository)]
Hasher = Annotated[PasswordHasher, Depends(get_password_hasher)]
# Текущий администратор (для запрета самопонижения/самоудаления).
CurrentAdmin = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[UserRead], summary="Список пользователей")
def list_users(
    repo: Repo,
    search: Annotated[str | None, Query(description="Поиск по логину")] = None,
) -> list[UserRead]:
    """Возвращает всех пользователей (опционально отфильтрованных по подстроке логина)."""
    users = ListUsersUseCase(repo).execute(search)
    return [user_to_read(u) for u in users]


@router.post(
    "", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Создать пользователя"
)
def create_user(repo: Repo, hasher: Hasher, payload: UserCreate) -> UserRead:
    """Создаёт нового пользователя. Дубликат логина → 422."""
    data = CreateUserInput(
        username=payload.username,
        password=payload.password,
        role=payload.role,
        is_active=payload.is_active,
    )
    user = CreateUserUseCase(repo, hasher).execute(data)
    return user_to_read(user)


@router.patch("/{user_id}", response_model=UserRead, summary="Редактировать пользователя")
def update_user(
    repo: Repo, hasher: Hasher, current: CurrentAdmin, user_id: int, payload: UserUpdate
) -> UserRead:
    """Частично обновляет пользователя. 404 — нет id, 422 — дубликат, 409 — инвариант."""
    data = UpdateUserInput(
        user_id=user_id,
        acting_user_id=current.id,
        role=payload.role,
        is_active=payload.is_active,
        password=payload.password,
    )
    try:
        user = UpdateUserUseCase(repo, hasher).execute(data)
    except UserNotFoundError as exc:
        raise _not_found() from exc
    except CannotModifySelfError as exc:
        raise _cannot_modify_self() from exc
    except LastAdminError as exc:
        raise _last_admin() from exc
    return user_to_read(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить пользователя")
def delete_user(repo: Repo, current: CurrentAdmin, user_id: int) -> None:
    """Удаляет пользователя. 404 — нет id, 409 — последний админ / самоудаление."""
    try:
        DeleteUserUseCase(repo).execute(
            DeleteUserInput(user_id=user_id, acting_user_id=current.id)
        )
    except UserNotFoundError as exc:
        raise _not_found() from exc
    except CannotModifySelfError as exc:
        raise _cannot_modify_self() from exc
    except LastAdminError as exc:
        raise _last_admin() from exc


# --- Машиночитаемые тела ошибок (SSOT-контракт для фронта, §1.2) ---


def _not_found() -> HTTPException:
    """404 {"detail": {"code": "USER_NOT_FOUND"}}."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "USER_NOT_FOUND"})


def _last_admin() -> HTTPException:
    """409 {"detail": {"code": "LAST_ADMIN", "message": ...}}."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "LAST_ADMIN",
            "message": "Нельзя удалить/понизить последнего администратора",
        },
    )


def _cannot_modify_self() -> HTTPException:
    """409 {"detail": {"code": "CANNOT_MODIFY_SELF"}}."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "CANNOT_MODIFY_SELF"},
    )
