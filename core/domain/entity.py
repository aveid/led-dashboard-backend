"""entity.py — базовый класс доменной сущности (Entity).

Чем сущность отличается от value object:
    Сущность имеет ИДЕНТИЧНОСТЬ (id). Два экрана с одинаковыми полями, но разными
    id — это разные экраны. И наоборот: экран остаётся «тем же самым», даже если
    поменять ему название. Поэтому равенство сущностей сравнивается по id, а не
    по всем полям.

За что отвечает этот класс:
    Даёт общее поведение равенства/хеширования по id для всех сущностей проекта
    (Screen, Landlord, Campaign и т.д.), чтобы не дублировать это в каждой.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(eq=False)  # eq=False: сравнение определяем сами (по id), а не по всем полям
class Entity:
    """Базовая сущность. Хранит идентификатор и задаёт сравнение по нему.

    id может быть None у только что созданной, ещё не сохранённой сущности
    (идентификатор присвоит хранилище при добавлении).
    """

    id: UUID | None = None

    def __eq__(self, other: object) -> bool:
        """Две сущности равны, если это один тип и у них совпадает непустой id."""
        if not isinstance(other, self.__class__):
            return NotImplemented
        if self.id is None or other.id is None:
            # Несохранённые сущности (без id) считаем равными только самим себе.
            return self is other
        return self.id == other.id

    def __hash__(self) -> int:
        """Хеш по id — чтобы сущности можно было класть в set/dict."""
        return hash(self.id)
