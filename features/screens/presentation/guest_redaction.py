"""guest_redaction.py — серверная редакция read-ответов для роли `guest`.

За что отвечает модуль:
    Гость (`UserRole.GUEST`) имеет доступ как `user` (только чтение/просмотр/
    экспорт), НО из любого read-ответа, достижимого для него, убираются:
      • цены — любое денежное поле форсится в `null` (null ≠ 0, существующая
        семантика Money-схемы);
      • договор/документы — вложения не-PHOTO (в этом проекте это CONTRACT и
        OTHER) не отдаются вовсе; presigned-url на них гостю не выдаётся.

    Граница безопасности — здесь, на бэке: гость не должен получить цену или
    документ даже из сырого JSON/devtools. Фронт делает то же как UX, но
    авторитетен бэкенд.

Чистые функции (без мутации оригинала — через `model_copy(update=...)`), живут
ТОЛЬКО в presentation-слое. Домен и use-cases ролью НЕ параметризуются.

Важно по вложениям: фильтр не-PHOTO выполняется ДО presign-энричмента — чтобы
для документов вообще не генерировать ссылку (иначе утечка url в JSON). Поэтому
фильтрация вложений живёт как `guest_visible_attachments` (над доменными
Attachment, до маппинга), а не над уже собранной ScreenRead — см.
`mappers.screen_to_read(is_guest=True)`.
"""

from __future__ import annotations

from collections.abc import Iterable

from features.screens.domain.entities import Attachment
from features.screens.domain.enums import AttachmentType

from .schemas import (
    CostSummaryResponse,
    DashboardSummaryResponse,
    LandlordScreenBrief,
)


def guest_visible_attachments(attachments: Iterable[Attachment]) -> list[Attachment]:
    """Оставляет гостю только PHOTO-вложения; договор/документы (не-PHOTO) скрыты.

    Работает над доменными Attachment ДО presign — чтобы ссылки на документы
    вообще не генерировались (§0/§4 инструкции: «не презайним их»).
    """
    return [a for a in attachments if a.type == AttachmentType.PHOTO]


def redact_landlord_brief(brief: LandlordScreenBrief) -> LandlordScreenBrief:
    """Бриф экрана арендодателя для гостя: цена → null (§4)."""
    return brief.model_copy(update={"monthly_price": None})


def redact_cost_summary(response: CostSummaryResponse) -> CostSummaryResponse:
    """Расчёт стоимости для гостя: итог и все суммы по арендодателям → null (§4)."""
    return response.model_copy(
        update={
            "total": None,
            "by_landlord": [
                item.model_copy(update={"total": None}) for item in response.by_landlord
            ],
        }
    )


def redact_dashboard_summary(response: DashboardSummaryResponse) -> DashboardSummaryResponse:
    """Сводка дашборда для гостя: денежные агрегаты → null (§4).

    Счётчики по статусам и список «скоро заканчивается» (только даты) остаются —
    денег в них нет.
    """
    return response.model_copy(
        update={
            "total_active_rent": None,
            "by_landlord": [
                item.model_copy(update={"total": None}) for item in response.by_landlord
            ],
        }
    )
