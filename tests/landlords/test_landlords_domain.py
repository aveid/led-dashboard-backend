"""Тесты доменных правил и сценариев модуля «арендодатели» (FR-8).

Без БД: используется фейковый репозиторий в памяти.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from core.domain.exceptions import ValidationError
from features.landlords.application.dto import CreateLandlordInput, UpdateLandlordInput
from features.landlords.application.use_cases import (
    CreateLandlordUseCase,
    ListLandlordsUseCase,
    UpdateLandlordUseCase,
)
from features.landlords.domain.entities import Landlord
from features.landlords.domain.repositories import LandlordRepository


class FakeLandlordRepository(LandlordRepository):
    """Репозиторий в памяти — подмена БД для тестов сценариев."""

    def __init__(self, landlords: list[Landlord] | None = None) -> None:
        self._items = {item.id: item for item in (landlords or [])}

    def get_by_id(self, landlord_id: UUID) -> Landlord:
        return self._items[landlord_id]

    def exists(self, landlord_id: UUID) -> bool:
        return landlord_id in self._items

    def list(self) -> list[Landlord]:
        return list(self._items.values())

    def add(self, landlord: Landlord) -> Landlord:
        """Имитирует поведение SQLAlchemy-репозитория: присваивает id при сохранении."""
        if landlord.id is None:
            landlord.id = uuid4()
        self._items[landlord.id] = landlord
        return landlord

    def update(self, landlord: Landlord) -> Landlord:
        self._items[landlord.id] = landlord
        return landlord

    def delete(self, landlord_id: UUID) -> None:
        self._items.pop(landlord_id, None)


def test_landlord_requires_non_empty_name() -> None:
    """Нельзя создать арендодателя с пустым названием."""
    with pytest.raises(ValidationError):
        Landlord(name="   ")


def test_create_landlord_use_case() -> None:
    """Сценарий создания сохраняет арендодателя со всеми полями."""
    repo = FakeLandlordRepository()

    landlord = CreateLandlordUseCase(repo).execute(
        CreateLandlordInput(name="Mega24", contact_person="Айбек", phone="+996700000000")
    )

    assert landlord.name == "Mega24"
    assert landlord.id is not None
    assert repo.get_by_id(landlord.id).contact_person == "Айбек"


def test_update_landlord_use_case_partial() -> None:
    """Редактирование меняет только переданные поля."""
    landlord = Landlord(name="Старое имя", phone="000", id=uuid4())
    repo = FakeLandlordRepository([landlord])

    updated = UpdateLandlordUseCase(repo).execute(
        UpdateLandlordInput(landlord_id=landlord.id, name="Новое имя")
    )

    assert updated.name == "Новое имя"
    assert updated.phone == "000"  # не изменился


def test_list_landlords_use_case() -> None:
    """Сценарий списка возвращает все сохранённые записи."""
    repo = FakeLandlordRepository([Landlord(name="A", id=uuid4()), Landlord(name="B", id=uuid4())])

    result = ListLandlordsUseCase(repo).execute()

    assert len(result) == 2
