"""repositories.py — реализация UserRepository на SQLAlchemy.

Работа с таблицей users. Наружу отдаёт доменные сущности User (не ORM). Конфликт
уникальности логина переводится в UserAlreadyExistsError (→ 422). Логин ищется
регистронезависимо (func.lower), как и уникальный барьер в БД.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from features.users.domain.entities import User, UserRole
from features.users.domain.exceptions import UserAlreadyExistsError, UserNotFoundError
from features.users.domain.repositories import UserRepository

from .mappers import user_to_domain
from .models import UserModel

_DUPLICATE_USERNAME_MESSAGE = "Пользователь с таким именем уже существует"


class SqlAlchemyUserRepository(UserRepository):
    """Хранилище пользователей поверх SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Получает сессию БД (внедряется на время HTTP-запроса)."""
        self._session = session

    def list(self, search: str | None = None) -> list[User]:
        """Возвращает пользователей, отсортированных по логину (опц. поиск по подстроке)."""
        stmt = select(UserModel).order_by(UserModel.username)
        if search:
            stmt = stmt.where(UserModel.username.ilike(f"%{search}%"))
        models = self._session.scalars(stmt).all()
        return [user_to_domain(m) for m in models]

    def get(self, user_id: int) -> User:
        """Возвращает пользователя по id или бросает UserNotFoundError (→ 404)."""
        model = self._session.get(UserModel, user_id)
        if model is None:
            raise UserNotFoundError(f"Пользователь с id={user_id} не найден.")
        return user_to_domain(model)

    def get_by_username(self, username: str) -> User | None:
        """Возвращает пользователя по логину (регистронезависимо) или None."""
        stmt = select(UserModel).where(func.lower(UserModel.username) == username.strip().lower())
        model = self._session.scalar(stmt)
        return user_to_domain(model) if model is not None else None

    def add(self, user: User) -> User:
        """Сохраняет нового пользователя; дубликат логина → UserAlreadyExistsError (422)."""
        model = UserModel(
            username=user.username,
            password_hash=user.password_hash,
            role=user.role.value,
            is_active=user.is_active,
        )
        self._session.add(model)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise UserAlreadyExistsError(_DUPLICATE_USERNAME_MESSAGE) from exc
        self._session.refresh(model)
        return user_to_domain(model)

    def save(self, user: User) -> User:
        """Сохраняет изменения пользователя; дубликат логина → UserAlreadyExistsError (422)."""
        model = self._session.get(UserModel, user.id)
        if model is None:
            raise UserNotFoundError(f"Пользователь с id={user.id} не найден.")
        model.username = user.username
        model.password_hash = user.password_hash
        model.role = user.role.value
        model.is_active = user.is_active
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise UserAlreadyExistsError(_DUPLICATE_USERNAME_MESSAGE) from exc
        self._session.refresh(model)
        return user_to_domain(model)

    def delete(self, user_id: int) -> None:
        """Удаляет пользователя по id или бросает UserNotFoundError (→ 404)."""
        model = self._session.get(UserModel, user_id)
        if model is None:
            raise UserNotFoundError(f"Пользователь с id={user_id} не найден.")
        self._session.delete(model)
        self._session.commit()

    def count_admins(self) -> int:
        """Число активных администраторов (для инварианта «последний админ»)."""
        stmt = (
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.role == UserRole.ADMIN.value, UserModel.is_active.is_(True))
        )
        return int(self._session.scalar(stmt) or 0)
