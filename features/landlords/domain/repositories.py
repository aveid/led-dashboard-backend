"""repositories.py — порт (интерфейс) репозитория арендодателей.

Домен объявляет, ЧТО должно уметь хранилище арендодателей, не зная КАК это
сделано. Реализация (SQLAlchemy) живёт в инфраструктуре и подставляется снаружи
(инверсия зависимостей). Так домен не зависит от БД.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from .entities import Landlord


class LandlordRepository(ABC):
    """Контракт хранилища арендодателей."""

    @abstractmethod
    def get_by_id(self, landlord_id: UUID) -> Landlord:
        """Вернуть арендодателя по id или бросить NotFoundError."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, landlord_id: UUID) -> bool:
        """Проверить наличие арендодателя по id (без загрузки сущности).

        Нужно сценариям, которым важен лишь факт существования (напр. список
        экранов арендодателя): по образцу `ScreenTypeRepository.exists`.
        """
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[Landlord]:
        """Вернуть всех арендодателей (для справочника/выпадающих списков)."""
        raise NotImplementedError

    @abstractmethod
    def add(self, landlord: Landlord) -> Landlord:
        """Сохранить нового арендодателя и вернуть его (с присвоенным id)."""
        raise NotImplementedError

    @abstractmethod
    def update(self, landlord: Landlord) -> Landlord:
        """Сохранить изменения существующего арендодателя."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, landlord_id: UUID) -> None:
        """Удалить арендодателя по id."""
        raise NotImplementedError
