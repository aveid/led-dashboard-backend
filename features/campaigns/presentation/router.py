"""router.py — REST-эндпоинты справочника кампаний (FR-3.10)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from core.api.auth import get_current_user, require_admin
from features.campaigns.application.dto import CreateCampaignInput, UpdateCampaignInput
from features.campaigns.application.use_cases import (
    CreateCampaignUseCase,
    ListCampaignsUseCase,
    UpdateCampaignUseCase,
)
from features.campaigns.domain.repositories import CampaignRepository

from .deps import get_campaign_repository
from .mappers import campaign_to_read
from .schemas import CampaignCreate, CampaignRead, CampaignUpdate

router = APIRouter(
    prefix="/api/campaigns",
    tags=["Кампании"],
    dependencies=[Depends(get_current_user)],
)

Repo = Annotated[CampaignRepository, Depends(get_campaign_repository)]


@router.get("", response_model=list[CampaignRead], summary="Список кампаний")
def list_campaigns(repo: Repo) -> list[CampaignRead]:
    """Возвращает все кампании (для справочника/выбора на карточке экрана)."""
    campaigns = ListCampaignsUseCase(repo).execute()
    return [campaign_to_read(c) for c in campaigns]


@router.post(
    "",
    response_model=CampaignRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать кампанию",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def create_campaign(repo: Repo, payload: CampaignCreate) -> CampaignRead:
    """Создаёт новую кампанию (FR-3.10)."""
    campaign = CreateCampaignUseCase(repo).execute(CreateCampaignInput(name=payload.name))
    return campaign_to_read(campaign)


@router.get("/{campaign_id}", response_model=CampaignRead, summary="Карточка кампании")
def get_campaign(repo: Repo, campaign_id: UUID) -> CampaignRead:
    """Возвращает одну кампанию по id. Если нет — 404."""
    return campaign_to_read(repo.get_by_id(campaign_id))


@router.patch(
    "/{campaign_id}",
    response_model=CampaignRead,
    summary="Переименовать кампанию",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def update_campaign(repo: Repo, campaign_id: UUID, payload: CampaignUpdate) -> CampaignRead:
    """Переименовывает кампанию."""
    data = UpdateCampaignInput(campaign_id=campaign_id, name=payload.name)
    campaign = UpdateCampaignUseCase(repo).execute(data)
    return campaign_to_read(campaign)


@router.delete(
    "/{campaign_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить кампанию",
    dependencies=[Depends(require_admin)],  # запись справочника — только admin
)
def delete_campaign(repo: Repo, campaign_id: UUID) -> None:
    """Удаляет кампанию (связь с экранами снимается каскадно)."""
    repo.delete(campaign_id)
