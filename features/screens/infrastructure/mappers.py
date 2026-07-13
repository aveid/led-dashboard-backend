"""mappers.py — преобразование между ORM-моделями и доменными сущностями.

Зачем нужны мапперы:
    Домен и БД — разные миры. Домен оперирует сущностями (Screen, RentalContract)
    с поведением; БД — строками таблиц. Мапперы переводят один мир в другой,
    удерживая границу слоёв: репозиторий отдаёт наружу доменные объекты, а не
    ORM-модели. Так остальной код не зависит от SQLAlchemy.

Здесь только направление ORM → домен (чтение). Обратное направление (запись
доменных данных в модель) выполняет репозиторий, т.к. ему нужна сессия БД.
"""

from __future__ import annotations

from decimal import Decimal

from geoalchemy2.shape import to_shape

from core.domain.value_objects import GeoPoint, Money
from features.cities.infrastructure.mappers import city_to_domain
from features.screen_types.infrastructure.mappers import screen_type_to_domain
from features.screens.domain.entities import Attachment, RentalContract, Screen
from features.screens.domain.enums import AttachmentType, ScreenStatus

from .models import AttachmentModel, RentalContractModel, ScreenModel


def rental_to_domain(model: RentalContractModel) -> RentalContract:
    """Строка договора (ORM) → доменный RentalContract."""
    return RentalContract(
        rent_price=Money(Decimal(model.rent_price), model.currency),
        start_date=model.start_date,
        end_date=model.end_date,
        id=model.id,
    )


def attachment_to_domain(model: AttachmentModel) -> Attachment:
    """Строка вложения (ORM) → доменный Attachment."""
    return Attachment(
        type=AttachmentType(model.type),
        object_key=model.object_key,
        original_filename=model.original_filename,
        content_type=model.content_type,
        size_bytes=model.size_bytes,
        uploaded_at=model.uploaded_at,
        id=model.id,
    )


def screen_to_domain(model: ScreenModel) -> Screen:
    """Строка экрана (ORM) со связями → доменный Screen.

    Координаты достаём из PostGIS-объекта через shapely: point.x — долгота,
    point.y — широта.
    """
    point = to_shape(model.location)  # shapely Point
    return Screen(
        name=model.name,
        city_id=model.city_id,
        location=GeoPoint(latitude=point.y, longitude=point.x),
        status=ScreenStatus(model.status),
        landlord_id=model.landlord_id,
        contact_id=model.contact_id,
        campaign_ids=[c.id for c in model.campaigns],
        rentals=[rental_to_domain(r) for r in model.rentals],
        comment=model.comment,
        attachments=[attachment_to_domain(a) for a in model.attachments],
        size=model.size,
        screen_type_id=model.screen_type_id,
        # Тип загружен вместе с экраном (lazy="joined") — отдаём его в домен для отображения.
        screen_type=(
            screen_type_to_domain(model.screen_type)
            if model.screen_type is not None
            else None
        ),
        # Город загружен вместе с экраном (lazy="joined") — отдаём его в домен для отображения.
        city=city_to_domain(model.city) if model.city is not None else None,
        rental_end_date=model.rental_end_date,
        id=model.id,
    )
