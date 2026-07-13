"""use_cases.py — сценарии модуля кампаний (create / update / list)."""

from __future__ import annotations

from core.application.use_case import UseCase
from features.campaigns.application.dto import CreateCampaignInput, UpdateCampaignInput
from features.campaigns.domain.entities import Campaign
from features.campaigns.domain.repositories import CampaignRepository


class CreateCampaignUseCase(UseCase[CreateCampaignInput, Campaign]):
    """Создаёт новую кампанию."""

    def __init__(self, repository: CampaignRepository) -> None:
        self._repository = repository

    def execute(self, data: CreateCampaignInput) -> Campaign:
        """Собирает доменную кампанию (с валидацией) и сохраняет."""
        campaign = Campaign(name=data.name)
        return self._repository.add(campaign)


class UpdateCampaignUseCase(UseCase[UpdateCampaignInput, Campaign]):
    """Переименовывает существующую кампанию."""

    def __init__(self, repository: CampaignRepository) -> None:
        self._repository = repository

    def execute(self, data: UpdateCampaignInput) -> Campaign:
        """Загружает кампанию, проверяет и применяет новое название."""
        from core.domain.exceptions import ValidationError

        if not data.name.strip():
            raise ValidationError("У кампании должно быть непустое название.")
        campaign = self._repository.get_by_id(data.campaign_id)
        campaign.name = data.name
        return self._repository.update(campaign)


class ListCampaignsUseCase(UseCase[None, list[Campaign]]):
    """Возвращает список всех кампаний (для справочника)."""

    def __init__(self, repository: CampaignRepository) -> None:
        self._repository = repository

    def execute(self, data: None = None) -> list[Campaign]:
        """Отдаёт все кампании."""
        return self._repository.list()
