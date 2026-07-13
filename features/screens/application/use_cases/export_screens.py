"""export_screens.py — сценарий «Подготовить экраны для выгрузки» (FR-7).

За что отвечает: возвращает список экранов для выгрузки в Excel — либо по явному
списку id (FR-7.4, «выгрузка выделенных на карте»), либо по фильтрам (FR-7.1–7.3:
все активные, по арендодателю, с учётом произвольных фильтров). Само построение
файла .xlsx — забота инфраструктуры/презентации (это деталь формата, не сценарий).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from core.application.use_case import UseCase
from features.screens.domain.entities import Screen
from features.screens.domain.repositories import ScreenFilters, ScreenRepository


@dataclass(frozen=True)
class ExportScreensInput:
    """Входные данные экспорта: либо конкретные id, либо фильтры (не оба сразу).

    Если screen_ids заданы — используются они (FR-7.4), фильтры игнорируются.
    Иначе применяются filters (пустые фильтры = выгрузить все экраны).
    """

    screen_ids: tuple[UUID, ...] = ()
    filters: ScreenFilters | None = None


class ExportScreensUseCase(UseCase[ExportScreensInput, list[Screen]]):
    """Возвращает экраны для выгрузки согласно выбору пользователя."""

    def __init__(self, repository: ScreenRepository) -> None:
        """Внедряем репозиторий через конструктор (DIP)."""
        self._repository = repository

    def execute(self, data: ExportScreensInput) -> list[Screen]:
        """Список по id, если он задан, иначе — по фильтрам (или все)."""
        if data.screen_ids:
            return self._repository.list_by_ids(list(data.screen_ids))
        return self._repository.list(data.filters)
