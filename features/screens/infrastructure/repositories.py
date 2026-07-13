"""repositories.py — реализация порта ScreenRepository на SQLAlchemy.

За что отвечает модуль:
    Конкретная работа с БД: выборка, сохранение и удаление экранов. Реализует
    интерфейс ScreenRepository из домена (принцип инверсии зависимостей: домен
    объявил контракт, инфраструктура его выполняет). Наружу всегда отдаёт
    доменные сущности, а не ORM-модели.

Синхронный код: методы обычные (не async), т.к. используем синхронный SQLAlchemy.
"""

from __future__ import annotations

from uuid import UUID

from datetime import date

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from core.domain.exceptions import NotFoundError
from features.screens.domain.constants import EXPIRY_TARGET_STATUS
from features.screens.domain.entities import Attachment, Screen
from features.screens.domain.enums import AttachmentType, ScreenStatus
from features.screens.domain.repositories import ScreenFilters, ScreenRepository

from .mappers import screen_to_domain
from .models import AttachmentModel, CampaignModel, RentalContractModel, ScreenModel


def _to_wkt(screen: Screen) -> WKTElement:
    """Переводит доменную гео-точку в формат PostGIS (WKT, SRID 4326).

    Внимание к порядку: в WKT сначала долгота (x), потом широта (y): POINT(lng lat).
    """
    return WKTElement(
        f"POINT({screen.location.longitude} {screen.location.latitude})", srid=4326
    )


