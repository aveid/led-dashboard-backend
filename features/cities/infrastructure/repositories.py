"""repositories.py — реализация CityRepository на SQLAlchemy.

Работа с таблицей городов. Наружу отдаёт доменные сущности City. Конфликты
уникальности названия и запрет удаления города с экранами переводятся в
доменные исключения (BusinessRuleViolation → HTTP 409).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.domain.exceptions import BusinessRuleViolation, NotFoundError
from features.cities.domain.entities import City
from features.cities.domain.repositories import CityRepository, CityWithScreens
from features.screens.infrastructure.models import ScreenModel

from .mappers import city_to_domain
from .models import CityModel

# Сообщение о конфликте уникального названия (единый текст для POST и PATCH).
_DUPLICATE_NAME_MESSAGE = "Город с таким названием уже существует"


class SqlAlchemyCityRepository(CityRepository):
    """Хранилище городов поверх SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Получает сессию БД (внедряется на время HTTP-запроса)."""
        self._session = session

    def list_with_screen_counts(self, only_active: bool = False) -> list[CityWithScreens]:
        """Возвращает города с числом привязанных экранов (LEFT JOIN + COUNT).

        Города без экранов тоже попадают в результат (outerjoin), с counts=0.
        """
        stmt = (
            select(CityModel, func.count(ScreenModel.id).label("screens_count"))
            .outerjoin(ScreenModel, ScreenModel.city_id == CityModel.id)
            .group_by(CityModel.id)
            .order_by(CityModel.name)
        )
        if only_active:
            stmt = stmt.where(CityModel.is_active.is_(True))
        rows = self._session.execute(stmt).all()
        return [
            CityWithScreens(city=city_to_domain(model), screens_count=count)
            for model, count in rows
        ]

    def get_by_id(self, city_id: int) -> City:
        """Возвращает город по id или бросает NotFoundError (→ 404)."""
        model = self._session.get(CityModel, city_id)
        if model is None:
            raise NotFoundError(f"Город с id={city_id} не найден.")
        return city_to_domain(model)

    def count_screens(self, city_id: int) -> int:
        """Возвращает число экранов, привязанных к городу."""
        stmt = select(func.count(ScreenModel.id)).where(ScreenModel.city_id == city_id)
        return int(self._session.scalar(stmt) or 0)

    def add(self, city: City) -> City:
        """Сохраняет новый город; дубликат названия → BusinessRuleViolation (409)."""
        model = CityModel(name=city.name, is_active=city.is_active)
        self._session.add(model)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise BusinessRuleViolation(_DUPLICATE_NAME_MESSAGE) from exc
        self._session.refresh(model)
        return city_to_domain(model)

    def update(self, city: City) -> City:
        """Обновляет город; дубликат названия → BusinessRuleViolation (409)."""
        model = self._session.get(CityModel, city.id)
        if model is None:
            raise NotFoundError(f"Город с id={city.id} не найден.")
        model.name = city.name
        model.is_active = city.is_active
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise BusinessRuleViolation(_DUPLICATE_NAME_MESSAGE) from exc
        self._session.refresh(model)
        return city_to_domain(model)

    def delete(self, city_id: int) -> None:
        """Удаляет город. Если к нему привязаны экраны — BusinessRuleViolation (409).

        Предпроверка count(screens) даёт понятную ошибку; на уровне БД тем же
        барьером стоит внешний ключ screens.city_id ON DELETE RESTRICT.
        """
        model = self._session.get(CityModel, city_id)
        if model is None:
            raise NotFoundError(f"Город с id={city_id} не найден.")
        if self.count_screens(city_id) > 0:
            raise BusinessRuleViolation("У города есть привязанные экраны")
        self._session.delete(model)
        self._session.commit()
