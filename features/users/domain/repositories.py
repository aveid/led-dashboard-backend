"""repositories.py — порт (интерфейс) репозитория пользователей.

Домен объявляет, ЧТО должно уметь хранилище пользователей, не зная КАК. Реализация
(SQLAlchemy) живёт в инфраструктуре и подставляется снаружи (инверсия зависимостей).

Методы возвращают доменные сущности User (а не ORM-модели) — граница слоёв. Хеш
пароля хранится, но наружу (в схемах ответа) никогда не отдаётся.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .entities import User


class UserRepository(ABC):
    """Контракт хранилища пользователей."""

    @abstractmethod
    def list(self, search: str | None = None) -> list[User]:
        """Вернуть пользователей, отсортированных по логину.

        search — необязательный регистронезависимый фильтр по подстроке логина.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, user_id: int) -> User:
        """Вернуть пользователя по id или бросить UserNotFoundError (→ 404)."""
        raise NotImplementedError

    @abstractmethod
    def get_by_username(self, username: str) -> User | None:
        """Вернуть пользователя по логину (регистронезависимо) или None.

        None (а не исключение) — потому что вызывается и для проверки уникальности
        при создании, и в аутентификации, где «нет такого» — штатная ветка.
        """
        raise NotImplementedError

    @abstractmethod
    def add(self, user: User) -> User:
        """Сохранить нового пользователя и вернуть его с присвоенным id/created_at.

        При конфликте уникальности логина бросает UserAlreadyExistsError (→ 422).
        """
        raise NotImplementedError

    @abstractmethod
    def save(self, user: User) -> User:
        """Сохранить изменения существующего пользователя.

        При конфликте уникальности логина бросает UserAlreadyExistsError (→ 422).
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, user_id: int) -> None:
        """Удалить пользователя по id или бросить UserNotFoundError (→ 404)."""
        raise NotImplementedError

    @abstractmethod
    def count_admins(self) -> int:
        """Вернуть число активных администраторов (role='admin' AND is_active=true).

        Нужен для инварианта «последний админ»: систему нельзя оставить без
        администратора (иначе раздел «Пользователи» окажется заблокирован).
        """
        raise NotImplementedError