class SqlAlchemyScreenRepository(ScreenRepository):
    """Хранилище экранов поверх SQLAlchemy/PostGIS."""

    def __init__(self, session: Session) -> None:
        """Получает сессию БД (внедряется на время HTTP-запроса через Depends)."""
        self._session = session

    # --- Чтение ---

    def get_by_id(self, screen_id: UUID) -> Screen:
        """Возвращает экран по id или бросает NotFoundError (→ HTTP 404)."""
        model = self._session.get(ScreenModel, screen_id)
        if model is None:
            raise NotFoundError(f"Экран с id={screen_id} не найден.")
        return screen_to_domain(model)

    def list(self, filters: ScreenFilters | None = None) -> list[Screen]:
        """Возвращает экраны, применяя переданные фильтры (FR-5). Пусто → все."""
        stmt = select(ScreenModel)
        if filters is not None:
            stmt = self._apply_filters(stmt, filters)
        models = self._session.scalars(stmt).unique().all()
        return [screen_to_domain(m) for m in models]

    def list_by_ids(self, screen_ids: list[UUID]) -> list[Screen]:
        """Возвращает экраны по списку id (для расчёта стоимости, FR-6)."""
        if not screen_ids:
            return []
        stmt = select(ScreenModel).where(ScreenModel.id.in_(screen_ids))
        models = self._session.scalars(stmt).unique().all()
        return [screen_to_domain(m) for m in models]

    def list_by_landlord(self, landlord_id: UUID) -> list[Screen]:
        """Возвращает экраны арендодателя (FR-8.5) по прямому FK landlord_id.

        Город и тип экрана подтягиваются вместе с экраном (lazy="joined" в
        ScreenModel), поэтому N+1 не возникает; маппер отдаёт доменные Screen.
        """
        stmt = select(ScreenModel).where(ScreenModel.landlord_id == landlord_id)
        models = self._session.scalars(stmt).unique().all()
        return [screen_to_domain(m) for m in models]

    def _apply_filters(self, stmt, filters: ScreenFilters):  # type: ignore[no-untyped-def]
        """Добавляет к запросу условия по заданным фильтрам (незаданные пропускаем)."""
        if filters.landlord_id is not None:
            stmt = stmt.where(ScreenModel.landlord_id == filters.landlord_id)
        if filters.status is not None:
            stmt = stmt.where(ScreenModel.status == filters.status.value)
        if filters.city_id is not None:
            stmt = stmt.where(ScreenModel.city_id == filters.city_id)
        if filters.screen_type_id is not None:
            # Несуществующий screen_type_id даёт пустую выборку — это ожидаемо (§4.3).
            stmt = stmt.where(ScreenModel.screen_type_id == filters.screen_type_id)
        if filters.campaign_id is not None:
            # Экраны, где среди кампаний есть нужная (M2M).
            stmt = stmt.where(ScreenModel.campaigns.any(CampaignModel.id == filters.campaign_id))
        if filters.contract_end_before is not None:
            # Экраны, у которых есть договор, заканчивающийся до указанной даты.
            stmt = stmt.where(
                ScreenModel.rentals.any(
                    RentalContractModel.end_date <= filters.contract_end_before
                )
            )
        return stmt

    def archive_expired(self, today: date) -> int:
        """Bulk-архивация активных экранов с истёкшей арендой одним UPDATE (FR-4.4).

        Предикат — точное зеркало доменного Screen.is_rental_expired: только ACTIVE,
        только с заданной rental_end_date, и только строго ПОСЛЕ последнего дня
        (rental_end_date < today). Обновляем статус на EXPIRY_TARGET_STATUS и бампим
        updated_at. synchronize_session=False — идентити-мап не трогаем (мы читаем
        экраны заново после sweep).

        Не коммитим здесь: фиксация — забота вызывающего (зависимость-триггер
        commit'ит в той же сессии запроса; см. presentation/deps.py). Так UPDATE
        виден последующему SELECT в той же транзакции, а use case остаётся чистым
        для переиспользования будущим Celery-beat. Возвращает число строк (≥ 0).
        """
        stmt = (
            update(ScreenModel)
            .where(
                ScreenModel.status == ScreenStatus.ACTIVE.value,
                ScreenModel.rental_end_date.is_not(None),
                ScreenModel.rental_end_date < today,
            )
            .values(status=EXPIRY_TARGET_STATUS.value, updated_at=func.now())
            .execution_options(synchronize_session=False)
        )
        result = self._session.execute(stmt)
        return result.rowcount or 0

    # --- Запись ---

    def add(self, screen: Screen) -> Screen:
        """Сохраняет новый экран (и его договоры/кампании) и возвращает с id."""
        model = ScreenModel(
            name=screen.name,
            city_id=screen.city_id,
            location=_to_wkt(screen),
            status=screen.status.value,
            landlord_id=screen.landlord_id,
            contact_id=screen.contact_id,
            comment=screen.comment,
            size=screen.size,
            screen_type_id=screen.screen_type_id,
            rental_end_date=screen.rental_end_date,
        )
        self._sync_campaigns(model, screen)
        self._append_rentals(model, screen)
        self._append_attachments(model, screen)

        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return screen_to_domain(model)

    def update(self, screen: Screen) -> Screen:
        """Обновляет существующий экран. Новые договоры добавляются в историю."""
        if screen.id is None:
            raise NotFoundError("Нельзя обновить экран без id.")
        model = self._session.get(ScreenModel, screen.id)
        if model is None:
            raise NotFoundError(f"Экран с id={screen.id} не найден.")

        # Обновляем скалярные поля и координаты.
        model.name = screen.name
        model.city_id = screen.city_id
        model.location = _to_wkt(screen)
        model.status = screen.status.value
        model.landlord_id = screen.landlord_id
        model.contact_id = screen.contact_id
        model.comment = screen.comment
        model.size = screen.size
        model.screen_type_id = screen.screen_type_id
        model.rental_end_date = screen.rental_end_date

        self._sync_campaigns(model, screen)
        self._append_new_rentals(model, screen)
        self._append_new_attachments(model, screen)

        self._session.commit()
        self._session.refresh(model)
        return screen_to_domain(model)

    def delete(self, screen_id: UUID) -> None:
        """Удаляет экран по id (вместе с его договорами и вложениями — каскад)."""
        model = self._session.get(ScreenModel, screen_id)
        if model is None:
            raise NotFoundError(f"Экран с id={screen_id} не найден.")
        self._session.delete(model)
        self._session.commit()

    # --- Вспомогательные методы записи ---

    def _sync_campaigns(self, model: ScreenModel, screen: Screen) -> None:
        """Приводит набор кампаний экрана к списку campaign_ids из домена."""
        if not screen.campaign_ids:
            model.campaigns = []
            return
        stmt = select(CampaignModel).where(CampaignModel.id.in_(screen.campaign_ids))
        model.campaigns = list(self._session.scalars(stmt).all())

    def _append_rentals(self, model: ScreenModel, screen: Screen) -> None:
        """Создаёт строки договоров для нового экрана из его истории аренды."""
        for rental in screen.rentals:
            model.rentals.append(
                RentalContractModel(
                    rent_price=rental.rent_price.amount,
                    currency=rental.rent_price.currency,
                    start_date=rental.start_date,
                    end_date=rental.end_date,
                )
            )

    def _append_new_rentals(self, model: ScreenModel, screen: Screen) -> None:
        """Добавляет в БД только НОВЫЕ договоры (у которых ещё нет id).

        Так история аренды (Q3) пополняется, а существующие записи не дублируются.
        """
        existing_ids = {r.id for r in model.rentals}
        for rental in screen.rentals:
            if rental.id is None or rental.id not in existing_ids:
                model.rentals.append(
                    RentalContractModel(
                        rent_price=rental.rent_price.amount,
                        currency=rental.rent_price.currency,
                        start_date=rental.start_date,
                        end_date=rental.end_date,
                    )
                )

    def _append_attachments(self, model: ScreenModel, screen: Screen) -> None:
        """Создаёт строки вложений для нового экрана из его списка attachments."""
        for att in screen.attachments:
            model.attachments.append(self._new_attachment_model(att))

    def _append_new_attachments(self, model: ScreenModel, screen: Screen) -> None:
        """Добавляет в БД только НОВЫЕ вложения (у которых ещё нет id)."""
        existing_ids = {a.id for a in model.attachments}
        for att in screen.attachments:
            if att.id is None or att.id not in existing_ids:
                model.attachments.append(self._new_attachment_model(att))

    @staticmethod
    def _new_attachment_model(att: Attachment) -> AttachmentModel:
        """Строит ORM-строку вложения из доменного Attachment."""
        return AttachmentModel(
            type=att.type.value,
            object_key=att.object_key,
            original_filename=att.original_filename,
            content_type=att.content_type,
            size_bytes=att.size_bytes,
        )

    def delete_attachment(self, attachment_id: UUID) -> None:
        """Удаляет одну строку вложения по id (идемпотентно)."""
        model = self._session.get(AttachmentModel, attachment_id)
        if model is not None:
            self._session.delete(model)
            self._session.commit()

    def count_attachments_by_type(
        self, screen_id: UUID, attachment_type: AttachmentType
    ) -> int:
        """Считает вложения заданного вида у экрана одним COUNT-запросом."""
        stmt = (
            select(func.count())
            .select_from(AttachmentModel)
            .where(
                AttachmentModel.screen_id == screen_id,
                AttachmentModel.type == attachment_type.value,
            )
        )
        return self._session.scalar(stmt) or 0
