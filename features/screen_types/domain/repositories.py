"""repositories.py — порт (интерфейс) репозитория типов экрана.

Домен объявляет, ЧТО должно уметь хранилище типов экрана, не зная КАК это
сделано. Реализация (SQLAlchemy) живёт в инфраструктуре и подставляется снаружи
(инверсия зависимостей) — домен не зависит от БД.

Методы возвращают доменные сущности ScreenType (а не ORM-модели) — граница слоёв.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .entities import ScreenType


class ScreenTypeRepository(ABC):
    """Контракт хранилища типов экрана."""

    @abstractmethod
    def list_paginated(
        self, search: str | None, limit: int, offset: int
    ) -> tuple[list[ScreenType], int]:
        """Вернуть страницу типов и общее число подходящих записей.

        search — необязательный поиск по name (подстрока, регистронезависимо).
        Возвращает кортеж (типы_на_странице, total): total считается по фильтру
        поиска, но без учёта limit/offset — он нужен фронту для пагинации (meta.total).
        Сортировка по name.
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, screen_type_id: int) -> ScreenType:
        """Вернуть тип по id или бросить NotFoundError (→ 404)."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, screen_type_id: int) -> bool:
        """Проверить, существует ли тип с таким id (для валидации screen_type_id)."""
        raise NotImplementedError

    @abstractmethod
    def add(self, screen_type: ScreenType) -> ScreenType:
        """Сохранить новый тип и вернуть его с присвоенным id и метками времени.

        Дубликат name (регистронезависимо) или code → UnprocessableEntityError (→ 422).
        """
        raise NotImplementedError

    @abstractmethod
    def update(self, screen_type: ScreenType) -> ScreenType:
        """Сохранить изменения типа.

        Отсутствующий id → NotFoundError (→ 404). Дубликат name/code →
        UnprocessableEntityError (→ 422).
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, screen_type_id: int) -> None:
        """Удалить тип по id.

        Отсутствующий id → NotFoundError (→ 404). Если на тип ссылается хотя бы
        один экран — ScreenTypeInUseError (→ 409); каскад/обнуление недопустимы,
        т.к. screens.screen_type_id теперь NOT NULL (ON DELETE RESTRICT в БД).
        """
        raise NotImplementedError
