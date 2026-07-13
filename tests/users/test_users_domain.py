"""Тесты доменных правил и сценариев раздела «Пользователи» (RBAC, NFR-8).

Без базы данных: используется фейковый репозиторий в памяти и фейковый хешер.
Проверяются: уникальность логина (регистронезависимо), частичное обновление,
инвариант «последний админ», запрет самопонижения/самоудаления, а также то, что
пароль хранится только хешем.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.domain.exceptions import ValidationError
from features.users.application.dto import (
    CreateUserInput,
    DeleteUserInput,
    UpdateUserInput,
)
from features.users.application.use_cases import (
    CreateUserUseCase,
    DeleteUserUseCase,
    ListUsersUseCase,
    UpdateUserUseCase,
)
from features.users.domain.entities import User, UserRole
from features.users.domain.exceptions import (
    CannotModifySelfError,
    LastAdminError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from features.users.domain.repositories import UserRepository


class FakeUserRepository(UserRepository):
    """Репозиторий пользователей в памяти — подмена БД для тестов сценариев."""

    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._next_id = 1

    def list(self, search: str | None = None) -> list[User]:
        items = sorted(self._users.values(), key=lambda u: u.username)
        if search:
            items = [u for u in items if search.lower() in u.username.lower()]
        return items

    def get(self, user_id: int) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise UserNotFoundError(f"Пользователь с id={user_id} не найден.")
        return user

    def get_by_username(self, username: str) -> User | None:
        for user in self._users.values():
            if user.username.lower() == username.strip().lower():
                return user
        return None

    def add(self, user: User) -> User:
        if self.get_by_username(user.username) is not None:
            raise UserAlreadyExistsError("Пользователь с таким именем уже существует")
        user.id = self._next_id
        self._next_id += 1
        user.created_at = datetime(2026, 7, 10)
        self._users[user.id] = user
        return user

    def save(self, user: User) -> User:
        if user.id not in self._users:
            raise UserNotFoundError(f"Пользователь с id={user.id} не найден.")
        self._users[user.id] = user
        return user

    def delete(self, user_id: int) -> None:
        if user_id not in self._users:
            raise UserNotFoundError(f"Пользователь с id={user_id} не найден.")
        del self._users[user_id]

    def count_admins(self) -> int:
        return sum(1 for u in self._users.values() if u.role is UserRole.ADMIN and u.is_active)

    # Хелпер для тестов: положить готового пользователя.
    def seed(self, user: User) -> User:
        user.id = self._next_id
        self._next_id += 1
        user.created_at = datetime(2026, 7, 10)
        self._users[user.id] = user
        return user


class FakeHasher:
    """Фейковый хешер: помечает пароль префиксом, чтобы отличать хеш от plaintext."""

    def hash(self, plain_password: str) -> str:
        return f"hashed::{plain_password}"


# --- Доменная сущность ---


def test_user_requires_non_empty_username() -> None:
    """Пользователя нельзя создать с пустым логином (доменное правило)."""
    with pytest.raises(ValidationError):
        User(username="   ", password_hash="x")


def test_user_username_is_trimmed() -> None:
    """Логин нормализуется — пробелы по краям убираются."""
    assert User(username="  admin  ", password_hash="x").username == "admin"


def test_user_role_defaults_to_user() -> None:
    """По умолчанию роль — наблюдатель (USER), не админ."""
    assert User(username="u", password_hash="x").role is UserRole.USER


# --- CreateUser ---


def test_create_user_hashes_password_and_defaults_role() -> None:
    """Пароль сохраняется только хешем; роль по умолчанию — USER."""
    repo = FakeUserRepository()
    user = CreateUserUseCase(repo, FakeHasher()).execute(
        CreateUserInput(username="viewer", password="secretpass1")
    )
    assert user.role is UserRole.USER
    assert user.password_hash == "hashed::secretpass1"
    assert "secretpass1" != user.password_hash  # plaintext никогда не хранится как есть


def test_create_user_duplicate_username_case_insensitive() -> None:
    """Дубликат логина без учёта регистра → UserAlreadyExistsError (→ 422)."""
    repo = FakeUserRepository()
    hasher = FakeHasher()
    CreateUserUseCase(repo, hasher).execute(CreateUserInput(username="Admin", password="password12"))
    with pytest.raises(UserAlreadyExistsError):
        CreateUserUseCase(repo, hasher).execute(
            CreateUserInput(username="ADMIN", password="password34")
        )


# --- UpdateUser: частичность ---


def test_update_user_partial_only_changes_sent_fields() -> None:
    """PATCH меняет только присланные поля; отсутствующий пароль не трогается."""
    repo = FakeUserRepository()
    admin = repo.seed(User(username="admin", password_hash="orig", role=UserRole.ADMIN))
    target = repo.seed(User(username="bob", password_hash="orig", role=UserRole.USER))

    updated = UpdateUserUseCase(repo, FakeHasher()).execute(
        UpdateUserInput(user_id=target.id, acting_user_id=admin.id, role=UserRole.ADMIN)
    )
    assert updated.role is UserRole.ADMIN
    assert updated.password_hash == "orig"  # пароль не прислан → не изменился


def test_update_user_password_is_rehashed_when_sent() -> None:
    """Присланный пароль перехешируется."""
    repo = FakeUserRepository()
    admin = repo.seed(User(username="admin", password_hash="orig", role=UserRole.ADMIN))
    target = repo.seed(User(username="bob", password_hash="orig", role=UserRole.USER))

    updated = UpdateUserUseCase(repo, FakeHasher()).execute(
        UpdateUserInput(user_id=target.id, acting_user_id=admin.id, password="newpass123")
    )
    assert updated.password_hash == "hashed::newpass123"


def test_update_nonexistent_user_raises_not_found() -> None:
    """PATCH несуществующего id → UserNotFoundError (→ 404)."""
    repo = FakeUserRepository()
    admin = repo.seed(User(username="admin", password_hash="x", role=UserRole.ADMIN))
    with pytest.raises(UserNotFoundError):
        UpdateUserUseCase(repo, FakeHasher()).execute(
            UpdateUserInput(user_id=999, acting_user_id=admin.id, is_active=False)
        )


# --- Инвариант «последний админ» ---


def test_demote_last_admin_is_blocked() -> None:
    """Понижение последнего активного админа (другим админом) → LastAdminError (→ 409).

    Смоделирован крайний случай: в системе ровно один активный админ, а операцию
    выполняет кто-то иной (acting_user_id ≠ target) — гейт всё равно защищает.
    """
    repo = FakeUserRepository()
    sole_admin = repo.seed(User(username="admin", password_hash="x", role=UserRole.ADMIN))
    with pytest.raises(LastAdminError):
        UpdateUserUseCase(repo, FakeHasher()).execute(
            UpdateUserInput(user_id=sole_admin.id, acting_user_id=999, role=UserRole.USER)
        )


def test_deactivate_last_admin_is_blocked() -> None:
    """Деактивация последнего активного админа → LastAdminError (→ 409)."""
    repo = FakeUserRepository()
    sole_admin = repo.seed(User(username="admin", password_hash="x", role=UserRole.ADMIN))
    with pytest.raises(LastAdminError):
        UpdateUserUseCase(repo, FakeHasher()).execute(
            UpdateUserInput(user_id=sole_admin.id, acting_user_id=999, is_active=False)
        )


def test_delete_last_admin_is_blocked() -> None:
    """Удаление последнего активного админа → LastAdminError (→ 409)."""
    repo = FakeUserRepository()
    sole_admin = repo.seed(User(username="admin", password_hash="x", role=UserRole.ADMIN))
    with pytest.raises(LastAdminError):
        DeleteUserUseCase(repo).execute(DeleteUserInput(user_id=sole_admin.id, acting_user_id=999))


def test_demote_admin_allowed_when_another_admin_exists() -> None:
    """Понизить одного админа можно, если есть ещё хотя бы один активный админ."""
    repo = FakeUserRepository()
    acting = repo.seed(User(username="admin1", password_hash="x", role=UserRole.ADMIN))
    other = repo.seed(User(username="admin2", password_hash="x", role=UserRole.ADMIN))
    updated = UpdateUserUseCase(repo, FakeHasher()).execute(
        UpdateUserInput(user_id=other.id, acting_user_id=acting.id, role=UserRole.USER)
    )
    assert updated.role is UserRole.USER


def test_demote_last_admin_to_guest_is_blocked() -> None:
    """Перевод последнего активного админа в GUEST — тоже понижение → LastAdminError (409).

    Демоут admin→guest должен срабатывать на инварианте «последний админ» так же,
    как admin→user (guest — не admin по доступу). Регресс на прежнюю логику, где
    понижением считался только переход в USER.
    """
    repo = FakeUserRepository()
    sole_admin = repo.seed(User(username="admin", password_hash="x", role=UserRole.ADMIN))
    with pytest.raises(LastAdminError):
        UpdateUserUseCase(repo, FakeHasher()).execute(
            UpdateUserInput(user_id=sole_admin.id, acting_user_id=999, role=UserRole.GUEST)
        )


# --- Запрет самомодификации ---


def test_self_demote_is_blocked() -> None:
    """Админ не может понизить сам себя → CannotModifySelfError (→ 409)."""
    repo = FakeUserRepository()
    admin = repo.seed(User(username="admin", password_hash="x", role=UserRole.ADMIN))
    # Заводим второго админа, чтобы сработал именно self-guard, а не last-admin.
    repo.seed(User(username="admin2", password_hash="x", role=UserRole.ADMIN))
    with pytest.raises(CannotModifySelfError):
        UpdateUserUseCase(repo, FakeHasher()).execute(
            UpdateUserInput(user_id=admin.id, acting_user_id=admin.id, role=UserRole.USER)
        )


def test_self_demote_to_guest_is_blocked() -> None:
    """Админ не может понизить сам себя до GUEST → CannotModifySelfError (409).

    Самопонижение admin→guest защищено тем же self-guard, что и admin→user.
    """
    repo = FakeUserRepository()
    admin = repo.seed(User(username="admin", password_hash="x", role=UserRole.ADMIN))
    repo.seed(User(username="admin2", password_hash="x", role=UserRole.ADMIN))
    with pytest.raises(CannotModifySelfError):
        UpdateUserUseCase(repo, FakeHasher()).execute(
            UpdateUserInput(user_id=admin.id, acting_user_id=admin.id, role=UserRole.GUEST)
        )


def test_self_delete_is_blocked() -> None:
    """Админ не может удалить сам себя → CannotModifySelfError (→ 409)."""
    repo = FakeUserRepository()
    admin = repo.seed(User(username="admin", password_hash="x", role=UserRole.ADMIN))
    repo.seed(User(username="admin2", password_hash="x", role=UserRole.ADMIN))
    with pytest.raises(CannotModifySelfError):
        DeleteUserUseCase(repo).execute(DeleteUserInput(user_id=admin.id, acting_user_id=admin.id))


# --- ListUsers ---


def test_list_users_search_by_username_substring() -> None:
    """Поиск по подстроке логина (регистронезависимо)."""
    repo = FakeUserRepository()
    repo.seed(User(username="alice", password_hash="x"))
    repo.seed(User(username="bob", password_hash="x"))
    result = ListUsersUseCase(repo).execute("ALI")
    assert [u.username for u in result] == ["alice"]
