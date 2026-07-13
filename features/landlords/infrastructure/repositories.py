"""repositories.py — реализация LandlordRepository на SQLAlchemy.

Работа с таблицей арендодателей. Наружу отдаёт доменные сущности Landlord.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.domain.exceptions import NotFoundError
from features.landlords.domain.entities import Landlord
from features.landlords.domain.repositories import LandlordRepository

from .mappers import landlord_to_domain
from .models import LandlordModel


class SqlAlchemyLandlordRepository(LandlordRepository):
    """Хранилище арендодателей поверх SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Получает сессию БД (внедряется на время HTTP-запроса)."""
        self._session = session

    def get_by_id(self, landlord_id: UUID) -> Landlord:
        """Возвращает арендодателя по id или бросает NotFoundError (→ 404)."""
        model = self._session.get(LandlordModel, landlord_id)
        if model is None:
            raise NotFoundError(f"Арендодатель с id={landlord_id} не найден.")
        return landlord_to_domain(model)

    def exists(self, landlord_id: UUID) -> bool:
        """Проверяет наличие арендодателя по id (без маппинга в домен)."""
        return self._session.get(LandlordModel, landlord_id) is not None

    def list(self) -> list[Landlord]:
        """Возвращает всех арендодателей, отсортированных по названию."""
        stmt = select(LandlordModel).order_by(LandlordModel.name)
        return [landlord_to_domain(m) for m in self._session.scalars(stmt).all()]

    def add(self, landlord: Landlord) -> Landlord:
        """Сохраняет нового арендодателя и возвращает его с присвоенным id."""
        model = LandlordModel(
            name=landlord.name,
            contact_person=landlord.contact_person,
            phone=landlord.phone,
            email=landlord.email,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return landlord_to_domain(model)

    def update(self, landlord: Landlord) -> Landlord:
        """Обновляет существующего арендодателя."""
        model = self._session.get(LandlordModel, landlord.id)
        if model is None:
            raise NotFoundError(f"Арендодатель с id={landlord.id} не найден.")
        model.name = landlord.name
        model.contact_person = landlord.contact_person
        model.phone = landlord.phone
        model.email = landlord.email
        self._session.commit()
        self._session.refresh(model)
        return landlord_to_domain(model)

    def delete(self, landlord_id: UUID) -> None:
        """Удаляет арендодателя по id.

        У экранов внешний ключ landlord_id объявлен как ON DELETE SET NULL —
        поэтому связанные экраны не удаляются, у них лишь очищается арендодатель.
        """
        model = self._session.get(LandlordModel, landlord_id)
        if model is None:
            raise NotFoundError(f"Арендодатель с id={landlord_id} не найден.")
        self._session.delete(model)
        self._session.commit()
