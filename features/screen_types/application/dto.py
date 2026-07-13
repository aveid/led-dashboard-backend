"""dto.py — DTO прикладного слоя справочника типов экрана.

Простые неизменяемые контейнеры данных для входа/выхода сценариев, отвязанные от
HTTP и БД.
"""

from __future__ import annotations

from dataclasses import dataclass

from features.screen_types.domain.entities import ScreenType


@dataclass(frozen=True)
class CreateScreenTypeInput:
    """Данные для создания типа экрана. code необязателен."""

    name: str
    code: str | None = None


@dataclass(frozen=True)
class UpdateScreenTypeInput:
    """Данные для частичного редактирования типа. None-поля не меняются."""

    screen_type_id: int
    name: str | None = None
    code: str | None = None


@dataclass(frozen=True)
class ListScreenTypesInput:
    """Параметры выборки списка типов: поиск и пагинация страницами.

    page — номер страницы с 1; per_page — размер страницы. Смещение сценарий
    вычисляет сам: offset = (page - 1) * per_page.
    """

    search: str | None = None
    page: int = 1
    per_page: int = 20


@dataclass(frozen=True)
class ScreenTypeListResult:
    """Результат выборки списка: типы страницы + сведения для meta пагинации."""

    items: list[ScreenType]
    total: int
    page: int
    per_page: int
