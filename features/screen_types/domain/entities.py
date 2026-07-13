"""entities.py — доменная сущность «Тип экрана» (ScreenType).

За что отвечает модуль:
    Описывает тип экрана как самостоятельную управляемую сущность справочника
    (вертикальный, горизонтальный, квадратный, остановка и любые заведённые
    пользователем). Раньше это было бы жёстко зашитым перечислением; теперь —
    отдельная сущность с идентификатором и жизненным циклом (создать/переименовать/
    удалить) независимо от конкретного экрана.

Почему сущность, а не value object:
    У типа есть собственная идентичность (id) и он живёт независимо от экранов,
    которые на него ссылаются (FK screens.screen_type_id).

Здесь только чистый Python: ни FastAPI, ни SQLAlchemy, ни Pydantic (правило
BACKEND_CONTEXT.md — доменный слой остаётся «чистым»).

Примечание об идентификаторе: у типов целочисленный автоинкрементный id
(небольшой стабильный справочник), поэтому ScreenType НЕ наследует базовый Entity,
чей id типизирован как UUID. Равенство/хеш определяем здесь по id — как у City.
"""

from __future__ import annotations

from datetime import datetime

from core.domain.exceptions import ValidationError


class ScreenType:
    """Тип экрана-справочник: то, к какому виду относится LED-экран.

    Поля:
        id         — идентификатор (int). None у ещё не сохранённого типа.
        name       — отображаемое имя (уникальное, непустое, напр. «Вертикальный»).
        code       — опциональный машинный код (напр. `vertical`) для системных
                     типов. У типов, заведённых пользователем вручную, может быть None.
        created_at — момент создания (проставляет БД). None до сохранения.
        updated_at — момент последнего изменения (проставляет БД). None до сохранения.
    """

    def __init__(
        self,
        name: str,
        code: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        id: int | None = None,
    ) -> None:
        """Создаёт тип экрана и проверяет, что имя непустое.

        Имя нормализуем (обрезаем пробелы по краям) — так «Вертикальный » и
        «Вертикальный» не станут разными типами. Код тоже нормализуем: пустая
        строка/только пробелы трактуются как «код не задан» (None).
        """
        self.id = id
        self.name = self._normalize_name(name)
        self.code = self._normalize_code(code)
        self.created_at = created_at
        self.updated_at = updated_at

    def rename(self, name: str) -> None:
        """Переименовывает тип (с той же проверкой непустого имени)."""
        self.name = self._normalize_name(name)

    def set_code(self, code: str | None) -> None:
        """Задаёт машинный код типа (или снимает его, если передан пустой/None)."""
        self.code = self._normalize_code(code)

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Обрезает пробелы и требует непустое имя (доменное правило)."""
        normalized = name.strip()
        if not normalized:
            raise ValidationError("У типа экрана должно быть непустое название.")
        return normalized

    @staticmethod
    def _normalize_code(code: str | None) -> str | None:
        """Пустой/пробельный код трактуем как отсутствующий (None)."""
        if code is None:
            return None
        normalized = code.strip()
        return normalized or None

    def __eq__(self, other: object) -> bool:
        """Типы равны, если это ScreenType с тем же непустым id."""
        if not isinstance(other, ScreenType):
            return NotImplemented
        if self.id is None or other.id is None:
            return self is other
        return self.id == other.id

    def __hash__(self) -> int:
        """Хеш по id — чтобы тип можно было класть в set/dict."""
        return hash(self.id)
