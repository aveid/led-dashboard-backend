"""list_screens.py — сценарий «Список экранов» с фильтрами (FR-1.2, FR-5).

За что отвечает: возвращает экраны из хранилища, опционально сузив выборку
переданными фильтрами (арендодатель, статус, город, кампания, срок договора).
Сам не фильтрует в памяти — делегирует репозиторию, который сделает это
эффективно на уровне БД.
"""

from __future__ import annotations

from features.screens.domain.entities import Screen
from features.screens.domain.repositories import ScreenFilters, ScreenRepository
from core.application.use_case import UseCase


class ListScreensUseCase(UseCase[ScreenFilters | None, list[Screen]]):
    """Отдаёт список экранов, при необходимости отфильтрованный."""

    def __init__(self, repository: ScreenRepository) -> None:
        """Внедряем репозиторий через конструктор (DIP)."""
        self._repository = repository

    def execute(self, data: ScreenFilters | None = None) -> list[Screen]:
        """Возвращает экраны. data=None означает «без фильтров» (все экраны)."""
        return self._repository.list(filters=data)
