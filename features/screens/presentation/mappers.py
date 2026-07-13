"""mappers.py (presentation) — перевод доменной сущности в схему ответа.

За что отвечает: превращает доменный Screen в ScreenRead (Pydantic) для отдачи
клиенту. Держит презентационную логику сериализации в одном месте, чтобы
эндпоинты оставались тонкими.
"""

from __future__ import annotations

from core.application.storage import FileStorage
from features.cities.presentation.mappers import city_to_read
from features.screen_types.presentation.mappers import screen_type_to_read
from features.screens.application.dto import LandlordScreenBrief
from features.screens.domain.entities import Screen

from .guest_redaction import guest_visible_attachments
from .schemas import AttachmentRead, MoneySchema, RentalContractSchema, ScreenRead
from .schemas import LandlordScreenBrief as LandlordScreenBriefSchema


def screen_to_read(
    screen: Screen, storage: FileStorage, expires_in: int, is_guest: bool = False
) -> ScreenRead:
    """Доменный Screen → схема ScreenRead для ответа API.

    Город отдаётся вложенным объектом CityRead. Он всегда загружен вместе с
    экраном (lazy="joined") и проставлен инфраструктурным маппером, поэтому
    screen.city здесь не None. screens_count для вложенного города не считаем
    (это агрегат списка городов) — оставляем 0.

    Для каждого вложения собираем свежую presigned-ссылку (url) из object_key
    через хранилище — это единственная точка генерации ссылок при чтении.

    is_guest — редакция для роли `guest` (§4): цена форсится в null, а
    договор/документы (вложения не-PHOTO) отбрасываются ДО presign, чтобы ссылки
    на них не генерировались вовсе (границу безопасности держит бэкенд).
    """
    attachments = guest_visible_attachments(screen.attachments) if is_guest else screen.attachments
    monthly_price = (
        None
        if is_guest
        else MoneySchema(
            amount=screen.monthly_price.amount, currency=screen.monthly_price.currency
        )
    )
    return ScreenRead(
        id=screen.id,  # у сохранённого экрана id всегда есть
        name=screen.name,
        city=city_to_read(screen.city),
        latitude=screen.location.latitude,
        longitude=screen.location.longitude,
        size=screen.size,
        screen_type_id=screen.screen_type_id,
        # Тип всегда загружен вместе с экраном (lazy="joined") и проставлен маппером,
        # поэтому screen.screen_type здесь не None (после backfill + NOT NULL).
        screen_type=screen_type_to_read(screen.screen_type),
        status=screen.status,
        landlord_id=screen.landlord_id,
        contact_id=screen.contact_id,
        campaign_ids=screen.campaign_ids,
        current_campaign_id=screen.current_campaign_id,
        monthly_price=monthly_price,
        rentals=[
            RentalContractSchema(
                id=r.id,
                # Для guest цена договора тоже форсится в null («цены пустые», §0).
                rent_price=(
                    None
                    if is_guest
                    else MoneySchema(amount=r.rent_price.amount, currency=r.rent_price.currency)
                ),
                start_date=r.start_date,
                end_date=r.end_date,
            )
            for r in screen.rentals
        ],
        attachments=[
            AttachmentRead(
                id=a.id,
                type=a.type,
                filename=a.original_filename,
                content_type=a.content_type,
                size_bytes=a.size_bytes,
                url=storage.generate_presigned_get_url(a.object_key, expires_in),
                uploaded_at=a.uploaded_at,
            )
            for a in attachments
        ],
        comment=screen.comment,
        rental_end_date=screen.rental_end_date,
    )


def landlord_screen_brief_to_read(brief: LandlordScreenBrief) -> LandlordScreenBriefSchema:
    """Прикладной DTO LandlordScreenBrief → схема ответа API (FR-8.5).

    Вложенные city/screen_type сериализуем теми же мини-схемами, что и в ScreenRead
    (city_to_read/screen_type_to_read) — без дублирования. Attachments/presign в
    этот путь не входят намеренно (компактный список для дропдауна).
    """
    return LandlordScreenBriefSchema(
        id=brief.id,
        name=brief.name,
        status=brief.status,
        size=brief.size,
        city_id=brief.city_id,
        city=city_to_read(brief.city),
        screen_type_id=brief.screen_type_id,
        screen_type=screen_type_to_read(brief.screen_type),
        lng=brief.lng,
        lat=brief.lat,
        # Money → та же MoneySchema, что и в ScreenRead; None остаётся None (нет цены).
        monthly_price=(
            MoneySchema(amount=brief.monthly_price.amount, currency=brief.monthly_price.currency)
            if brief.monthly_price is not None
            else None
        ),
    )
