"""repositories.py — порт (интерфейс) репозитория городов.

Домен объявляет, ЧТО должно уметь хранилище городов, не зная КАК это сделано.
Реализация (SQLAlchemy) живёт в инфраструктуре и подставляется снаружи (инверсия
зависимостей). Так домен не зависит от БД.

Методы возвращают доменные сущности City (а не ORM-модели) — граница слоёв.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .entities import City


@dataclass(frozen=True)
class CityWithScreens:
    """Город вместе с количеством привязанных к нему экранов.

    Отдельный результат для списка городов: счётчик экранов — это агрегат
    из запроса (join+count), а не собственное состояние города, поэтому он
    вынесен рядом с сущностью, а не внутрь неё.
    """

    city: City
    screens_count: int


class CityRepository(ABC):
    """Контракт хранилища городов."""

    @abstractmethod
    def list_with_screen_counts(self, only_active: bool = False) -> list[CityWithScreens]:
        """Вернуть города с числом привязанных экранов, отсортированные по названию.

        only_active=True — только активные города.
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, city_id: int) -> City:
        """Вернуть город по id или бросить NotFoundError."""
        raise NotImplementedError

    @abstractmethod
    def count_screens(self, city_id: int) -> int:
        """Вернуть число экранов, привязанных к городу (для запрета удаления)."""
        raise NotImplementedError

    @abstractmethod
    def add(self, city: City) -> City:
        """Сохранить новый город и вернуть его с присвоенным id.

        При конфликте уникальности названия бросает BusinessRuleViolation (→ 409).
        """
        raise NotImplementedError

    @abstractmethod
    def update(self, city: City) -> City:
        """Сохранить изменения города.

        При конфликте уникальности названия бросает BusinessRuleViolation (→ 409).
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, city_id: int) -> None:
        """Удалить город по id.

        Если к городу привязаны экраны — бросает BusinessRuleViolation (→ 409);
        на уровне БД тем же барьером стоит внешний ключ ON DELETE RESTRICT.
        """
        raise NotImplementedError
