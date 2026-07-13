"""use_cases.py — сценарии модуля арендодателей (create / update / list).

За что отвечает: оркестрирует работу с арендодателями через порт репозитория.
Справочник простой, поэтому сценарии с логикой (создание/редактирование/список)
собраны в одном файле. Операции get/delete тривиальны и вызываются в роутере
напрямую через репозиторий.
"""

from __future__ import annotations

from core.application.use_case import UseCase
from features.landlords.application.dto import CreateLandlordInput, UpdateLandlordInput
from features.landlords.domain.entities import Landlord
from features.landlords.domain.repositories import LandlordRepository


class CreateLandlordUseCase(UseCase[CreateLandlordInput, Landlord]):
    """Создаёт нового арендодателя."""

    def __init__(self, repository: LandlordRepository) -> None:
        self._repository = repository

    def execute(self, data: CreateLandlordInput) -> Landlord:
        """Собирает доменного арендодателя (с валидацией) и сохраняет его."""
        landlord = Landlord(
            name=data.name,
            contact_person=data.contact_person,
            phone=data.phone,
            email=data.email,
        )
        return self._repository.add(landlord)


class UpdateLandlordUseCase(UseCase[UpdateLandlordInput, Landlord]):
    """Редактирует существующего арендодателя (частичное обновление)."""

    def __init__(self, repository: LandlordRepository) -> None:
        self._repository = repository

    def execute(self, data: UpdateLandlordInput) -> Landlord:
        """Загружает арендодателя, применяет присланные поля и сохраняет."""
        landlord = self._repository.get_by_id(data.landlord_id)
        if data.name is not None:
            # Пересоздаём проверку имени, присваивая через конструктор недопустимо,
            # поэтому валидируем вручную тем же правилом.
            if not data.name.strip():
                from core.domain.exceptions import ValidationError

                raise ValidationError("У арендодателя должно быть непустое название.")
            landlord.name = data.name
        if data.contact_person is not None:
            landlord.contact_person = data.contact_person
        if data.phone is not None:
            landlord.phone = data.phone
        if data.email is not None:
            landlord.email = data.email
        return self._repository.update(landlord)


class ListLandlordsUseCase(UseCase[None, list[Landlord]]):
    """Возвращает список всех арендодателей (для справочника)."""

    def __init__(self, repository: LandlordRepository) -> None:
        self._repository = repository

    def execute(self, data: None = None) -> list[Landlord]:
        """Отдаёт всех арендодателей."""
        return self._repository.list()
