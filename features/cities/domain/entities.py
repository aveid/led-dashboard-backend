"""entities.py — доменная сущность «Город» (City).

За что отвечает модуль:
    Описывает город как самостоятельную сущность справочника (областной центр
    Кыргызстана). Раньше город был просто строкой в адресе экрана; теперь это
    отдельная сущность с идентификатором, признаком активности и связью с экранами.

Почему сущность, а не value object:
    У города есть собственная идентичность (id) и жизненный цикл (его можно
    переименовать, деактивировать, удалить) независимо от конкретного экрана.

Здесь только чистый Python: ни FastAPI, ни SQLAlchemy, ни Pydantic (правило
CONTEXT.md — доменный слой остаётся «чистым»).

Примечание об идентификаторе: у городов целочисленный автоинкрементный id
(маленький стабильный справочник), поэтому City НЕ наследует базовый Entity,
чей id типизирован как UUID. Равенство/хеш определяем здесь по id.
"""

from __future__ import annotations

from core.domain.exceptions import ValidationError


class City:
    """Город-справочник: областной центр, к которому привязаны экраны.

    Поля:
        id         — идентификатор (int). None у ещё не сохранённого города.
        name       — название города (уникальное, непустое).
        is_active  — активен ли город (неактивные можно прятать в выпадающих списках).
    """

    def __init__(
        self,
        name: str,
        is_active: bool = True,
        id: int | None = None,
    ) -> None:
        """Создаёт город и проверяет, что название непустое.

        Название нормализуем (обрезаем пробелы по краям) — так «Ош » и «Ош»
        не станут разными городами.
        """
        normalized = name.strip()
        if not normalized:
            raise ValidationError("У города должно быть непустое название.")
        self.id = id
        self.name = normalized
        self.is_active = is_active

    def rename(self, name: str) -> None:
        """Переименовывает город (с той же проверкой непустого названия)."""
        normalized = name.strip()
        if not normalized:
            raise ValidationError("У города должно быть непустое название.")
        self.name = normalized

    def __eq__(self, other: object) -> bool:
        """Города равны, если это City с тем же непустым id."""
        if not isinstance(other, City):
            return NotImplemented
        if self.id is None or other.id is None:
            return self is other
        return self.id == other.id

    def __hash__(self) -> int:
        """Хеш по id — чтобы город можно было класть в set/dict."""
        return hash(self.id)
