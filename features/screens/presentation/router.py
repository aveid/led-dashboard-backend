"""router.py — REST-эндпоинты фичи «экраны» (FastAPI).

За что отвечает модуль:
    Определяет HTTP-маршруты для экранов и связывает их с прикладными сценариями.
    Эндпоинты тонкие: разбирают запрос → вызывают use case → возвращают ответ.
    Никакой бизнес-логики здесь нет (она в домене/приложении).

Все маршруты защищены зависимостью get_current_user (нужен валидный JWT).
Документация по ним автоматически появляется в /api/docs (OpenAPI).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from core.api.auth import get_current_user, require_admin, require_non_guest
from core.api.pagination import PaginationParams
from core.application.storage import FileStorage
from core.domain.exceptions import NotFoundError, ValidationError
from core.domain.value_objects import Money
from features.users.domain.entities import User, UserRole
from features.campaigns.domain.repositories import CampaignRepository
from features.campaigns.presentation.deps import get_campaign_repository
from features.landlords.domain.repositories import LandlordRepository
from features.landlords.presentation.deps import get_landlord_repository
from features.screens.application.dto import (
    ActivateScreenInput,
    AddAttachmentInput,
    CreateScreenInput,
    UpdateScreenInput,
    UpdateScreenLocationInput,
)
from features.screens.application.use_cases.activate_screen import ActivateScreenUseCase
from features.screens.application.use_cases.add_attachment import AddAttachmentUseCase
from features.screens.application.use_cases.cost_summary import CostSummaryUseCase
from features.screens.application.use_cases.delete_attachment import (
    DeleteAttachmentInput,
    DeleteAttachmentUseCase,
)
from features.screens.application.use_cases.create_screen import CreateScreenUseCase
from features.screens.application.use_cases.dashboard_summary import (
    DashboardSummaryInput,
    DashboardSummaryUseCase,
)
from features.screens.application.use_cases.export_screens import (
    ExportScreensInput,
    ExportScreensUseCase,
)
from features.screens.application.use_cases.list_screens import ListScreensUseCase
from features.screens.application.use_cases.update_screen import UpdateScreenUseCase
from features.screens.application.use_cases.update_screen_location import (
    UpdateScreenLocationUseCase,
)
from features.screen_types.domain.repositories import ScreenTypeRepository
from features.screen_types.presentation.deps import get_screen_type_repository
from features.screens.domain.attachment_policy import AttachmentLimitExceededError
from features.screens.domain.enums import AttachmentType, ScreenStatus
from features.screens.domain.repositories import ScreenFilters, ScreenRepository
from features.screens.infrastructure.excel_export import build_screens_workbook

from .deps import (
    expire_due_screens,
    get_file_storage,
    get_presign_expiry,
    get_screen_repository,
)
from .guest_redaction import redact_cost_summary, redact_dashboard_summary
from .mappers import screen_to_read
from .schemas import (
    AttachmentUrlResponse,
    CostSummaryRequest,
    CostSummaryResponse,
    DashboardSummaryResponse,
    EndingContractSchema,
    LandlordCostSchema,
    MoneySchema,
    ScreenActivateRequest,
    ScreenCreate,
    ScreenLocationUpdate,
    ScreenRead,
    ScreenUpdate,
)

# Общая зависимость: все маршруты требуют аутентификации.
router = APIRouter(
    prefix="/api/screens",
    tags=["Экраны"],
    dependencies=[Depends(get_current_user)],
)

# Короткие псевдонимы для внедряемых зависимостей (чтобы не повторять длинную запись).
Repo = Annotated[ScreenRepository, Depends(get_screen_repository)]
ScreenTypeRepo = Annotated[ScreenTypeRepository, Depends(get_screen_type_repository)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]
Expiry = Annotated[int, Depends(get_presign_expiry)]
# Текущий пользователь (для guest-редакции). Зависимость та же, что на роутере —
# FastAPI её дедуплицирует, поэтому дополнительной проверки токена не будет.
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "",
    response_model=list[ScreenRead],
    summary="Список экранов (с фильтрами)",
    dependencies=[Depends(expire_due_screens)],  # ленивая авто-архивация по истечению (FR-4.4)
)
def list_screens(
    repo: Repo,
    storage: Storage,
    expiry: Expiry,
    current_user: CurrentUser,
    pagination: Annotated[PaginationParams, Depends()],
    landlord_id: UUID | None = None,
    status_filter: Annotated[ScreenStatus | None, "фильтр по статусу"] = None,
    city_id: int | None = None,
    screen_type_id: int | None = None,
    campaign_id: UUID | None = None,
    contract_end_before: date | None = None,
) -> list[ScreenRead]:
    """Возвращает экраны, отфильтрованные по переданным параметрам (FR-1.2, FR-5).

    Параметры-фильтры необязательны и комбинируются по И. Пагинация — limit/offset.
    Фильтр по городу — по city_id, по типу экрана — по screen_type_id (§4.3):
    несуществующий screen_type_id даёт пустой список, а не ошибку.
    """
    filters = ScreenFilters(
        landlord_id=landlord_id,
        status=status_filter,
        city_id=city_id,
        screen_type_id=screen_type_id,
        campaign_id=campaign_id,
        contract_end_before=contract_end_before,
    )
    screens = ListScreensUseCase(repo).execute(filters)
    # Простейшая пагинация на уровне ответа (для MVP достаточно). limit=None
    # (по умолчанию, см. PaginationParams) — вернуть весь список без обрезания.
    end = None if pagination.limit is None else pagination.offset + pagination.limit
    page = screens[pagination.offset : end]
    is_guest = current_user.role is UserRole.GUEST
    return [screen_to_read(s, storage, expiry, is_guest=is_guest) for s in page]


@router.post(
    "",
    response_model=ScreenRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать экран",
    dependencies=[Depends(require_admin)],  # запись экранов — только admin
)
def create_screen(
    repo: Repo,
    screen_types: ScreenTypeRepo,
    storage: Storage,
    expiry: Expiry,
    payload: ScreenCreate,
) -> ScreenRead:
    """Создаёт новый экран (FR-10.1). Несуществующий screen_type_id → 422."""
    data = CreateScreenInput(
        name=payload.name,
        city_id=payload.city_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        size=payload.size,
        screen_type_id=payload.screen_type_id,
        status=payload.status,
        landlord_id=payload.landlord_id,
        contact_id=payload.contact_id,
        campaign_ids=tuple(payload.campaign_ids),
        comment=payload.comment,
        rental_end_date=payload.rental_end_date,
    )
    screen = CreateScreenUseCase(repo, screen_types).execute(data)
    return screen_to_read(screen, storage, expiry)


@router.post(
    "/cost-summary",
    response_model=CostSummaryResponse,
    summary="Расчёт стоимости выбранных экранов",
)
def cost_summary(
    repo: Repo, current_user: CurrentUser, payload: CostSummaryRequest
) -> CostSummaryResponse:
    """Считает количество, общую стоимость и разбивку по арендодателям (FR-6).

    Маршрут объявлен ДО '/{screen_id}', чтобы путь 'cost-summary' не был принят
    за идентификатор экрана. Для роли guest все денежные итоги форсятся в null (§4).
    """
    result = CostSummaryUseCase(repo).execute(payload.screen_ids)
    response = CostSummaryResponse(
        selected_count=result.selected_count,
        total=_money(result.total),
        by_landlord=[
            LandlordCostSchema(
                landlord_id=item.landlord_id,
                screens_count=item.screens_count,
                total=_money(item.total),
            )
            for item in result.by_landlord
        ],
    )
    if current_user.role is UserRole.GUEST:
        response = redact_cost_summary(response)
    return response


@router.get(
    "/dashboard-summary",
    response_model=DashboardSummaryResponse,
    summary="Сводная статистика для главного экрана",
    dependencies=[
        Depends(require_non_guest),  # ← первым: guest → 403 GUEST_FORBIDDEN ещё до sweep
        Depends(expire_due_screens),  # статусы в сводке — актуальные (FR-4.4)
    ],
)
def dashboard_summary(
    repo: Repo,
    current_user: CurrentUser,
    threshold_days: Annotated[
        int, Query(ge=1, le=365, description="Порог «скоро заканчивается», дней")
    ] = 30,
) -> DashboardSummaryResponse:
    """Считает сводку по всем экранам: счётчики, аренда активных, разбивка,
    договоры, заканчивающиеся в пределах threshold_days (FR-9).

    Маршрут объявлен ДО '/{screen_id}', чтобы 'dashboard-summary' не был принят
    за идентификатор экрана. Для роли guest денежные агрегаты форсятся в null (§4).
    """
    result = DashboardSummaryUseCase(repo).execute(DashboardSummaryInput(threshold_days=threshold_days))
    response = DashboardSummaryResponse(
        total_screens=result.total_screens,
        active_count=result.active_count,
        inactive_count=result.inactive_count,
        potential_count=result.potential_count,
        archived_count=result.archived_count,
        total_active_rent=_money(result.total_active_rent),
        by_landlord=[
            LandlordCostSchema(
                landlord_id=item.landlord_id,
                screens_count=item.screens_count,
                total=_money(item.total),
            )
            for item in result.by_landlord
        ],
        ending_soon=[
            EndingContractSchema(
                screen_id=item.screen_id,
                screen_name=item.screen_name,
                landlord_id=item.landlord_id,
                end_date=item.end_date,
            )
            for item in result.ending_soon
        ],
    )
    if current_user.role is UserRole.GUEST:
        response = redact_dashboard_summary(response)
    return response


@router.get(
    "/export",
    summary="Выгрузка экранов в Excel (.xlsx)",
    dependencies=[Depends(expire_due_screens)],  # отчёт отражает актуальные статусы (FR-4.4)
)
def export_screens(
    repo: Repo,
    current_user: CurrentUser,
    landlords_repo: Annotated[LandlordRepository, Depends(get_landlord_repository)],
    campaigns_repo: Annotated[CampaignRepository, Depends(get_campaign_repository)],
    screen_ids: Annotated[
        list[UUID] | None, Query(description="Выгрузить только эти экраны (FR-7.4)")
    ] = None,
    landlord_id: UUID | None = None,
    status_filter: Annotated[ScreenStatus | None, "фильтр по статусу"] = None,
    city_id: int | None = None,
    screen_type_id: int | None = None,
    campaign_id: UUID | None = None,
    contract_end_before: date | None = None,
) -> StreamingResponse:
    """Выгружает экраны в .xlsx (FR-7): по явному списку id (FR-7.4) либо по
    фильтрам (FR-7.1 — все активные через status_filter=active, FR-7.2 — по
    арендодателю, FR-7.3 — с учётом произвольных фильтров).

    Маршрут объявлен ДО '/{screen_id}', чтобы 'export' не был принят за id экрана.
    """
    export_input = ExportScreensInput(
        screen_ids=tuple(screen_ids) if screen_ids else (),
        filters=ScreenFilters(
            landlord_id=landlord_id,
            status=status_filter,
            city_id=city_id,
            screen_type_id=screen_type_id,
            campaign_id=campaign_id,
            contract_end_before=contract_end_before,
        ),
    )
    screens = ExportScreensUseCase(repo).execute(export_input)

    # Человекочитаемые названия для колонок «Арендодатель»/«Кампания» (FR-7.5).
    landlord_names = {item.id: item.name for item in landlords_repo.list()}
    campaign_names = {item.id: item.name for item in campaigns_repo.list()}

    content = build_screens_workbook(
        screens,
        landlord_names,
        campaign_names,
        is_guest=current_user.role is UserRole.GUEST,
    )
    filename = f"screens_export_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{screen_id}",
    response_model=ScreenRead,
    summary="Карточка экрана",
    dependencies=[Depends(expire_due_screens)],  # деталь показывает актуальный статус (FR-4.4)
)
def get_screen(
    repo: Repo, storage: Storage, expiry: Expiry, current_user: CurrentUser, screen_id: UUID
) -> ScreenRead:
    """Возвращает один экран по id (FR-3), с вложениями и свежими url. Если нет — 404.

    Для роли guest ответ редактируется (§4): цена → null, договор/документы
    (вложения не-PHOTO) не отдаются и не презайнятся.
    """
    is_guest = current_user.role is UserRole.GUEST
    return screen_to_read(repo.get_by_id(screen_id), storage, expiry, is_guest=is_guest)


@router.patch(
    "/{screen_id}",
    response_model=ScreenRead,
    summary="Редактировать экран",
    dependencies=[Depends(require_admin)],  # запись экранов — только admin
)
def update_screen(
    repo: Repo,
    screen_types: ScreenTypeRepo,
    storage: Storage,
    expiry: Expiry,
    screen_id: UUID,
    payload: ScreenUpdate,
) -> ScreenRead:
    """Частично обновляет экран (FR-10.2). size/screen_type_id обязательны (§4.2);
    несуществующий screen_type_id → 422."""
    data = UpdateScreenInput(
        screen_id=screen_id,
        size=payload.size,
        screen_type_id=payload.screen_type_id,
        name=payload.name,
        city_id=payload.city_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        status=payload.status,
        landlord_id=payload.landlord_id,
        contact_id=payload.contact_id,
        campaign_ids=tuple(payload.campaign_ids) if payload.campaign_ids is not None else None,
        comment=payload.comment,
        rental_end_date=payload.rental_end_date,
        # Отличаем «поле не прислано» от явного null: применяем дату только если
        # клиент её действительно передал (иначе PATCH других полей не затрёт дату).
        apply_rental_end_date="rental_end_date" in payload.model_fields_set,
    )
    screen = UpdateScreenUseCase(repo, screen_types).execute(data)
    return screen_to_read(screen, storage, expiry)


@router.patch(
    "/{screen_id}/location",
    response_model=ScreenRead,
    summary="Сменить локацию экрана (перетащить пин)",
    dependencies=[Depends(require_admin)],  # relocate — запись, только admin
)
def update_screen_location(
    repo: Repo, storage: Storage, expiry: Expiry, screen_id: UUID, payload: ScreenLocationUpdate
) -> ScreenRead:
    """Меняет только координаты экрана точкой на карте (FR-3.3).

    Узкий идемпотентный сценарий «перетащить пин и сохранить»: тело {lng, lat},
    возвращает полный ScreenRead с новой геометрией. Несуществующий id → 404 с
    машиночитаемым detail {"code": "SCREEN_NOT_FOUND"} (SSOT-контракт для фронта);
    координаты вне диапазона отсекает Pydantic (422) ещё до сценария.
    """
    data = UpdateScreenLocationInput(
        screen_id=screen_id,
        latitude=payload.lat,
        longitude=payload.lng,
    )
    try:
        screen = UpdateScreenLocationUseCase(repo).execute(data)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCREEN_NOT_FOUND"},
        ) from exc
    return screen_to_read(screen, storage, expiry)


@router.post(
    "/{screen_id}/activate",
    response_model=ScreenRead,
    summary="Активировать экран",
    dependencies=[Depends(require_admin)],  # активация — запись, только admin
)
def activate_screen(
    repo: Repo, storage: Storage, expiry: Expiry, screen_id: UUID, payload: ScreenActivateRequest
) -> ScreenRead:
    """Активирует экран, фиксируя договор аренды (FR-4).

    Проходит единый инвариант активации (тот же, что PATCH status=active и
    create-as-active): указан арендодатель и прикреплено фото (FR-4.2), задана
    сумма аренды и дата окончания (§5). Дата окончания договора становится
    rental_end_date экрана. Наличие договора-файла (Attachment типа CONTRACT) не
    требуется. Если инвариант не выполнен — 409 Conflict.
    """
    data = ActivateScreenInput(
        screen_id=screen_id,
        rent_price=payload.rent_price,
        start_date=payload.start_date,
        end_date=payload.end_date,
        currency=payload.currency,
    )
    screen = ActivateScreenUseCase(repo).execute(data)
    return screen_to_read(screen, storage, expiry)


@router.post(
    "/{screen_id}/attachments",
    response_model=ScreenRead,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить вложение (фото/договор/документ)",
    dependencies=[Depends(require_admin)],  # загрузка вложений — запись, только admin
)
async def upload_attachment(
    repo: Repo,
    storage: Storage,
    expiry: Expiry,
    screen_id: UUID,
    attachment_type: Annotated[str, Form(description="photo | contract | other")],
    file: Annotated[UploadFile, File(description="Файл вложения")],
) -> ScreenRead:
    """Кладёт файл в объектное хранилище (S3/MinIO) и прикрепляет его к экрану.

    Эндпоинт асинхронный, т.к. чтение загруженного файла (file.read) асинхронно.
    Неизвестный kind → 400; неверный MIME → 415; превышение размера → 413;
    отсутствующий экран → 404; достигнут лимит вложений вида → 409 с машиночитаемым
    detail (проверки типа/размера/экрана/лимита делает сценарий).
    """
    try:
        kind = AttachmentType(attachment_type)
    except ValueError as exc:
        raise ValidationError(
            f"Неизвестный тип вложения: '{attachment_type}'. Допустимо: photo | contract | other."
        ) from exc
    content = await file.read()
    data = AddAttachmentInput(
        screen_id=screen_id,
        attachment_type=kind,
        filename=file.filename or "file",
        content_type=file.content_type or "application/octet-stream",
        data=content,
    )
    try:
        screen = AddAttachmentUseCase(repo, storage).execute(data)
    except AttachmentLimitExceededError as exc:
        # 409 с машиночитаемым телом (SSOT-контракт, продублирован во фронт-инструкции):
        # фронт различает эту ошибку по detail.code, а не по тексту сообщения.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ATTACHMENT_LIMIT_EXCEEDED",
                "kind": exc.kind.value,
                "max": exc.max_allowed,
            },
        ) from exc
    return screen_to_read(screen, storage, expiry)


@router.get(
    "/{screen_id}/attachments/{attachment_id}/download-url",
    response_model=AttachmentUrlResponse,
    summary="Обновить presigned-ссылку на вложение",
)
def refresh_attachment_url(
    repo: Repo,
    storage: Storage,
    expiry: Expiry,
    current_user: CurrentUser,
    screen_id: UUID,
    attachment_id: UUID,
) -> AttachmentUrlResponse:
    """Возвращает свежую presigned-ссылку на скачивание вложения (для протухшей ссылки).

    Проверяет, что вложение принадлежит экрану; иначе — 404. Этот GET открыт и для
    guest, поэтому здесь тоже держим границу безопасности (§0): гость НЕ получает
    presigned-url на договор/документ. Для guest любое вложение не-PHOTO трактуется
    как отсутствующее → 404 (тем же телом, что и «не найдено»), чтобы не выдать
    ссылку и не подтвердить существование документа.
    """
    screen = repo.get_by_id(screen_id)
    attachment = next((a for a in screen.attachments if a.id == attachment_id), None)
    is_guest = current_user.role is UserRole.GUEST
    if attachment is None or (is_guest and attachment.type is not AttachmentType.PHOTO):
        raise NotFoundError(
            f"Вложение id={attachment_id} не найдено у экрана id={screen_id}."
        )
    url = storage.generate_presigned_get_url(attachment.object_key, expiry)
    return AttachmentUrlResponse(url=url, expires_in=expiry)


@router.delete(
    "/{screen_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить вложение экрана",
    dependencies=[Depends(require_admin)],  # удаление вложений — запись, только admin
)
def delete_attachment(
    repo: Repo, storage: Storage, screen_id: UUID, attachment_id: UUID
) -> None:
    """Удаляет вложение из БД и (best-effort) из хранилища. Успех → 204.

    Несуществующее вложение ИЛИ чужой screen_id → 404 с телом контракта
    {"detail": "Attachment not found"} (SSOT, продублирован во фронт-инструкции).
    """
    try:
        DeleteAttachmentUseCase(repo, storage).execute(
            DeleteAttachmentInput(screen_id=screen_id, attachment_id=attachment_id)
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        ) from exc


@router.delete(
    "/{screen_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить экран",
    dependencies=[Depends(require_admin)],  # удаление экрана — запись, только admin
)
def delete_screen(repo: Repo, screen_id: UUID) -> None:
    """Удаляет экран по id."""
    repo.delete(screen_id)


def _money(money: Money) -> MoneySchema:
    """Вспомогательная функция: доменный Money → схема MoneySchema."""
    return MoneySchema(amount=money.amount, currency=money.currency)
