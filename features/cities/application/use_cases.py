"""use_cases.py — сценарии модуля городов (list / create / update).

За что отвечает: оркеструет работу с городами через порт репозитория. Справочник
простой, поэтому сценарии собраны в одном файле. Операции get/delete тривиальны
и вызываются в роутере напрямую через репозиторий.
"""

from __future__ import annotations

from core.application.use_case import UseCase
from features.cities.application.dto import CreateCityInput, UpdateCityInput
from features.cities.domain.entities import City
from features.cities.domain.repositories import CityRepository, CityWithScreens


class ListCitiesUseCase(UseCase[bool, list[CityWithScreens]]):
    """Возвращает города вместе с числом привязанных экранов."""

    def __init__(self, repository: CityRepository) -> None:
        self._repository = repository

    def execute(self, data: bool = False) -> list[CityWithScreens]:
        """data — флаг only_active (True: только активные города)."""
        return self._repository.list_with_screen_counts(only_active=data)


class CreateCityUseCase(UseCase[CreateCityInput, City]):
    """Создаёт новый город."""

    def __init__(self, repository: CityRepository) -> None:
        self._repository = repository

    def execute(self, data: CreateCityInput) -> City:
        """Собирает доменный город (с валидацией названия) и сохраняет его."""
        city = City(name=data.name)
        return self._repository.add(city)


class UpdateCityUseCase(UseCase[UpdateCityInput, City]):
    """Редактирует существующий город (частичное обновление)."""

    def __init__(self, repository: CityRepository) -> None:
        self._repository = repository

    def execute(self, data: UpdateCityInput) -> City:
        """Загружает город, применяет присланные поля и сохраняет."""
        city = self._repository.get_by_id(data.city_id)
        if data.name is not None:
            city.rename(data.name)  # доменное правило: название непустое
        if data.is_active is not None:
            city.is_active = data.is_active
        return self._repository.update(city)
