"""Тесты доменных правил и сценариев модуля «кампании» (FR-3.10).

Без БД: используется фейковый репозиторий в памяти.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from core.domain.exceptions import ValidationError
from features.campaigns.application.dto import CreateCampaignInput, UpdateCampaignInput
from features.campaigns.application.use_cases import (
    CreateCampaignUseCase,
    ListCampaignsUseCase,
    UpdateCampaignUseCase,
)
from features.campaigns.domain.entities import Campaign
from features.campaigns.domain.repositories import CampaignRepository


class FakeCampaignRepository(CampaignRepository):
    """Репозиторий в памяти — подмена БД для тестов сценариев."""

    def __init__(self, campaigns: list[Campaign] | None = None) -> None:
        self._items = {c.id: c for c in (campaigns or [])}

    def get_by_id(self, campaign_id: UUID) -> Campaign:
        return self._items[campaign_id]

    def list(self) -> list[Campaign]:
        return list(self._items.values())

    def add(self, campaign: Campaign) -> Campaign:
        """Имитирует поведение SQLAlchemy-репозитория: присваивает id при сохранении."""
        if campaign.id is None:
            campaign.id = uuid4()
        self._items[campaign.id] = campaign
        return campaign

    def update(self, campaign: Campaign) -> Campaign:
        self._items[campaign.id] = campaign
        return campaign

    def delete(self, campaign_id: UUID) -> None:
        self._items.pop(campaign_id, None)


def test_campaign_requires_non_empty_name() -> None:
    """Нельзя создать кампанию с пустым названием."""
    with pytest.raises(ValidationError):
        Campaign(name="  ")


def test_create_campaign_use_case() -> None:
    """Сценарий создания сохраняет кампанию."""
    repo = FakeCampaignRepository()

    campaign = CreateCampaignUseCase(repo).execute(CreateCampaignInput(name="Новогодняя акция"))

    assert campaign.name == "Новогодняя акция"
    assert campaign.id is not None


def test_update_campaign_use_case_rejects_empty_name() -> None:
    """Переименование в пустое название отклоняется до обращения к репозиторию."""
    repo = FakeCampaignRepository([Campaign(name="Старое", id=uuid4())])
    campaign_id = next(iter(repo.list())).id

    with pytest.raises(ValidationError):
        UpdateCampaignUseCase(repo).execute(UpdateCampaignInput(campaign_id=campaign_id, name=" "))


def test_list_campaigns_use_case() -> None:
    """Сценарий списка возвращает все сохранённые кампании."""
    repo = FakeCampaignRepository([Campaign(name="A", id=uuid4()), Campaign(name="B", id=uuid4())])

    result = ListCampaignsUseCase(repo).execute()

    assert len(result) == 2
