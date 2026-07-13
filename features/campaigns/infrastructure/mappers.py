"""mappers.py — преобразование ORM-модели кампании в доменную сущность."""

from __future__ import annotations

from features.campaigns.domain.entities import Campaign

from .models import CampaignModel


def campaign_to_domain(model: CampaignModel) -> Campaign:
    """Строка campaigns (ORM) → доменная Campaign."""
    return Campaign(name=model.name, id=model.id)
