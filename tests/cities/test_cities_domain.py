"""Тесты доменных правил и сценариев модуля «города».

Без базы данных: используется фейковый репозиторий в памяти, моделирующий
уникальность названий и запрет удаления города с экранами.
"""

from __future__ import annotations

import pytest

from core.domain.exceptions import BusinessRuleViolation, NotFoundError, ValidationError
from features.cities.application.dto import CreateCityInput, UpdateCityInput
from features.cities.application.use_cases import (
    CreateCityUseCase,
    ListCitiesUseCase,
    UpdateCityUseCase,
)
from features.cities.domain.entities import City
from features.cities.domain.repositories import CityRepository, CityWithScreens


class FakeCityRepository(CityRepository):
    """Репозиторий городов в памяти — подмена БД для тестов сценариев."""

    def __init__(self) -> None:
        self._cities: dict[int, City] = {}
        self._screen_counts: dict[int, int] = {}
        self._next_id = 1

    def list_with_screen_counts(self, only_active: bool = False) -> list[CityWithScreens]:
        cities = sorted(self._cities.values(), key=lambda c: c.name)
        if only_active:
            cities = [c for c in cities if c.is_active]
        return [
            CityWithScreens(city=c, screens_count=self._screen_counts.get(c.id, 0))
            for c in cities
        ]

    def get_by_id(self, city_id: int) -> City:
        city = self._cities.get(city_id)
        if city is None:
            raise NotFoundError(f"Город с id={city_id} не найден.")
        return city

    def count_screens(self, city_id: int) -> int:
        return self._screen_counts.get(city_id, 0)

    def add(self, city: City) -> City:
        if any(c.name == city.name for c in self._cities.values()):
            raise BusinessRuleViolation("Город с таким названием уже существует")
        city.id = self._next_id
        self._next_id += 1
        self._cities[city.id] = city
        return city

    def update(self, city: City) -> City:
        if any(c.id != city.id and c.name == city.name for c in self._cities.values()):
            raise BusinessRuleViolation("Город с таким названием уже существует")
        self._cities[city.id] = city
        return city

    def delete(self, city_id: int) -> None:
        if city_id not in self._cities:
            raise NotFoundError(f"Город с id={city_id} не найден.")
        if self.count_screens(city_id) > 0:
            raise BusinessRuleViolation("У города есть привязанные экраны")
        del self._cities[city_id]

    # Хелпер для тестов: сколько экранов «висит» на городе.
    def set_screen_count(self, city_id: int, count: int) -> None:
        self._screen_counts[city_id] = count


def test_city_requires_non_empty_name() -> None:
    """Город нельзя создать с пустым названием (доменное правило)."""
    with pytest.raises(ValidationError):
        City(name="   ")


def test_city_name_is_trimmed() -> None:
    """Название нормализуется — пробелы по краям убираются."""
    assert City(name="  Ош  ").name == "Ош"


def test_create_city_use_case() -> None:
    """Сценарий создаёт город и присваивает id."""
    repo = FakeCityRepository()
    city = CreateCityUseCase(repo).execute(CreateCityInput(name="Токмок"))
    assert city.id == 1
    assert city.name == "Токмок"


def test_create_duplicate_city_conflicts() -> None:
    """Повторное создание города с тем же названием → 409 (BusinessRuleViolation)."""
    repo = FakeCityRepository()
    CreateCityUseCase(repo).execute(CreateCityInput(name="Ош"))
    with pytest.raises(BusinessRuleViolation):
        CreateCityUseCase(repo).execute(CreateCityInput(name="Ош"))


def test_update_city_deactivate() -> None:
    """Сценарий обновления умеет менять активность и название."""
    repo = FakeCityRepository()
    city = CreateCityUseCase(repo).execute(CreateCityInput(name="Нарын"))

    updated = UpdateCityUseCase(repo).execute(
        UpdateCityInput(city_id=city.id, name="Нарын-2", is_active=False)
    )

    assert updated.name == "Нарын-2"
    assert updated.is_active is False


def test_delete_city_with_screens_conflicts() -> None:
    """Удаление города с привязанными экранами запрещено (→ 409)."""
    repo = FakeCityRepository()
    city = CreateCityUseCase(repo).execute(CreateCityInput(name="Бишкек"))
    repo.set_screen_count(city.id, 3)

    with pytest.raises(BusinessRuleViolation):
        repo.delete(city.id)


def test_list_cities_with_screen_counts_sorted() -> None:
    """Список городов отсортирован по названию и несёт число экранов."""
    repo = FakeCityRepository()
    osh = CreateCityUseCase(repo).execute(CreateCityInput(name="Ош"))
    CreateCityUseCase(repo).execute(CreateCityInput(name="Баткен"))
    repo.set_screen_count(osh.id, 5)

    rows = ListCitiesUseCase(repo).execute()

    assert [r.city.name for r in rows] == ["Баткен", "Ош"]
    counts = {r.city.name: r.screens_count for r in rows}
    assert counts["Ош"] == 5
    assert counts["Баткен"] == 0
