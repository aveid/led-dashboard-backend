"""use_cases.py — сценарии справочника типов экрана (list / create / update).

Оркеструет работу с типами через порт репозитория. Справочник простой, поэтому
сценарии собраны в одном файле. Операции get/delete тривиальны и вызываются в
роутере напрямую через репозиторий (как в модуле городов).
"""

from __future__ import annotations

from core.application.use_case import UseCase
from features.screen_types.application.dto import (
    CreateScreenTypeInput,
    ListScreenTypesInput,
    ScreenTypeListResult,
    UpdateScreenTypeInput,
)
from features.screen_types.domain.entities import ScreenType
from features.screen_types.domain.repositories import ScreenTypeRepository


class ListScreenTypesUseCase(UseCase[ListScreenTypesInput, ScreenTypeListResult]):
    """Возвращает страницу типов с общим числом подходящих записей (для пагинации)."""

    def __init__(self, repository: ScreenTypeRepository) -> None:
        self._repository = repository

    def execute(self, data: ListScreenTypesInput) -> ScreenTypeListResult:
        """Считает offset из номера страницы и делегирует выборку репозиторию."""
        offset = (data.page - 1) * data.per_page
        items, total = self._repository.list_paginated(
            search=data.search, limit=data.per_page, offset=offset
        )
        return ScreenTypeListResult(
            items=items, total=total, page=data.page, per_page=data.per_page
        )


class CreateScreenTypeUseCase(UseCase[CreateScreenTypeInput, ScreenType]):
    """Создаёт новый тип экрана."""

    def __init__(self, repository: ScreenTypeRepository) -> None:
        self._repository = repository

    def execute(self, data: CreateScreenTypeInput) -> ScreenType:
        """Собирает доменный тип (с валидацией имени) и сохраняет его."""
        screen_type = ScreenType(name=data.name, code=data.code)
        return self._repository.add(screen_type)


class UpdateScreenTypeUseCase(UseCase[UpdateScreenTypeInput, ScreenType]):
    """Редактирует существующий тип экрана (частичное обновление)."""

    def __init__(self, repository: ScreenTypeRepository) -> None:
        self._repository = repository

    def execute(self, data: UpdateScreenTypeInput) -> ScreenType:
        """Загружает тип, применяет присланные поля и сохраняет."""
        screen_type = self._repository.get_by_id(data.screen_type_id)
        if data.name is not None:
            screen_type.rename(data.name)  # доменное правило: имя непустое
        if data.code is not None:
            screen_type.set_code(data.code)
        return self._repository.update(screen_type)
