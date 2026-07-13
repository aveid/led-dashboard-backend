"""Тесты доменных правил и сценариев справочника «типы экрана».

Без базы данных: используется фейковый репозиторий в памяти, моделирующий
регистронезависимую уникальность имени, уникальность кода и запрет удаления
типа, на который ссылаются экраны.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.domain.exceptions import (
    NotFoundError,
    UnprocessableEntityError,
    ValidationError,
)
from features.screen_types.application.dto import (
    CreateScreenTypeInput,
    ListScreenTypesInput,
    UpdateScreenTypeInput,
)
from features.screen_types.application.use_cases import (
    CreateScreenTypeUseCase,
    ListScreenTypesUseCase,
    UpdateScreenTypeUseCase,
)
from features.screen_types.domain.entities import ScreenType
from features.screen_types.domain.exceptions import ScreenTypeInUseError
from features.screen_types.domain.repositories import ScreenTypeRepository


class FakeScreenTypeRepository(ScreenTypeRepository):
    """Репозиторий типов экрана в памяти — подмена БД для тестов сценариев."""

    def __init__(self) -> None:
        self._types: dict[int, ScreenType] = {}
        self._screen_counts: dict[int, int] = {}
        self._next_id = 1

    def list_paginated(
        self, search: str | None, limit: int, offset: int
    ) -> tuple[list[ScreenType], int]:
        items = sorted(self._types.values(), key=lambda t: t.name)
        if search:
            items = [t for t in items if search.lower() in t.name.lower()]
        total = len(items)
        return items[offset : offset + limit], total

    def get_by_id(self, screen_type_id: int) -> ScreenType:
        st = self._types.get(screen_type_id)
        if st is None:
            raise NotFoundError(f"Тип экрана с id={screen_type_id} не найден.")
        return st

    def exists(self, screen_type_id: int) -> bool:
        return screen_type_id in self._types

    def add(self, screen_type: ScreenType) -> ScreenType:
        self._guard_unique(screen_type)
        screen_type.id = self._next_id
        self._next_id += 1
        # БД проставляет метки времени; фейк подставляет фиксированные значения.
        screen_type.created_at = datetime(2026, 7, 8)
        screen_type.updated_at = datetime(2026, 7, 8)
        self._types[screen_type.id] = screen_type
        return screen_type

    def update(self, screen_type: ScreenType) -> ScreenType:
        if screen_type.id not in self._types:
            raise NotFoundError(f"Тип экрана с id={screen_type.id} не найден.")
        self._guard_unique(screen_type, exclude_id=screen_type.id)
        self._types[screen_type.id] = screen_type
        return screen_type

    def delete(self, screen_type_id: int) -> None:
        if screen_type_id not in self._types:
            raise NotFoundError(f"Тип экрана с id={screen_type_id} не найден.")
        used_by = self._screen_counts.get(screen_type_id, 0)
        if used_by > 0:
            raise ScreenTypeInUseError(used_by_count=used_by)
        del self._types[screen_type_id]

    def _guard_unique(self, screen_type: ScreenType, exclude_id: int | None = None) -> None:
        for other in self._types.values():
            if exclude_id is not None and other.id == exclude_id:
                continue
            if other.name.lower() == screen_type.name.lower():
                raise UnprocessableEntityError("Тип экрана с таким названием уже существует")
            if screen_type.code is not None and other.code == screen_type.code:
                raise UnprocessableEntityError("Тип экрана с таким кодом уже существует")

    # Хелпер для тестов: сколько экранов «висит» на типе.
    def set_screen_count(self, screen_type_id: int, count: int) -> None:
        self._screen_counts[screen_type_id] = count


# --- Доменная сущность ---


def test_screen_type_requires_non_empty_name() -> None:
    """Тип нельзя создать с пустым названием (доменное правило)."""
    with pytest.raises(ValidationError):
        ScreenType(name="   ")


def test_screen_type_name_is_trimmed() -> None:
    """Название нормализуется — пробелы по краям убираются."""
    assert ScreenType(name="  Вертикальный  ").name == "Вертикальный"


def test_screen_type_blank_code_becomes_none() -> None:
    """Пустой/пробельный код трактуется как отсутствующий (None)."""
    assert ScreenType(name="Тип", code="   ").code is None
    assert ScreenType(name="Тип", code="vertical").code == "vertical"


# --- Сценарии ---


def test_create_screen_type_use_case() -> None:
    """Сценарий создаёт тип, присваивает id и проставляет метки времени."""
    repo = FakeScreenTypeRepository()
    st = CreateScreenTypeUseCase(repo).execute(
        CreateScreenTypeInput(name="Ультраширокий", code="ultrawide")
    )
    assert st.id == 1
    assert st.name == "Ультраширокий"
    assert st.code == "ultrawide"
    assert st.created_at is not None and st.updated_at is not None


def test_create_duplicate_name_case_insensitive_conflicts() -> None:
    """Повтор названия без учёта регистра → 422 (UnprocessableEntityError)."""
    repo = FakeScreenTypeRepository()
    CreateScreenTypeUseCase(repo).execute(CreateScreenTypeInput(name="Вертикальный"))
    with pytest.raises(UnprocessableEntityError):
        CreateScreenTypeUseCase(repo).execute(CreateScreenTypeInput(name="вертикальный"))


def test_create_duplicate_code_conflicts() -> None:
    """Повтор кода → 422 (UnprocessableEntityError)."""
    repo = FakeScreenTypeRepository()
    CreateScreenTypeUseCase(repo).execute(
        CreateScreenTypeInput(name="Вертикальный", code="vertical")
    )
    with pytest.raises(UnprocessableEntityError):
        CreateScreenTypeUseCase(repo).execute(
            CreateScreenTypeInput(name="Другой", code="vertical")
        )


def test_update_screen_type_renames_and_sets_code() -> None:
    """Сценарий обновления меняет название и код."""
    repo = FakeScreenTypeRepository()
    st = CreateScreenTypeUseCase(repo).execute(CreateScreenTypeInput(name="Квадратный"))

    updated = UpdateScreenTypeUseCase(repo).execute(
        UpdateScreenTypeInput(screen_type_id=st.id, name="Квадрат", code="square")
    )

    assert updated.name == "Квадрат"
    assert updated.code == "square"


def test_update_missing_screen_type_raises() -> None:
    """Редактирование несуществующего типа → NotFoundError (→ 404)."""
    repo = FakeScreenTypeRepository()
    with pytest.raises(NotFoundError):
        UpdateScreenTypeUseCase(repo).execute(
            UpdateScreenTypeInput(screen_type_id=999, name="Нет")
        )


def test_delete_screen_type_in_use_raises_conflict() -> None:
    """Удаление типа, на который ссылаются экраны → ScreenTypeInUseError (→ 409)."""
    repo = FakeScreenTypeRepository()
    st = CreateScreenTypeUseCase(repo).execute(CreateScreenTypeInput(name="Вертикальный"))
    repo.set_screen_count(st.id, 12)

    with pytest.raises(ScreenTypeInUseError) as exc_info:
        repo.delete(st.id)
    assert exc_info.value.used_by_count == 12


def test_delete_unused_screen_type_removes_it() -> None:
    """Неиспользуемый тип удаляется без ошибки."""
    repo = FakeScreenTypeRepository()
    st = CreateScreenTypeUseCase(repo).execute(CreateScreenTypeInput(name="Остановка"))

    repo.delete(st.id)

    assert not repo.exists(st.id)


def test_list_screen_types_search_and_pagination() -> None:
    """Список ищет по названию и режет по страницам, отдавая полный total."""
    repo = FakeScreenTypeRepository()
    for name in ["Вертикальный", "Горизонтальный", "Квадратный", "Остановка"]:
        CreateScreenTypeUseCase(repo).execute(CreateScreenTypeInput(name=name))

    # Поиск по подстроке (регистронезависимо): «верт» → «Вертикальный».
    found = ListScreenTypesUseCase(repo).execute(
        ListScreenTypesInput(search="верт", page=1, per_page=20)
    )
    assert found.total == 1
    assert [t.name for t in found.items] == ["Вертикальный"]

    # Пагинация без поиска: 4 всего, страница 2 по 2 → последние два по алфавиту.
    page2 = ListScreenTypesUseCase(repo).execute(
        ListScreenTypesInput(search=None, page=2, per_page=2)
    )
    assert page2.total == 4
    assert page2.page == 2
    assert len(page2.items) == 2
