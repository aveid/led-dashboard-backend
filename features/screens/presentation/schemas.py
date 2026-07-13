"""schemas.py — Pydantic-схемы (контракты HTTP) фичи «экраны».

За что отвечает модуль:
    Описывает форму данных на границе HTTP: что приходит в запросе и что уходит
    в ответе. Схемы валидируют вход и сериализуют выход, а также автоматически
    попадают в OpenAPI-документацию FastAPI (контракт для фронтенда).

Схемы ≠ доменные сущности: это «внешний» формат. Перевод схема↔домен делают
эндпоинты (через DTO прикладного слоя) и функция screen_to_read (mappers.py).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from features.cities.presentation.schemas import CityRead
from features.screen_types.presentation.schemas import ScreenTypeRead
from features.screens.domain.enums import AttachmentType, ScreenStatus


class MoneySchema(BaseModel):
    """Денежная сумма в ответе: величина и валюта."""

    amount: Decimal
    currency: str = "KGS"


class RentalContractSchema(BaseModel):
    """Договор аренды (период + цена) в ответе.

    rent_price nullable: для роли guest цена договора форсится в null (та же
    редакция «цены пустые», что и для monthly_price — §0/§4).
    """

    id: UUID | None = None
    rent_price: MoneySchema | None
    start_date: date
    end_date: date


class ScreenCreate(BaseModel):
    """Тело запроса на создание экрана (FR-10.1).

    Координаты — плоскими полями (из точки клика по карте, FR-3.3); сервер соберёт
    из них доменную гео-точку. Отдельных текстовых полей адреса (район/улица) нет.
    """

    name: str
    city_id: int
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    # size обязателен и непустой; screen_type_id обязателен (§4.2). Отсутствие/пустой
    # size / отсутствие screen_type_id → 422 (Pydantic) ещё до сценария.
    size: str = Field(min_length=1, max_length=100)
    screen_type_id: int
    status: ScreenStatus = ScreenStatus.POTENTIAL
    landlord_id: UUID | None = None
    contact_id: UUID | None = None
    campaign_ids: list[UUID] = Field(default_factory=list)
    comment: str = ""
    # Последний день аренды включительно (FR-4.4), формат YYYY-MM-DD. Необязательно;
    # null/отсутствие → бессрочная аренда (экран не будет авто-архивироваться).
    rental_end_date: date | None = None


class ScreenUpdate(BaseModel):
    """Тело запроса на редактирование экрана (FR-10.2).

    Присланные поля обновляются, отсутствующие остаются как были. Исключение —
    size и screen_type_id: форма редактирования всегда их шлёт (§4.2), поэтому они
    обязательны. size обязан быть непустым — редактирование старого экрана с пустым
    size без ввода значения отклоняется (422).
    """

    size: str = Field(min_length=1, max_length=100)
    screen_type_id: int
    name: str | None = None
    city_id: int | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: ScreenStatus | None = None
    landlord_id: UUID | None = None
    contact_id: UUID | None = None
    campaign_ids: list[UUID] | None = None
    comment: str | None = None
    # Дата окончания аренды (FR-4.4). Необязательное поле; допускается явный null,
    # чтобы СНЯТЬ дату (сделать аренду бессрочной — сценарий реактивации, §6).
    # Роутер отличает «не прислано» от «null» через model_fields_set, поэтому
    # отсутствие поля не затирает уже сохранённую дату.
    rental_end_date: date | None = None


class ScreenLocationUpdate(BaseModel):
    """Тело запроса на смену локации экрана точкой на карте (FR-3.3).

    Координаты в WGS84 (SRID 4326). Диапазоны валидируются здесь (Pydantic вернёт
    422 при выходе за них ещё до сценария).
    """

    lng: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)


class AttachmentRead(BaseModel):
    """Вложение экрана в ответе: фото, договор или документ (FR-3.12/3.13).

    url — короткоживущая presigned-ссылка на скачивание файла напрямую из хранилища
    (без JWT приложения). Она собирается на каждый ответ заново, поэтому всегда свежая.
    """

    id: UUID | None = None
    type: AttachmentType
    filename: str
    content_type: str
    size_bytes: int
    url: str
    uploaded_at: datetime | None = None


class AttachmentUrlResponse(BaseModel):
    """Ответ на запрос обновления ссылки: свежая presigned-ссылка и её TTL (сек)."""

    url: str
    expires_in: int


class ScreenRead(BaseModel):
    """Экран в ответе API (карточка экрана, FR-3)."""

    id: UUID
    name: str
    city: CityRead
    latitude: float
    longitude: float
    size: str
    screen_type_id: int
    screen_type: ScreenTypeRead
    status: ScreenStatus
    landlord_id: UUID | None
    contact_id: UUID | None
    campaign_ids: list[UUID]
    current_campaign_id: UUID | None
    # Nullable: обычно всегда заполнено (домен отдаёт Money.zero() при отсутствии
    # аренды, null ≠ 0). Для роли guest презентационная редакция форсит цену в null
    # (см. mappers.screen_to_read(is_guest=True)) — поэтому поле допускает None.
    monthly_price: MoneySchema | None
    rentals: list[RentalContractSchema]
    attachments: list[AttachmentRead]
    comment: str
    # Последний день аренды включительно (FR-4.4); null — бессрочная аренда.
    rental_end_date: date | None


class LandlordScreenBrief(BaseModel):
    """Облегчённый экран в списке экранов арендодателя (FR-8.5, SSOT для фронта).

    Компактный ответ для выпадающего списка «экраны арендодателя»: без тяжёлых
    полей — attachments сюда НЕ входят (осознанно, чтобы не делать presign на
    каждый экран). Вложенные city/screen_type — те же мини-схемы, что и в
    ScreenRead. lng/lat отдаём, чтобы фронт мог показать экран на карте по тапу.
    """

    id: UUID
    name: str
    status: ScreenStatus
    size: str
    city_id: int
    city: CityRead
    screen_type_id: int
    screen_type: ScreenTypeRead
    lng: float
    lat: float
    # Месячная аренда экрана (FR-8.4). Та же MoneySchema, что и в ScreenRead
    # (ключи amount/currency, amount из Decimal — формат денег наружу совпадает).
    # None — если цены нет (экран не арендуется); фронт скрывает, а не показывает 0.
    monthly_price: MoneySchema | None = None


class CostSummaryRequest(BaseModel):
    """Запрос расчёта стоимости выбранных экранов (FR-6): список их id."""

    screen_ids: list[UUID]


class ScreenActivateRequest(BaseModel):
    """Тело запроса на активацию экрана (FR-4): условия договора аренды.

    Экран будет активирован, только если у него уже указан арендодатель и
    прикреплено фото (правило FR-4.2 проверяется на сервере). Наличие договора
    (Attachment типа CONTRACT) больше не требуется; активировать без договора
    можно и через обычное редактирование (PATCH /api/screens/{id}, status=active).
    """

    rent_price: Decimal = Field(gt=0, description="Стоимость аренды в месяц")
    start_date: date
    end_date: date
    currency: str = "KGS"


class LandlordCostSchema(BaseModel):
    """Разбивка стоимости по одному арендодателю (FR-6.4).

    total nullable: для роли guest денежные агрегаты форсятся в null (редакция).
    """

    landlord_id: UUID | None
    screens_count: int
    total: MoneySchema | None


class CostSummaryResponse(BaseModel):
    """Ответ расчёта стоимости выбранных экранов (FR-6.2–6.4).

    total nullable: для роли guest итог и разбивка по арендодателям форсятся в null.
    """

    selected_count: int
    total: MoneySchema | None
    by_landlord: list[LandlordCostSchema]


class TokenResponse(BaseModel):
    """Ответ на вход: JWT access-токен."""

    access_token: str
    token_type: str = "bearer"


class EndingContractSchema(BaseModel):
    """Договор, заканчивающийся в пределах порога (FR-9.5), в ответе API."""

    screen_id: UUID
    screen_name: str
    landlord_id: UUID | None
    end_date: date


class DashboardSummaryResponse(BaseModel):
    """Сводная информация для главного экрана (FR-9)."""

    total_screens: int
    active_count: int
    inactive_count: int
    potential_count: int
    archived_count: int
    # nullable: для роли guest денежный агрегат аренды форсится в null (редакция).
    total_active_rent: MoneySchema | None
    by_landlord: list[LandlordCostSchema]
    ending_soon: list[EndingContractSchema]
