"""use_cases.py — сценарии раздела «Пользователи» (list / create / update / delete).

За что отвечает: оркеструет работу с пользователями через порт репозитория и
порт хешера паролей. Здесь же живут бизнес-инварианты RBAC:
    • уникальность логина (регистронезависимо) при создании;
    • «последний админ» — систему нельзя оставить без активного администратора;
    • запрет менять/удалять собственную учётку деструктивно (self-guard).

Сценарии чистые: зависят только от доменных портов (repository, hasher), не знают
про HTTP/SQLAlchemy. Слой представления ловит доменные исключения и переводит их
в HTTP-ответы (см. router.py и core/api/errors.py).
"""

from __future__ import annotations

from core.application.use_case import UseCase
from features.users.application.dto import (
    CreateUserInput,
    DeleteUserInput,
    UpdateUserInput,
)
from features.users.application.ports import PasswordHasher
from features.users.domain.entities import User, UserRole
from features.users.domain.exceptions import (
    CannotModifySelfError,
    LastAdminError,
    UserAlreadyExistsError,
)
from features.users.domain.repositories import UserRepository


class ListUsersUseCase(UseCase[str | None, list[User]]):
    """Возвращает пользователей (опционально отфильтрованных по подстроке логина)."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def execute(self, data: str | None = None) -> list[User]:
        """data — необязательная строка поиска по логину (регистронезависимо)."""
        return self._repository.list(search=data)


class CreateUserUseCase(UseCase[CreateUserInput, User]):
    """Создаёт нового пользователя (проверяет уникальность логина, хеширует пароль)."""

    def __init__(self, repository: UserRepository, hasher: PasswordHasher) -> None:
        self._repository = repository
        self._hasher = hasher

    def execute(self, data: CreateUserInput) -> User:
        """Уникальность логина (регистронезависимо) → иначе UserAlreadyExistsError (422)."""
        if self._repository.get_by_username(data.username) is not None:
            raise UserAlreadyExistsError("Пользователь с таким именем уже существует")
        user = User(
            username=data.username,
            password_hash=self._hasher.hash(data.password),
            role=data.role,
            is_active=data.is_active,
        )
        return self._repository.add(user)


class UpdateUserUseCase(UseCase[UpdateUserInput, User]):
    """Частично редактирует пользователя (role / is_active / password).

    Соблюдает инварианты: нельзя понизить/деактивировать себя (CANNOT_MODIFY_SELF)
    и нельзя понизить/деактивировать последнего активного админа (LAST_ADMIN).
    """

    def __init__(self, repository: UserRepository, hasher: PasswordHasher) -> None:
        self._repository = repository
        self._hasher = hasher

    def execute(self, data: UpdateUserInput) -> User:
        user = self._repository.get(data.user_id)  # UserNotFoundError → 404

        # Что именно пытаемся сделать с админом: понизить или деактивировать.
        # Понижение = смена роли администратора на ЛЮБУЮ не-admin роль (user или
        # guest). Раньше учитывался только переход в USER — из-за чего демоут
        # admin→guest не срабатывал бы на инвариантах LAST_ADMIN/CANNOT_MODIFY_SELF.
        demoting = (
            data.role is not None
            and data.role is not UserRole.ADMIN
            and user.role is UserRole.ADMIN
        )
        deactivating = data.is_active is False and user.is_active is True
        is_self = user.id == data.acting_user_id

        # Самопонижение/самодеактивация запрещены (иначе админ может закрыть себе доступ).
        if is_self and (demoting or deactivating):
            raise CannotModifySelfError()

        # Инвариант «последний админ»: понижение/деактивация последнего активного
        # администратора недопустимы (иначе раздел «Пользователи» будет заблокирован).
        if (demoting or deactivating) and user.is_admin and self._repository.count_admins() <= 1:
            raise LastAdminError()

        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active
        if data.password is not None:
            user.set_password_hash(self._hasher.hash(data.password))

        return self._repository.save(user)  # UserAlreadyExistsError не возникает (логин не меняем)


class DeleteUserUseCase(UseCase[DeleteUserInput, None]):
    """Удаляет пользователя, соблюдая self-guard и инвариант «последний админ»."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def execute(self, data: DeleteUserInput) -> None:
        user = self._repository.get(data.user_id)  # UserNotFoundError → 404

        if user.id == data.acting_user_id:
            raise CannotModifySelfError()

        if user.is_admin and self._repository.count_admins() <= 1:
            raise LastAdminError()

        self._repository.delete(data.user_id)
