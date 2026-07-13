"""dto.py — DTO (Data Transfer Objects) прикладного слоя фичи «экраны».

Что такое DTO:
    Простые контейнеры данных для передачи между слоями. Они отделяют «форму»
    входа/выхода сценария от доменных сущностей и от JSON API, поэтому сценарий
    не зависит ни от Pydantic-схем презентации, ни от деталей БД.

За что отвечает модуль:
    • входные DTO для сценариев (например, данные для создания экрана);
    • выходные DTO для результатов (например, результат расчёта стоимости).

Все DTO — неизменяемые (frozen) датаклассы: их удобно создавать и безопасно
передавать, не опасаясь случайных изменений.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from core.domain.value_objects import Money
from features.cities.domain.entities import City
from features.screen_types.domain.entities import ScreenType
from features.screens.domain.enums import AttachmentType, ScreenStatus


@dataclass(frozen=True)
class CreateScreenInput:
    """Входные данные для создания экрана (сценарий CreateScreenUseCase).

    Плоская структура (город/координаты по отдельности), удобная для приёма из
    HTTP-запроса. Сценарий сам соберёт из неё доменный объект GeoPoint. Координаты
    приходят из точки клика по карте (FR-3.3), отдельных текстовых полей адреса нет.

    campaign_ids — размещённые кампании (сейчас 0 или 1, Q4). Кортеж, а не список,
    чтобы DTO оставался неизменяемым.
    """

    name: str
    city_id: int
    latitude: float
    longitude: float
    size: str            # размер экрана (свободный текст), обязателен при создании
    screen_type_id: int  # ссылка на справочник типов, обязателен при создании
    status: ScreenStatus = ScreenStatus.POTENTIAL
    landlord_id: UUID | None = None
    contact_id: UUID | None = None
    campaign_ids: tuple[UUID, ...] = ()
    comment: str = ""
    # Последний день аренды включительно (FR-4.4); None — бессрочная (не истекает).
    rental_end_date: date | None = None


@dataclass(frozen=True)
class UpdateScreenInput:
    """Входные данные для редактирования экрана (FR-10.2).

    Большинство полей необязательны: None означает «не менять». Для полей-ссылок
    (landlord_id/contact_id) в MVP None тоже трактуется как «не менять» —
    отдельное «снять значение» добавим позже при необходимости.

    Исключение — size и screen_type_id: форма редактирования всегда шлёт их (§4.2),
    поэтому они обязательны и всегда применяются. size обязан быть непустым
    (проверяет Pydantic-схема), screen_type_id — существовать (проверяет сценарий).

    Смена статуса на «активный» через это редактирование разрешена как обычный
    переход: договор больше не является предусловием активации. Полный сценарий
    «оформить аренду» с фиксацией договора остаётся отдельным (ActivateScreenUseCase).
    """

    screen_id: UUID
    size: str            # форма всегда шлёт непустой размер (§4.2), обязателен
    screen_type_id: int  # форма всегда шлёт тип экрана (§4.2), обязателен
    name: str | None = None
    city_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: ScreenStatus | None = None
    landlord_id: UUID | None = None
    contact_id: UUID | None = None
    campaign_ids: tuple[UUID, ...] | None = None
    comment: str | None = None
    # Дата окончания аренды (FR-4.4). Для неё «None» неоднозначно (не прислано vs
    # «очистить дату» → бессрочная аренда), поэтому решает отдельный флаг
    # apply_rental_end_date: применяем поле, ТОЛЬКО когда фронт его действительно
    # прислал (роутер выставляет флаг по payload.model_fields_set). Это позволяет
    # очистить дату явным null (сценарий реактивации, §6), не затирая её случайно
    # при обычном PATCH других полей.
    rental_end_date: date | None = None
    apply_rental_end_date: bool = False


@dataclass(frozen=True)
class UpdateScreenLocationInput:
    """Входные данные для смены локации экрана точкой на карте (FR-3.3).

    Отдельный узкий сценарий «перетащить пин и сохранить»: несёт только id экрана
    и новые координаты, чтобы не переотправлять всю сущность. Сценарий соберёт из
    координат доменный GeoPoint (с проверкой диапазонов) и вызовет Screen.relocate.
    """

    screen_id: UUID
    latitude: float
    longitude: float


@dataclass(frozen=True)
class ActivateScreenInput:
    """Входные данные для активации экрана (FR-4).

    Активация переводит экран в статус «активный» и фиксирует договор аренды за
    период. Доменное правило (FR-4.2) требует, чтобы у экрана уже были указаны
    арендодатель и прикреплено фото — иначе активация будет отклонена. Наличие
    ДОГОВОРА (Attachment типа CONTRACT) больше не требуется (договор опционален);
    перевести экран в «активный» без договора можно и через UpdateScreen.
    """

    screen_id: UUID
    rent_price: Decimal        # стоимость аренды в месяц (Q1)
    start_date: date           # дата начала аренды
    end_date: date             # дата окончания договора
    currency: str = "KGS"


@dataclass(frozen=True)
class AddAttachmentInput:
    """Входные данные для загрузки вложения к экрану (FR-3.12/3.13).

    Сюда приходит СЫРОЙ файл (байты + метаданные из multipart-запроса). Сценарий
    сам проверит MIME/размер, положит файл в хранилище под сгенерированным ключом и
    создаст запись вложения. Так презентация не знает про хранилище и ключи объектов.
    """

    screen_id: UUID
    attachment_type: AttachmentType
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class LandlordScreenBrief:
    """Облегчённый экран в списке экранов арендодателя (FR-8.5).

    Компактный DTO для выпадающего списка «экраны арендодателя»: без тяжёлых
    полей (attachments/presign сюда НЕ входят — §2 инструкции). Гео-координаты
    (lng/lat) отдаём, чтобы фронт мог показать экран на карте по тапу.

    Вложенные city/screen_type держим как доменные сущности — слой представления
    сам сериализует их теми же мини-схемами, что и в ScreenRead (без дублирования).
    """

    id: UUID
    name: str
    status: ScreenStatus
    size: str
    city_id: int
    city: City
    screen_type_id: int
    screen_type: ScreenType
    lng: float
    lat: float
    # Месячная аренда экрана (FR-8.4). None — если цены нет (экран не арендуется):
    # фронт трактует отсутствие как «скрыть», а не «0». Тот же Money VO, что и в
    # полном ScreenRead — формат денег наружу совпадает.
    monthly_price: Money | None = None


@dataclass(frozen=True)
class LandlordCost:
    """Разбивка стоимости по одному арендодателю (часть результата FR-6.4 и FR-9.4).

    Имя арендодателя здесь не хранится — только его id и агрегаты. Человекочитаемое
    название подставляет слой представления (по данным арендодателей).
    """

    landlord_id: UUID | None    # None — если у экранов не указан арендодатель
    screens_count: int          # сколько экранов у этого арендодателя (в выборке)
    total: Money                # суммарная аренда по ним


@dataclass(frozen=True)
class CostSummaryResult:
    """Результат расчёта стоимости выбранных экранов (FR-6.2–FR-6.4).

    Соответствует примеру из брифа: «Выбрано 8 · Итого 220 000 сом · разбивка».
    """

    selected_count: int                     # сколько экранов выбрано (FR-6.2)
    total: Money                            # общая стоимость аренды (FR-6.3)
    by_landlord: list[LandlordCost] = field(default_factory=list)  # разбивка (FR-6.4)


@dataclass(frozen=True)
class EndingContract:
    """Договор, который скоро заканчивается (FR-9.5) — строка для списка на дашборде."""

    screen_id: UUID
    screen_name: str
    landlord_id: UUID | None
    end_date: date


@dataclass(frozen=True)
class DashboardSummaryResult:
    """Сводная информация для главного экрана (FR-9).

    total_screens — всего экранов в базе (FR-9.1);
    active_count/inactive_count/potential_count/archived_count — разбивка по
    статусам, active/inactive — отдельно, как того требует FR-9.2;
    total_active_rent — суммарная аренда АКТИВНЫХ экранов в месяц (FR-9.3);
    by_landlord — количество экранов и сумма аренды по каждому арендодателю (FR-9.4);
    ending_soon — договоры активных экранов, заканчивающиеся в пределах порога (FR-9.5).
    """

    total_screens: int
    active_count: int
    inactive_count: int
    potential_count: int
    archived_count: int
    total_active_rent: Money
    by_landlord: list[LandlordCost] = field(default_factory=list)
    ending_soon: list[EndingContract] = field(default_factory=list)
