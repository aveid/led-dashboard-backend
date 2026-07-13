"""router.py — REST-эндпоинты справочника арендодателей (FR-8).

Эндпоинты тонкие: вызывают use case и возвращают ответ. Простые операции
(get/delete) обращаются к репозиторию напрямую — отдельный use case для них
был бы лишней прослойкой без логики.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from core.api.auth import get_current_user, require_admin
from features.users.domain.entities import User, UserRole
from features.landlords.application.dto import CreateLandlordInput, UpdateLandlordInput
from features.landlords.application.use_cases import (
    CreateLandlordUseCase,
    ListLandlordsUseCase,
    UpdateLandlordUseCase,
)
from features.landlords.domain.exceptions import LandlordNotFoundError
from features.landlords.domain.repositories import LandlordRepository
from features.screens.application.use_cases.list_screens_by_landlord import (
    ListScreensByLandlordUseCase,
)
from features.screens.domain.repositories import ScreenRepository
from features.screens.presentation.deps import expire_due_screens, get_screen_repository
from features.screens.presentation.guest_redaction import redact_landlord_brief
from features.screens.presentation.mappers import landlord_screen_brief_to_read
from features.screens.presentation.schemas import LandlordScreenBrief

from .deps import get_landlord_repository
from .mappers import landlord_to_read
from .schemas import LandlordCreate, LandlordRead, LandlordUpdate

router = APIRouter(
    prefix="/api/landlords",
    tags=["Арендодатели"],
    dependencies=[Depends(get_current_user)],
)

Repo = Annotated[LandlordRepository, Depends(get_landlord_repository)]
ScreenRepo = Annotated[ScreenRepository, Depends(get_screen_repository)]


@router.get("", response_model=list[LandlordRead], summary="Список арендодателей")
def list_landlords(repo: Repo) -> list[LandlordRead]:
    """Возвращает всех арендодателей (для справочника/выпадающих списков)."""
    landlords = ListLandlordsUseCase(repo).execute()
    return [landlord_to_read(item) for item in landlords]


@router.post(
    "",
    response_model=LandlordRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать арендодателя",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def create_landlord(repo: Repo, payload: LandlordCreate) -> LandlordRead:
    """Создаёт нового арендодателя (FR-8)."""
    data = CreateLandlordInput(**payload.model_dump())
    landlord = CreateLandlordUseCase(repo).execute(data)
    return landlord_to_read(landlord)


@router.get("/{landlord_id}", response_model=LandlordRead, summary="Карточка арендодателя")
def get_landlord(repo: Repo, landlord_id: UUID) -> LandlordRead:
    """Возвращает одного арендодателя по id. Если нет — 404."""
    return landlord_to_read(repo.get_by_id(landlord_id))


@router.get(
    "/{landlord_id}/screens",
    response_model=list[LandlordScreenBrief],
    summary="Экраны арендодателя (облегчённый список)",
    # Ленивая авто-архивация по истечению (FR-4.4): иначе счётчик/Σ арендодателя
    # увидели бы устаревший active. Sweep идёт в той же сессии → статусы актуальны.
    dependencies=[Depends(expire_due_screens)],
)
def list_landlord_screens(
    repo: Repo,
    screen_repo: ScreenRepo,
    current_user: Annotated[User, Depends(get_current_user)],
    landlord_id: UUID,
) -> list[LandlordScreenBrief]:
    """Плоский список облегчённых экранов арендодателя (FR-8.5).

    Раскрытие карточки арендодателя в список его экранов. Ответ — bare array
    компактных брифов (без attachments/presign). Счётчик «Экранов: N» (FR-8.3)
    фронт считает как длину этого списка. Несуществующий арендодатель → 404 с
    машиночитаемым телом {"detail": {"code": "LANDLORD_NOT_FOUND"}}; существующий
    без экранов → 200 с []. Для роли guest цена каждого брифа форсится в null (§4).
    """
    try:
        briefs = ListScreensByLandlordUseCase(screen_repo, repo).execute(landlord_id)
    except LandlordNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LANDLORD_NOT_FOUND"},
        ) from exc
    reads = [landlord_screen_brief_to_read(brief) for brief in briefs]
    if current_user.role is UserRole.GUEST:
        reads = [redact_landlord_brief(read) for read in reads]
    return reads


@router.patch(
    "/{landlord_id}",
    response_model=LandlordRead,
    summary="Редактировать арендодателя",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def update_landlord(repo: Repo, landlord_id: UUID, payload: LandlordUpdate) -> LandlordRead:
    """Частично обновляет арендодателя."""
    data = UpdateLandlordInput(landlord_id=landlord_id, **payload.model_dump())
    landlord = UpdateLandlordUseCase(repo).execute(data)
    return landlord_to_read(landlord)


@router.delete(
    "/{landlord_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить арендодателя",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def delete_landlord(repo: Repo, landlord_id: UUID) -> None:
    """Удаляет арендодателя. У связанных экранов landlord_id очищается (SET NULL)."""
    repo.delete(landlord_id)
